import os
import requests
import logging

API_URL = os.getenv("API_URL", "http://backend:8000/api/v1")
API_KEY = os.getenv("NETGUARD_API_KEY")

def post_agent_log(agent_name: str, level: str, message: str):
    """Fire-and-forget agent log to backend. Never raises."""
    if not API_KEY:
        return
    try:
        requests.post(
            f"{API_URL}/monitoring/agent-logs",
            json={"agent_name": agent_name, "level": level, "message": message},
            headers={"X-API-Key": API_KEY},
            timeout=5
        )
    except Exception:
        pass
