# src/graph/queries.py
from typing import Optional

from neo4j import GraphDatabase
import os

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "test1234")

_driver = None


def _get_driver():
    global _driver
    if _driver is None:
        _driver = GraphDatabase.driver(
            NEO4J_URI,
            auth=(NEO4J_USER, NEO4J_PASSWORD)
        )
    return _driver


def _node_to_dict(node):
    return dict(node)


# -----------------------------
# Student
# -----------------------------
def get_student(student_id):
    drv = _get_driver()
    with drv.session() as s:
        result = s.run(
            "MATCH (st:Student {student_id:$sid}) RETURN st",
            sid=student_id
        )
        rec = result.single()
        return _node_to_dict(rec["st"]) if rec else None

def _get_student_courses(student_id: str) -> list:
    with _get_driver().session() as s:
        return [
            _node_to_dict(r["cr"])
            for r in s.run(
                "MATCH (st:Student {student_id:$sid})-[:ENROLLED_IN]->(cr:Course) RETURN cr",
                sid=student_id,
            )
        ]


def _get_all_student_decisions(student_id: str) -> list:
    with _get_driver().session() as s:
        return [
            _node_to_dict(r["d"])
            for r in s.run(
                """
                MATCH (st:Student {student_id:$sid})-[:HAS_DECISION]->(d:Decision)
                RETURN d ORDER BY d.valid_until DESC
                """,
                sid=student_id,
            )
        ]


# -----------------------------
# Screen
# -----------------------------
def get_current_screen(student_id):
    drv = _get_driver()
    with drv.session() as s:
        q = """
        MATCH (st:Student {student_id:$sid})-[:CURRENT_SCREEN]->(s:Screen)
        RETURN s
        """
        rec = s.run(q, sid=student_id).single()
        return _node_to_dict(rec["s"]) if rec else None


# -----------------------------
# Goals
# -----------------------------
def get_student_goals(student_id):
    drv = _get_driver()
    with drv.session() as s:
        q = """
        MATCH (st:Student {student_id:$sid})-[:HAS_GOAL]->(g:Goal)
        RETURN g
        """
        res = s.run(q, sid=student_id)
        return [_node_to_dict(r["g"]) for r in res]


# -----------------------------
# Assignment
# -----------------------------
def get_assignment_for_goal(goal_id):
    drv = _get_driver()
    with drv.session() as s:
        q = """
        MATCH (g:Goal {goal_id:$gid})-[:REQUIRES]->(a:Assignment)
        RETURN a
        """
        rec = s.run(q, gid=goal_id).single()
        return _node_to_dict(rec["a"]) if rec else None

def get_assignment(assignment_id):
    drv = _get_driver()
    with drv.session() as s:
        result = s.run(
            "MATCH (a:Assignment {assignment_id:$aid}) RETURN a",
            aid=assignment_id
        )
        rec = result.single()
        return _node_to_dict(rec["a"]) if rec else None

def _resolve_assignment(student_id: str, entities: dict, screen: Optional[dict]) -> Optional[dict]:
    """
    Resolve a single assignment from:
    1. Explicit assignment_id in entities (already resolved by extractor)
    2. Explicit goal_id in entities
    3. Screen is an assignment page -> first goal's assignment
    4. Fallback: first assignment across all goals
    """
    if entities.get("assignment_id"):
        return get_assignment(entities["assignment_id"])

    if entities.get("goal_id"):
        a = get_assignment_for_goal(entities["goal_id"])
        if a:
            return a

    goals = get_student_goals(student_id)

    if screen and screen.get("name", "").lower().startswith("assignment"):
        for g in goals:
            a = get_assignment_for_goal(g["goal_id"])
            if a:
                return a

    for g in goals:
        a = get_assignment_for_goal(g["goal_id"])
        if a:
            return a

    return None

# -----------------------------
# Deadline
# -----------------------------
def get_deadline(assignment_id):
    drv = _get_driver()
    with drv.session() as s:
        q = """
        MATCH (a:Assignment {assignment_id:$aid})-[:HAS_DEADLINE]->(d:Deadline)
        RETURN d
        """
        rec = s.run(q, aid=assignment_id).single()
        return _node_to_dict(rec["d"]) if rec else None


# -----------------------------
# Decisions (NEW MODEL)
# Student -> HAS_DECISION -> Decision
# Decision -> ABOUT -> Assignment
# -----------------------------
def get_active_decisions(student_id, assignment_id):
    drv = _get_driver()
    with drv.session() as s:
        q = """
        MATCH (st:Student {student_id:$sid})-[:HAS_DECISION]->(d:Decision)
        MATCH (d)-[:ABOUT]->(a:Assignment {assignment_id:$aid})
        WHERE d.status IN ['approved', 'active']
        RETURN d
        ORDER BY d.valid_until DESC
        """
        res = s.run(q, sid=student_id, aid=assignment_id)
        return [_node_to_dict(r["d"]) for r in res]


# -----------------------------
# Intent
# Student -> HAS_CONVERSATION -> Conversation -> INFERRED_INTENT -> Intent
# -----------------------------
def get_last_intent(student_id):
    drv = _get_driver()
    with drv.session() as s:
        q = """
        MATCH (st:Student {student_id:$sid})
              -[:HAS_CONVERSATION]->(c:Conversation)
              -[:INFERRED_INTENT]->(i:Intent)
        RETURN i
        ORDER BY c.started_at DESC
        LIMIT 1
        """
        rec = s.run(q, sid=student_id).single()
        return _node_to_dict(rec["i"]) if rec else None