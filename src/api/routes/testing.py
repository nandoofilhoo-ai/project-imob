from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from src.core.database import get_db
from src.core.logger import get_logger
from src.schemas.schemas import TestSendRequest, TestGenerateRequest
from src.repositories.db_repositories import DbRepository
from src.integrations.whatsapp_provider import get_whatsapp_provider
from src.services.llm_adapter import PromptBuilder, get_llm_provider, finalize_reply
from src.services.rule_engine import RuleEngine
from src.services.qualification_service import QualificationService

router = APIRouter()
logger = get_logger(__name__)

@router.post("/test/send/evolution")
def test_send_evolution(payload: TestSendRequest, db: Session = Depends(get_db)):
    """
    Sends a test message using the configured Evolution provider channel.
    """
    channel = None
    if payload.instance_name:
        channel = DbRepository.get_channel_by_instance(db, "evolution", payload.instance_name)
    else:
        from src.models.db_models import ChannelConfig
        channel = db.query(ChannelConfig).filter(ChannelConfig.provider == "evolution").first()

    if not channel:
        raise HTTPException(status_code=404, detail="No active Evolution channel config found in DB.")

    provider = get_whatsapp_provider("evolution")
    result = provider.send_text(
        channel_config=channel,
        number=payload.number,
        text=payload.text
    )
    
    if not result.get("success"):
        raise HTTPException(status_code=502, detail=f"Evolution delivery failed: {result.get('error') or result.get('data')}")

    return {
        "status": "success",
        "provider": "evolution",
        "channel_id": channel.id,
        "recipient": payload.number,
        "response": result.get("data")
    }


@router.post("/test/generate")
def test_generate(payload: TestGenerateRequest, db: Session = Depends(get_db)):
    """
    Runs the LLM prompt and reply pipeline without sending anything or triggering Chatwoot.
    Useful for testing the brain and RuleEngine.
    """
    tenant = DbRepository.get_tenant(db, payload.tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    tenant_config = DbRepository.get_tenant_config(db, payload.tenant_id)

    # 1. Look up/create Lead
    lead = DbRepository.get_or_create_lead(db, payload.tenant_id, payload.number, "Test Lead")

    # 2. Update qualification heuristics
    QualificationService.process_incoming_message(db, lead.id, payload.text)
    qualification = DbRepository.get_qualification(db, lead.id)

    # 3. Evaluate Rule Engine
    from src.models.db_models import Conversation
    conversation = db.query(Conversation).filter(
        Conversation.lead_id == lead.id
    ).order_by(Conversation.created_at.desc()).first()
    
    if not conversation:
        from src.models.db_models import ChannelConfig
        channel = db.query(ChannelConfig).first()
        channel_id = channel.id if channel else 1
        conversation = Conversation(id=0, tenant_id=payload.tenant_id, lead_id=lead.id, channel_config_id=channel_id, status="open")

    decision = RuleEngine.evaluate(
        db=db,
        lead=lead,
        conversation=conversation,
        qualification=qualification,
        message_text=payload.text
    )

    reply_text = ""
    prompt = ""

    if decision["should_respond"]:
        if decision["action"] == "handoff":
            reply_text = decision["suggested_reply"] or "Transferindo para corretor..."
        elif decision["action"] == "bot_reply":
            prompt = PromptBuilder.build(
                tenant=tenant,
                tenant_config=tenant_config,
                qualification=qualification,
                last_message=payload.text,
                suggested_question=decision["suggested_reply"]
            )
            llm_provider = get_llm_provider(suggested_question=decision["suggested_reply"])
            raw_reply = llm_provider.generate_reply(prompt)
            reply_text = finalize_reply(raw_reply, decision["suggested_reply"])

    return {
        "decision": decision,
        "qualification_state": {
            "objetivo": qualification.objetivo,
            "tipo_imovel": qualification.tipo_imovel,
            "bairro": qualification.bairro,
            "faixa_preco": qualification.faixa_preco,
            "urgencia": qualification.urgencia,
            "pronto_para_handoff": qualification.pronto_para_handoff
        },
        "prompt_evaluated": prompt,
        "reply": reply_text
    }
