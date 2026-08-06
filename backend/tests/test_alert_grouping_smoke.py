import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_alert_grouping_imports():
    from app.services import alert_grouping

    assert callable(alert_grouping.process_alert_grouping)


if __name__ == "__main__":
    test_alert_grouping_imports()
    print("alert_grouping smoke test passed")
