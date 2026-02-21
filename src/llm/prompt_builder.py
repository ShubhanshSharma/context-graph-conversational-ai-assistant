# src/llm/prompt_builder.py
from datetime import datetime
from typing import Any, Dict, Optional, List


SYSTEM_INSTRUCTIONS = """You are helpful, factual student support assistant.
Use only the provided facts. Do not hallucinate. If answering requires missing facts, ask a concise clarifying question.
When referencing a fact, include its source id in square brackets, e.g. [Assignment:a1], [Decision:dec1].
Keep answers short and actionable.
"""


def _fmt_dt(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    # If naive datetime, use isoformat (seed currently creates naive datetimes)
    try:
        return dt.isoformat()
    except Exception:
        return str(dt)


def _list_decision_lines(decisions: List[Dict[str, Any]]) -> List[str]:
    lines = []
    for d in decisions:
        decision_id = d.get("decision_id") or d.get("id") or "unknown"
        d_type = d.get("type") or d.get("decision_type") or "decision"
        status = d.get("status")
        valid_until = _fmt_dt(d.get("valid_until"))
        # indicate scope/applies_to if present
        applies_to = d.get("assignment_id") or d.get("applies_to") or d.get("scope_id")
        scope_note = f" applies_to={applies_to}" if applies_to else ""
        lines.append(f"- [{decision_id}] {d_type} ({status}){scope_note}" + (f", valid_until={valid_until}" if valid_until else ""))
    return lines


def build_context_text(context: Dict[str, Any]) -> str:
    """
    Build a small block of facts from the context selector output.
    Expected keys in context: user, screen, intent, assignment, deadline, decisions, effective_deadline
    """
    parts = []

    user = context.get("user")
    if user:
        parts.append(f"User: {user.get('name')} [User:{user.get('user_id')}] (role={user.get('role', 'unknown')})")

    screen = context.get("screen")
    if screen:
        parts.append(f"Current screen: {screen.get('name')} [Screen:{screen.get('screen_id')}]")

    intent = context.get("intent")
    if intent:
        parts.append(f"Last inferred intent: {intent.get('label')} (confidence={intent.get('confidence')}) [Intent:{intent.get('intent_id')}]")

    assignment = context.get("assignment")
    if assignment:
        parts.append(f"Assignment: {assignment.get('title')} [Assignment:{assignment.get('assignment_id')}] (status={assignment.get('status')})")

    deadline = context.get("deadline")
    if deadline:
        due = _fmt_dt(deadline.get("due_at"))
        parts.append(f"Original deadline: {due} [Deadline:{deadline.get('deadline_id')}] (type={deadline.get('type')})")

    # decisions list
    decisions = context.get("decisions") or []
    if decisions:
        parts.append("Decisions affecting this assignment:")
        parts.extend(_list_decision_lines(decisions))

    effective = context.get("effective_deadline")
    if effective:
        parts.append(f"Effective deadline (computed): {_fmt_dt(effective)}")

    # Provenance hint
    parts.append("Provenance: facts come from the context graph; cite node ids when referencing facts.")
    return "\n".join(parts)


def build_full_prompt(context: Dict[str, Any], user_message: str, system_instructions: Optional[str] = None) -> str:
    """
    Compose the final prompt to send to the LLM:
    [system instructions]
    [context facts]
    USER: <user_message>

    Returned string is plain text ready to pass to an API that expects a single prompt body.
    """
    sys_text = system_instructions or SYSTEM_INSTRUCTIONS
    facts = build_context_text(context)

    prompt = f"{sys_text}\n\nFACTS:\n{facts}\n\nUSER MESSAGE:\n{user_message}\n\nINSTRUCTIONS:\nAnswer using only the facts above. If facts are insufficient, ask one short clarifying question."
    return prompt


# quick demo when run directly
if __name__ == "__main__":
    # minimal fake context to show formatting
    from datetime import datetime, timedelta

    demo_ctx = {
        "user": {"user_id": "u1", "name": "Rahul", "role": "student"},
        "screen": {"screen_id": "s1", "name": "assignment_page"},
        "intent": {"intent_id": "i1", "label": "deadline_help", "confidence": 0.92},
        "assignment": {"assignment_id": "a1", "title": "Linear Equations Worksheet", "status": "pending"},
        "deadline": {"deadline_id": "d1", "due_at": datetime.utcnow(), "type": "hard"},
        "decisions": [
            {"decision_id": "dec1", "type": "extension", "status": "approved", "valid_until": datetime.utcnow() + timedelta(days=1), "assignment_id": "a1", "for_user": "u1"}
        ],
        "effective_deadline": datetime.utcnow() + timedelta(days=1),
    }

    user_msg = "Can I submit this assignment tomorrow?"
    print("=== PROMPT PREVIEW ===\n")
    print(build_full_prompt(demo_ctx, user_msg))
