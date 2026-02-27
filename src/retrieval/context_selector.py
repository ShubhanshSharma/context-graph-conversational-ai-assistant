# src/retrieval/context_selector.py
from datetime import datetime
from typing import Optional, Dict, Any, List

from src.graph.queries import (
    _get_all_student_decisions,
    _get_student_courses,
    _resolve_assignment,
    get_assignment,
    get_student,
    get_current_screen,
    get_student_goals,
    get_assignment_for_goal,
    get_deadline,
    get_active_decisions,
    get_last_intent,
)


def _safe_filter_active_decisions(decisions: List[dict]) -> List[dict]:
    now = datetime.utcnow()
    active = []

    for d in decisions:
        if not d:
            continue

        status = d.get("status", "").lower()
        valid_until = d.get("valid_until")

        if isinstance(valid_until, str):
            try:
                valid_until = datetime.fromisoformat(valid_until)
            except Exception:
                valid_until = None

        if status in ("approved", "active"):
            if valid_until is None or valid_until > now:
                active.append(d)

    return active


def compute_effective_deadline(
    deadline: Optional[dict],
    decisions: List[dict]
) -> Optional[datetime]:
    """
    Effective deadline = max(original_deadline, decision.valid_until)
    """

    base = None
    if deadline:
        base = deadline.get("due_at")
        if isinstance(base, str):
            try:
                base = datetime.fromisoformat(base)
            except Exception:
                base = None

    candidates = []
    if base:
        candidates.append(base)

    for d in decisions:
        valid_until = d.get("valid_until")
        if isinstance(valid_until, str):
            try:
                valid_until = datetime.fromisoformat(valid_until)
            except Exception:
                valid_until = None
        if valid_until:
            candidates.append(valid_until)

    if not candidates:
        return None

    return max(candidates)

def select_context(
    student_id: str,
    detected_intent: Optional[dict] = None,
) -> Dict[str, Any]:
    """
    Returns the minimal graph context needed for the detected intent.

    detected_intent shape (from extractor):
    {
        "label": "deadline_help",
        "confidence": 0.92,
        "entities": {
            "assignment_name": "...",
            "assignment_id": "...",   # resolved by extractor if found
            "goal_id": "...",
            "date_reference_normalized": "...",
        }
    }
    """

    student = get_student(student_id)
    screen = get_current_screen(student_id)

    intent = detected_intent or {}
    label = intent.get("label", "general_question").lower()
    entities = intent.get("entities") or {}

    assignment = None
    deadline = None
    decisions = []
    effective_deadline = None
    goals = []
    courses = []

    # ------------------------------------------------------------------
    # deadline_help
    # Student is asking when something is due or if they missed it.
    # Need: assignment, its deadline, any active extensions.
    # ------------------------------------------------------------------
    if label == "deadline_help":
        assignment = _resolve_assignment(student_id, entities, screen)
        if assignment:
            deadline = get_deadline(assignment["assignment_id"])
            decisions = _safe_filter_active_decisions(
                get_active_decisions(student_id, assignment["assignment_id"])
            )
            effective_deadline = compute_effective_deadline(deadline, decisions)

    # ------------------------------------------------------------------
    # extension_request
    # Student wants more time. Need assignment + deadline to show current
    # state, plus full decision history so AI/mentor can see prior grants.
    # ------------------------------------------------------------------
    elif label == "extension_request":
        assignment = _resolve_assignment(student_id, entities, screen)
        if assignment:
            deadline = get_deadline(assignment["assignment_id"])
        decisions = _get_all_student_decisions(student_id)   # all, not just active
        effective_deadline = compute_effective_deadline(
            deadline,
            _safe_filter_active_decisions(decisions),
        )

    # ------------------------------------------------------------------
    # assignment_help
    # Student needs help with content/doing the assignment.
    # Need: assignment details + deadline (so AI knows urgency).
    # ------------------------------------------------------------------
    elif label == "assignment_help":
        assignment = _resolve_assignment(student_id, entities, screen)
        if assignment:
            deadline = get_deadline(assignment["assignment_id"])

    # ------------------------------------------------------------------
    # progress_query
    # Student asking about overall progress. Goals + courses is enough.
    # ------------------------------------------------------------------
    elif label == "progress_query":
        goals = get_student_goals(student_id)
        courses = _get_student_courses(student_id)

    # ------------------------------------------------------------------
    # general_question (or unrecognised label)
    # Attach goals so the AI has something to orient on.
    # ------------------------------------------------------------------
    else:
        goals = get_student_goals(student_id)

    return {
        "student": student,
        "screen": screen,
        "intent": intent,
        "assignment": assignment,
        "deadline": deadline,
        "decisions": decisions,
        "effective_deadline": effective_deadline,
        "goals": goals,
        "courses": courses,
    }

# Quick test
if __name__ == "__main__":
    from src.graph.seed import build_seed_graph

    build_seed_graph()

    ctx = select_context("s1")  # <-- use student_id here
    print("Context selected:")

    import pprint
    pprint.pprint(ctx)