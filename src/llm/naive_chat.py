# src/baseline/naive_chat.py

from src.llm.client import generate


def ask(user_message: str) -> str:
    """
    Baseline system.
    Sends only user input.
    No memory, no graph, no intelligence.
    """
    return generate(user_message)


if __name__ == "__main__":
    msg = "Can I submit this assignment tomorrow?"
    print("USER:", msg)
    print("BASELINE:", ask(msg))
