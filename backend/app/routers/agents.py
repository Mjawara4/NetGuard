from fastapi import APIRouter, Depends, HTTPException
import redis
import os
from pydantic import BaseModel

router = APIRouter()

# Simple Redis connection
# In prod, use async redis or dependency injection
redis_client = redis.Redis(host=os.getenv("REDIS_HOST", "redis"), port=6379, db=0)

class TriggerRequest(BaseModel):
    agent_name: str

@router.post("/trigger")
def trigger_agent(request: TriggerRequest):
    """
    Triggers an agent to run immediately via Redis Pub/Sub.
    Agent Names: 'monitor', 'diagnoser', 'fix'
    """
    channel = f"agent_trigger:{request.agent_name}"
    try:
        redis_client.publish(channel, "run_now")
        return {"status": "success", "message": f"Trigger signal sent to {request.agent_name}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
