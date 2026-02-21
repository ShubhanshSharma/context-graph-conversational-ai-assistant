# src/retrieval/context_selector.py
from datetime import datetime
from typing import Optional, Dict, Any, List

from src.graph.queries import (
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
    detected_intent: Optional[dict] = None
) -> Dict[str, Any]:
    """
    Returns:
    {
      student,
      assignment,
      deadline,
      decisions,
      screen,
      intent,
      effective_deadline
    }
    """

    # 1. Basic facts
    student = get_student(student_id)
    screen = get_current_screen(student_id)
    intent = detected_intent or get_last_intent(student_id)

    assignment = None

    def _assignment_from_goals(goals):
        for g in goals:
            goal_id = g.get("goal_id")
            if goal_id:
                a = get_assignment_for_goal(goal_id)
                if a:
                    return a
        return None

    # 2. Try screen context first
    if screen and screen.get("name", "").lower().startswith("assignment"):
        goals = get_student_goals(student_id)
        assignment = _assignment_from_goals(goals)

    # 3. Fallback: first goal
    if assignment is None:
        goals = get_student_goals(student_id)
        assignment = _assignment_from_goals(goals)

    # 4. Deadline
    deadline = None
    if assignment:
        deadline = get_deadline(assignment.get("assignment_id"))

    # 5. Decisions
    decisions = []
    if assignment:
        raw = get_active_decisions(
            student_id,
            assignment.get("assignment_id")
        )
        decisions = _safe_filter_active_decisions(raw)

    # 6. Effective deadline
    effective_deadline = compute_effective_deadline(deadline, decisions)

    return {
        "student": student,
        "screen": screen,
        "intent": intent,
        "assignment": assignment,
        "deadline": deadline,
        "decisions": decisions,
        "effective_deadline": effective_deadline,
    }


# Quick test
if __name__ == "__main__":
    from src.graph.seed import build_seed_graph

    build_seed_graph()

    ctx = select_context("s1")  # <-- use student_id here
    print("Context selected:")

    import pprint
    pprint.pprint(ctx)