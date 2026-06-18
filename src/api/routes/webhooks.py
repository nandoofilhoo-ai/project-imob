from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session
from src.core.database import get_db
from src.core.logger import get_logger
from src.repositories.db_repositories import DbRepository
from src.integrations.whatsapp_provider import EvolutionProvider, MetaCloudProvider
from src.services.inbound_orchestrator import InboundOrchestrator
from src.api.routes.debug import record_debug_event

router = APIRouter()
logger = get_logger(__name__)

@router.post("/webhook/evolution")
async def webhook_evolution(request: Request, db: Session = Depends(get_db)):
    """
    Receives Evolution API webhooks, normalizes them, filters them, and forwards to the orchestration service.
    """
    try:
        payload = await request.json()
    except Exception as e:
        logger.error(f"Failed to parse Evolution webhook JSON body: {e}")
        return {"status": "error", "message": "Invalid JSON"}

    logger.info("Received webhook from Evolution API")
    
    # 1. Audit log raw payload
    DbRepository.create_audit_log(db, tenant_id=None, event_type="webhook_raw_evolution", payload=payload)

    # 2. Normalize payload
    provider = EvolutionProvider()
    normalized = provider.normalize_inbound(payload)
    
    if not normalized:
        record_debug_event("webhook_evolution_ignored", {"reason": "normalization_failed", "payload": payload})
        return {"status": "ignored", "reason": "normalization_failed_or_unsupported_event"}

    # 3. Apply MVP filters
    if normalized.is_from_me:
        logger.info(f"Evolution: Ignoring message fromMe for number {normalized.number}")
        record_debug_event("webhook_evolution_ignored", {"reason": "message_from_me", "number": normalized.number})
        return {"status": "ignored", "reason": "message_from_me"}

    if normalized.is_group:
        logger.info(f"Evolution: Ignoring group message for group {normalized.number}")
        record_debug_event("webhook_evolution_ignored", {"reason": "group_message", "number": normalized.number})
        return {"status": "ignored", "reason": "group_message"}

    if not normalized.text or not normalized.text.strip():
        logger.info(f"Evolution: Ignoring message with no text content for number {normalized.number}")
        record_debug_event("webhook_evolution_ignored", {"reason": "no_text_content", "number": normalized.number})
        return {"status": "ignored", "reason": "no_text_content"}

    # 4. Orchestrate
    result = InboundOrchestrator.orchestrate(db, normalized)
    
    # Record debug event
    normalized_summary = {
        "instance_name": normalized.instance_name,
        "number": normalized.number,
        "contact_name": normalized.contact_name,
        "text": normalized.text,
        "timestamp": normalized.timestamp,
    }
    record_debug_event("webhook_evolution_processed", {
        "normalized": normalized_summary,
        "result": result
    })

    return result


@router.post("/webhook/meta")
async def webhook_meta(request: Request, db: Session = Depends(get_db)):
    """
    Receives Meta Cloud API webhooks, normalizes them, filters them, and forwards to the orchestration service.
    """
    # Meta webhook verification challenge
    # Meta sends GET requests with hub.mode, hub.challenge, hub.verify_token for registration verification
    params = request.query_params
    if request.method == "GET" or "hub.challenge" in params:
        challenge = params.get("hub.challenge", "")
        # A simple pass-through response is fine for stub verification
        return Response(content=challenge, media_type="text/plain")

    try:
        payload = await request.json()
    except Exception as e:
        logger.error(f"Failed to parse Meta webhook JSON body: {e}")
        return {"status": "error", "message": "Invalid JSON"}

    logger.info("Received webhook from Meta Cloud API")
    
    # 1. Audit log raw payload
    DbRepository.create_audit_log(db, tenant_id=None, event_type="webhook_raw_meta", payload=payload)

    # 2. Normalize payload
    provider = MetaCloudProvider()
    normalized = provider.normalize_inbound(payload)
    
    if not normalized:
        record_debug_event("webhook_meta_ignored", {"reason": "normalization_failed", "payload": payload})
        return {"status": "ignored", "reason": "normalization_failed_or_unsupported_event"}

    # 3. Apply MVP filters
    if normalized.is_from_me:
        logger.info(f"Meta: Ignoring message fromMe for number {normalized.number}")
        return {"status": "ignored", "reason": "message_from_me"}

    if normalized.is_group:
        logger.info(f"Meta: Ignoring group message for group {normalized.number}")
        return {"status": "ignored", "reason": "group_message"}

    if not normalized.text or not normalized.text.strip():
        logger.info(f"Meta: Ignoring message with no text content for number {normalized.number}")
        return {"status": "ignored", "reason": "no_text_content"}

    # 4. Orchestrate
    result = InboundOrchestrator.orchestrate(db, normalized)

    # Record debug event
    normalized_summary = {
        "instance_name": normalized.instance_name,
        "number": normalized.number,
        "contact_name": normalized.contact_name,
        "text": normalized.text,
        "timestamp": normalized.timestamp,
    }
    record_debug_event("webhook_meta_processed", {
        "normalized": normalized_summary,
        "result": result
    })

    return result
