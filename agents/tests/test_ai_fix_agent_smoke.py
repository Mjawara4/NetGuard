import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_ai_fix_agent_imports():
    import ai_fix_agent

    assert callable(ai_fix_agent.ask_llm)
    assert callable(ai_fix_agent.run_agent)


if __name__ == "__main__":
    test_ai_fix_agent_imports()
    print("ai_fix_agent smoke test passed")
