from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from src.core.database import get_db
from src.repositories.db_repositories import DbRepository
from src.integrations.whatsapp_provider import get_whatsapp_provider

router = APIRouter()

@router.get("/channels/status")
def get_channels_status(db: Session = Depends(get_db)):
    """
    Lists all active communication channels and queries their provider's connection status.
    """
    channels = DbRepository.list_active_channels(db)
    results = []
    
    for ch in channels:
        connection_status = "unknown"
        details = {}
        try:
            provider = get_whatsapp_provider(ch.provider)
            state_res = provider.get_connection_state(ch)
            if state_res.get("success"):
                data = state_res.get("data", {})
                # Evolution API returns { "instance": { "state": "open", "status": "CONNECTED" } } or similar
                # Meta API returns a static mock connected state
                connection_status = "CONNECTED" if "open" in str(data).lower() or "connected" in str(data).lower() else "DISCONNECTED"
                details = data
            else:
                connection_status = "DISCONNECTED"
                details = {"error": state_res.get("error")}
        except Exception as e:
            connection_status = "error"
            details = {"exception": str(e)}

        results.append({
            "id": ch.id,
            "tenant_id": ch.tenant_id,
            "name": ch.name,
            "provider": ch.provider,
            "instance_id": ch.provider_instance_id,
            "status": ch.status,
            "connection": connection_status,
            "details": details
        })
        
    return results
