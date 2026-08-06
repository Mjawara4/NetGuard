import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_reporter_agent_imports():
    import reporter_agent

    assert callable(reporter_agent.generate_summary_llm)
    assert callable(reporter_agent.run_agent)


if __name__ == "__main__":
    test_reporter_agent_imports()
    print("reporter_agent smoke test passed")
