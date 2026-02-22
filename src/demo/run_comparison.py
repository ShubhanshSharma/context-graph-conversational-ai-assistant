
# This will:

# user_input = "Can I submit tomorrow?"

# print("BASELINE")
# run naive

# print("WITH GRAPH")
# run flow

# print("Retrieved context")


# src/demo/run_comparison.py

"""
Comparison runner

This script compares:
1️⃣ Baseline (no context)
2️⃣ Graph-aware assistant (with context graph)

It prints:
- User input
- Baseline output
- Graph-aware output
"""

from src.llm.naive_chat import ask
from src.flow.assistant_flow import run_assistant


def main():
    user_id = "s1"
    user_input = "Can I submit this assignment tomorrow?"

    print("\n" + "=" * 60)
    print("USER INPUT")
    print("=" * 60)
    print(user_input)

    print("\n" + "=" * 60)
    print("BASELINE (No Graph Context)")
    print("=" * 60)
    baseline_response = ask(user_input)
    print(baseline_response)

    print("\n" + "=" * 60)
    print("GRAPH-AWARE ASSISTANT (With Context Graph)")
    print("=" * 60)
    graph_response = run_assistant(user_id=user_id, user_message=user_input)
    print(graph_response)

    print("\n" + "=" * 60)
    print("Done.")
    print("=" * 60)


if __name__ == "__main__":
    main()