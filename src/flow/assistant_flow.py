
# Flow:

# input
#  → detect intent
#  → retrieve context
#  → build prompt
#  → call LLM
#  → return answer

# src/flow/assistant_flow.py

from src.retrieval.extractor import extract_intent_entities_and_update
from src.retrieval.context_selector import select_context
from src.llm.prompt_builder import build_full_prompt
from src.llm.client import generate
from src.graph.seed import build_seed_graph


# later you can replace with real classifier
def detect_intent(user_message: str) -> str:
    
    text = user_message.lower()

    if "deadline" in text or "submit" in text or "time" in text:
        return {
            "label": "deadline_help",
            "confidence": 1.0,
            "intent_id": "i1",
        }

    return {
        "label": "general_help",
        "confidence": 1.0,
        "intent_id": "i0",
    }



def run_assistant(user_id: str, user_message: str) -> str:
    nlu_result = extract_intent_entities_and_update(
        user_id=user_id,
        conversation_id="c1",
        user_message=user_message
    )

    intent = {
        "label": nlu_result["extraction"]["intent"],
        "confidence": nlu_result["extraction"]["confidence"],
    }

    context = select_context(
        student_id=user_id,
        detected_intent=intent
    )
    prompt = build_full_prompt(context, user_message)
    # print("prompt:- ", prompt)
    answer = generate(prompt)
    return answer


# demo runner
if __name__ == "__main__":
    uid = "s1"
    msg = "Can I submit this assignment tomorrow?"

    print("USER:", msg)
    reply = run_assistant(uid, msg)
    print("ASSISTANT:", reply)
