"""
Usage:
    from src.nlu.extractor import extract_intent_entities_and_update
    result = extract_intent_entities_and_update(user_id="u1", conversation_id="c1",
                                                 user_message="Can I submit this assignment tomorrow?")
    # result contains the structured extraction + resolved entity ids + graph update info
"""

import os
import json
import re
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from openai import OpenAI  
from neo4j import GraphDatabase

# reuse same env names as other modules
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "test1234")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", None)
GROQ_BASE_URL = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")  # if needed

# ------------- what to extract ----------------
INTENT_LABELS = [
    "deadline_help",
    "extension_request",
    "assignment_help",
    "progress_query",
    "general_question",
]

ENTITY_KEYS = [
    "assignment_name",
    "course_name",
    "date_reference",   # e.g., "tomorrow", "2026-02-16"
    "decision_type",    # e.g., "extension"
    "goal_name",
]


# ------------- Helpers: date normalization -------------
def normalize_date_reference(date_ref: Optional[str], anchor: Optional[datetime] = None) -> Optional[str]:
    """
    Convert common relative date strings to ISO datetime strings.
    Very small, robust set: "today", "tomorrow", "next week", explicit YYYY-MM-DD or ISO strings pass-through.
    Returns ISO datetime string (date-only or datetime) or None.
    """
    if not date_ref:
        return None
    text = date_ref.strip().lower()
    now = anchor or datetime.utcnow()

    # direct ISO/date pattern
    iso_like = None
    # quick ISO detection YYYY-MM-DD
    m = re.match(r"(\d{4}-\d{2}-\d{2})", text)
    if m:
        try:
            dt = datetime.fromisoformat(m.group(1))
            return dt.isoformat()
        except Exception:
            pass

    if "today" in text:
        return now.isoformat()
    if "tomorrow" in text:
        return (now + timedelta(days=1)).isoformat()
    if "next week" in text:
        return (now + timedelta(days=7)).isoformat()
    if "yesterday" in text:
        return (now - timedelta(days=1)).isoformat()

    # fallback: try parsing numbers like "in 2 days"
    m = re.search(r"in\s+(\d+)\s+day", text)
    if m:
        days = int(m.group(1))
        return (now + timedelta(days=days)).isoformat()

    # if nothing matched, return the raw string to allow human-in-loop verification
    return date_ref


# ------------- LLM-based structured extraction prompt ----------------
EXTRACTION_INSTRUCTIONS = """
Extract the user's intent and relevant entities from the following user message.
Output JSON only (no extra text) with the exact schema:
{
  "intent": "<one_of_allowed_intents>",
  "confidence": <float between 0 and 1>,
  "entities": {
    "assignment_name": "<optional string or null>",
    "course_name": "<optional string or null>",
    "date_reference": "<optional string like 'tomorrow' or '2026-02-16' or null>",
    "decision_type": "<optional string like 'extension' or null>",
    "goal_name": "<optional string or null>"
  }
}

Allowed intents: %s

User message:
""" % (json.dumps(INTENT_LABELS))


def _call_llm_extractor(user_message: str) -> Optional[str]:
    """
    Calls Groq-compatible LLM to perform structured extraction.
    Returns raw text (expected to be JSON). Falls back to None on error.
    """
    # if no GROQ_API_KEY, don't attempt network call here. Caller will fallback to mock.
    if not GROQ_API_KEY:
        return None

    client = OpenAI(api_key=GROQ_API_KEY, base_url=GROQ_BASE_URL)
    prompt = EXTRACTION_INSTRUCTIONS + "\n\n" + user_message.strip()

    try:
        resp = client.chat.completions.create(
            model="llama-3.3-70b-versatile",  # align with client usage in repo
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=300,
        )
        text = resp.choices[0].message.content.strip()
        return text
    except Exception as e:
        # graceful fallback to None so mock code runs
        print(f"[NLU] LLM extraction error: {e}")
        return None


# ------------- Entity resolution (graph lookups) -------------
# We'll use Neo4j driver directly here to find assignments & other entities by fuzzy match.

_driver = None


def _get_driver():
    global _driver
    if _driver is None:
        _driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    return _driver


def resolve_assignment_by_name(assignment_name: str) -> Optional[Dict[str, Any]]:
    """
    Try to find a single assignment node whose title contains the assignment_name (case-insensitive).
    Returns a dict of node properties or None.
    """
    if not assignment_name:
        return None
    q = """
    MATCH (a:Assignment)
    WHERE toLower(a.title) CONTAINS toLower($q)
    RETURN a LIMIT 1
    """
    drv = _get_driver()
    with drv.session() as s:
        rec = s.run(q, q=assignment_name).single()
        if not rec:
            return None
        node = dict(rec["a"])
        # ensure assignment_id present
        if "assignment_id" not in node and "title" in node:
            # fallback generate id if not present
            node["assignment_id"] = node.get("assignment_id") or re.sub(r'\W+', '_', node.get("title")).lower()
        return node


def resolve_course_by_name(course_name: str) -> Optional[Dict[str, Any]]:
    if not course_name:
        return None
    q = """
    MATCH (c:Course)
    WHERE toLower(c.title) CONTAINS toLower($q)
    RETURN c LIMIT 1
    """
    drv = _get_driver()
    with drv.session() as s:
        rec = s.run(q, q=course_name).single()
        return dict(rec["c"]) if rec else None


def resolve_goal_by_name(goal_name: str) -> Optional[Dict[str, Any]]:
    if not goal_name:
        return None
    q = """
    MATCH (g:Goal)
    WHERE toLower(g.title) CONTAINS toLower($q)
    RETURN g LIMIT 1
    """
    drv = _get_driver()
    with drv.session() as s:
        rec = s.run(q, q=goal_name).single()
        return dict(rec["g"]) if rec else None


# ------------- Step 5/6: Graph updates - create Intent node & relationships -------------
def create_intent_node_and_link(conversation_id: str, intent_label: str, confidence: float, raw_entities: Dict[str, Any]):
    """
    Creates an Intent node with properties and links it from the Conversation node.
    Returns created intent_id (generated) and node properties.
    """
    drv = _get_driver()
    now_iso = datetime.utcnow().isoformat()
    # create a generated id for the intent node
    generated_intent_id = f"intent_{int(now_iso.replace('-', '').replace(':', '').replace('T','').split('.')[0])}"

    create_query = """
    MERGE (i:Intent {intent_id:$intent_id})
    SET i.label = $label, i.confidence = $confidence, i.raw_entities = $raw_entities, i.created_at = $created_at
    WITH i
    MATCH (c:Conversation {conversation_id:$conversation_id})
    MERGE (c)-[:INFERRED_INTENT]->(i)
    RETURN i
    """
    with drv.session() as s:
        rec = s.run(create_query, intent_id=generated_intent_id, label=intent_label,
                    confidence=float(confidence), raw_entities=json.dumps(raw_entities),
                    created_at=now_iso, conversation_id=conversation_id).single()
        
        if rec is None:
            raise ValueError("Intent creation query returned no result. Check MATCH conditions.")
        node = dict(rec["i"])
        node["intent_id"] = generated_intent_id
        return node


def link_conversation_about_assignment(conversation_id: str, assignment_id: str):
    """
    Create (conv)-[:ABOUT]->(assignment)
    """
    if not assignment_id:
        return False
    drv = _get_driver()
    q = """
    MATCH (c:Conversation {conversation_id:$conversation_id}), (a:Assignment {assignment_id:$aid})
    MERGE (c)-[:ABOUT]->(a)
    RETURN a
    """
    with drv.session() as s:
        rec = s.run(q, conversation_id=conversation_id, aid=assignment_id).single()
        return bool(rec)


# ------------- Top-level orchestration  ----------------
def extract_intent_entities_and_update(user_id: str, conversation_id: str, user_message: str) -> Dict[str, Any]:
    """
    Full pipeline:
    1) call LLM extractor (or mock)
    2) parse JSON result / fallback to mock
    3) normalize date references
    4) resolve extracted entity strings to graph node dicts (assignment, course, goal)
    5) create Intent node and link to Conversation (graph update)
    6) optionally link conversation ABOUT assignment if resolved

    Returns a dict with:
      {
         "extraction": {intent, confidence, entities_raw},
         "entities_resolved": {assignment: {...}, course: {...}, goal: {...}},
         "intent_node": {...},
         "linked_about_assignment": True/False
      }
    """
    # 1) call LLM
    raw = _call_llm_extractor(user_message)
    parsed = None
    if raw:
        # try to parse JSON cleanly
        try:
            parsed = json.loads(raw)
        except Exception:
            # sometimes models wrap code blocks; try to find first JSON-like substring
            m = re.search(r"\{.*\}", raw, re.DOTALL)
            if m:
                try:
                    parsed = json.loads(m.group(0))
                except Exception:
                    parsed = None

    if not parsed:
        # fallback to deterministic mock extractor
        print('could not parse json from llm')

    # enforce schema keys
    intent_label = parsed.get("intent") if parsed.get("intent") in INTENT_LABELS else "general_question"
    confidence = float(parsed.get("confidence") or 0.0)
    entities_raw = parsed.get("entities") or {}

    # 3) normalize dates
    date_ref = entities_raw.get("date_reference")
    normalized_date = normalize_date_reference(date_ref) if date_ref else None
    if normalized_date:
        entities_raw["date_reference_normalized"] = normalized_date

    # 4) resolve entities (assignment, course, goal)
    resolved = {"assignment": None, "course": None, "goal": None}

    assignment_name = entities_raw.get("assignment_name")
    if assignment_name:
        resolved_assignment = resolve_assignment_by_name(assignment_name)
        if resolved_assignment:
            resolved["assignment"] = resolved_assignment

    # if not found by name, attempt to resolve by context: user's goals -> assignment
    if not resolved["assignment"]:
        # look up user's goals and try to resolve assignment from goal via queries (simple approach)
        # we attempt a Cypher that finds assignment under user's goals
        drv = _get_driver()
        with drv.session() as s:
            q = """
            MATCH (u:Student {student_id:$uid})-[:HAS_GOAL]->(g:Goal)-[:REQUIRES]->(a:Assignment)
            RETURN a LIMIT 1
            """
            rec = s.run(q, uid=user_id).single()
            if rec:
                resolved["assignment"] = dict(rec["a"])

    # resolve course/goal if provided in raw entities
    if entities_raw.get("course_name"):
        resolved["course"] = resolve_course_by_name(entities_raw.get("course_name"))
    if entities_raw.get("goal_name"):
        resolved["goal"] = resolve_goal_by_name(entities_raw.get("goal_name"))

    # 5) create Intent node and link to conversation
    intent_node = create_intent_node_and_link(conversation_id=conversation_id,
                                              intent_label=intent_label,
                                              confidence=confidence,
                                              raw_entities=entities_raw)

    # 6) optionally link conversation ABOUT assignment if resolved
    linked_about = False
    if resolved.get("assignment"):
        aid = resolved["assignment"].get("assignment_id")
        if aid:
            linked_about = link_conversation_about_assignment(conversation_id, aid)

    return {
        "extraction": {
            "intent": intent_label,
            "confidence": confidence,
            "entities_raw": entities_raw,
        },
        "entities_resolved": resolved,
        "intent_node": intent_node,
        "linked_about_assignment": linked_about,
    }


# If run directly, quick demo using seeded data assumptions
if __name__ == "__main__":
    sample = "Can I submit this assignment tomorrow?"
    out = extract_intent_entities_and_update(user_id="s1", conversation_id="c1", user_message=sample)
    print(json.dumps(out, default=str, indent=2))