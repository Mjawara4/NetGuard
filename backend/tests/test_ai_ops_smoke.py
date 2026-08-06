import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_ai_ops_imports():
    from app.routers import ai_ops

    assert callable(ai_ops.ask_llm_intent)
    assert callable(ai_ops.explain_result)


if __name__ == "__main__":
    test_ai_ops_imports()
    print("ai_ops smoke test passed")
