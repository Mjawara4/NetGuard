import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_ai_analytics_imports():
    from app.routers import ai_analytics

    assert hasattr(ai_analytics, "router")


if __name__ == "__main__":
    test_ai_analytics_imports()
    print("ai_analytics smoke test passed")
