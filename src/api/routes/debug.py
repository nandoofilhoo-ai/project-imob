from fastapi import APIRouter
from typing import List, Dict, Any

router = APIRouter()

# Simple thread-safe-ish memory storage for tracking recent webhook/orchestration events
RECENT_EVENTS: List[Dict[str, Any]] = []

def record_debug_event(event_type: str, data: Any):
    from datetime import datetime
    event = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "event_type": event_type,
        "data": data
    }
    RECENT_EVENTS.append(event)
    # Cap list size to 50
    if len(RECENT_EVENTS) > 50:
        RECENT_EVENTS.pop(0)

@router.get("/debug/recent-events")
def get_recent_events():
    """
    Lists recent events received by the webhooks or processed by the orchestrator.
    """
    return RECENT_EVENTS
