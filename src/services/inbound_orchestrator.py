from sqlalchemy.orm import Session
from typing import Dict, Any, Optional
from src.core.logger import get_logger
from src.integrations.whatsapp_provider import NormalizedMessage, get_whatsapp_provider
from src.repositories.db_repositories import DbRepository
from src.services.qualification_service import QualificationService
from src.services.rule_engine import RuleEngine
from src.services.llm_adapter import PromptBuilder, get_llm_provider, finalize_reply
from src.services.chatwoot_client import ChatwootClient

logger = get_logger(__name__)

class InboundOrchestrator:
    @classmethod
    def orchestrate(cls, db: Session, normalized_msg: NormalizedMessage) -> Dict[str, Any]:
        """
        Coordinates the entire flow:
        1. Identifies channel & tenant
        2. Retrieves or creates Lead & Conversation
        3. Persists incoming message
        4. Updates lead qualification parameters
        5. Evaluates rules (takeover, handoff, missing info)
        6. Interacts with Chatwoot for contact/conversation sync
        7. Generates & sends reply if needed
        8. Audit logs the entire transaction
        """
        logger.info(f"Orchestrator: Processing message from {normalized_msg.number} to instance '{normalized_msg.instance_name}'")
        
        # 1. Look up active channel configuration
        # For Evolution, instance_name matches provider_instance_id
        # For Meta, phone_number_id matches provider_instance_id
        channel_config = DbRepository.get_channel_by_instance(db, "evolution", normalized_msg.instance_name)
        if not channel_config:
            # Check Meta too
            channel_config = DbRepository.get_channel_by_instance(db, "meta", normalized_msg.instance_name)

            
        if not channel_config:
            # Fallback query using generic filter to be absolutely safe
            from src.models.db_models import ChannelConfig
            channel_config = db.query(ChannelConfig).filter(
                ChannelConfig.provider_instance_id == normalized_msg.instance_name
            ).first()

        if not channel_config:
            logger.error(f"Orchestrator: No active channel found for instance_name: '{normalized_msg.instance_name}'")
            return {"status": "ignored", "reason": "channel_not_found"}

        tenant_id = channel_config.tenant_id
        tenant = DbRepository.get_tenant(db, tenant_id)
        if not tenant:
            logger.error(f"Orchestrator: Tenant not found for id: {tenant_id}")
            return {"status": "ignored", "reason": "tenant_not_found"}

        # 2. Get or create Lead
        lead = DbRepository.get_or_create_lead(
            db=db,
            tenant_id=tenant_id,
            number=normalized_msg.number,
            name=normalized_msg.contact_name
        )

        # 3. Get or create active Conversation
        conversation = DbRepository.get_or_create_conversation(
            db=db,
            tenant_id=tenant_id,
            lead_id=lead.id,
            channel_config_id=channel_config.id
        )

        # 4. Save incoming message in local DB
        inbound_db_msg = DbRepository.create_message(
            db=db,
            conversation_id=conversation.id,
            sender_type="lead",
            text=normalized_msg.text or "",
            payload=normalized_msg.raw_payload
        )

        # 5. Process lead qualification heuristic updates
        if normalized_msg.text:
            QualificationService.process_incoming_message(db, lead.id, normalized_msg.text)
        
        # Fetch fresh qualification state
        qualification = DbRepository.get_qualification(db, lead.id)

        # 6. Evaluate Rule Engine
        decision = RuleEngine.evaluate(
            db=db,
            lead=lead,
            conversation=conversation,
            qualification=qualification,
            message_text=normalized_msg.text or ""
        )
        
        reply_sent = False
        reply_text = None
        handoff_triggered = False

        # 7. Sincronização Chatwoot (Inbound Phase)
        chatwoot_client = ChatwootClient()
        chatwoot_conv_id = None
        
        try:
            # Identify or create Chatwoot contact
            cw_contact_id = chatwoot_client.find_or_create_contact(lead.number, lead.name)
            if cw_contact_id and lead.chatwoot_contact_id != cw_contact_id:
                lead.chatwoot_contact_id = cw_contact_id
                db.commit()

            # Identify or create Chatwoot conversation
            # Fallback to account ID or 1 for inbox if channel lacks configuration
            inbox_id = channel_config.chatwoot_inbox_id or chatwoot_client.account_id or 1
            if cw_contact_id:
                chatwoot_conv_id = chatwoot_client.find_or_create_conversation(cw_contact_id, inbox_id)
                if chatwoot_conv_id and conversation.chatwoot_conversation_id != chatwoot_conv_id:
                    conversation.chatwoot_conversation_id = chatwoot_conv_id
                    db.commit()

            # Record incoming message in Chatwoot
            if chatwoot_conv_id and normalized_msg.text:
                cw_msg_id = chatwoot_client.create_incoming_message(chatwoot_conv_id, normalized_msg.text)
                if cw_msg_id:
                    inbound_db_msg.chatwoot_message_id = cw_msg_id
                    db.commit()
        except Exception as ex:
            logger.error(f"Orchestrator: Failed during Chatwoot inbound sync: {ex}")

        # 8. Act on Decision
        if decision["should_respond"]:
            action = decision["action"]
            
            if action == "handoff":
                handoff_triggered = True
                # Record handoff event locally
                DbRepository.create_handoff(
                    db=db,
                    lead_id=lead.id,
                    conversation_id=conversation.id,
                    reason=decision["reason"],
                    details=f"Última mensagem: {normalized_msg.text}\nQualificação: {qualification.resumo_atual}"
                )
                
                reply_text = decision["suggested_reply"] or "Vou chamar um atendente humano para falar com você. Só um instante."
                
                # Try to notify Chatwoot via private note and tagging
                try:
                    if chatwoot_conv_id:
                        chatwoot_client.add_private_note(
                            chatwoot_conv_id,
                            f"⚠️ [BOT HANDOFF] Transferido para atendimento humano.\nMotivo: {decision['reason']}\nResumo Qualificação:\n{qualification.resumo_atual}"
                        )
                        chatwoot_client.add_label(chatwoot_conv_id, "sdr-handoff")
                except Exception as ex:
                    logger.error(f"Orchestrator: Chatwoot handoff tagging failed: {ex}")

            elif action == "bot_reply":
                # Generate Bot reply via PromptBuilder + LLM Provider
                prompt = PromptBuilder.build(
                    tenant=tenant,
                    tenant_config=DbRepository.get_tenant_config(db, tenant_id),
                    qualification=qualification,
                    last_message=normalized_msg.text or "",
                    suggested_question=decision["suggested_reply"]
                )
                
                try:
                    llm_provider = get_llm_provider(suggested_question=decision["suggested_reply"])
                    raw_reply = llm_provider.generate_reply(prompt)
                    reply_text = finalize_reply(raw_reply, decision["suggested_reply"])
                except Exception as ex:
                    logger.error(f"Orchestrator: LLM failed to generate reply: {ex}. Using fallback.")
                    reply_text = finalize_reply(None, decision["suggested_reply"])

            # Send WhatsApp message via provider
            if reply_text:
                whatsapp_provider = get_whatsapp_provider(channel_config.provider)
                send_result = whatsapp_provider.send_text(
                    channel_config=channel_config,
                    number=lead.number,
                    text=reply_text
                )
                
                if send_result.get("success"):
                    reply_sent = True
                    # Persist Outbound message
                    outbound_db_msg = DbRepository.create_message(
                        db=db,
                        conversation_id=conversation.id,
                        sender_type="bot",
                        text=reply_text
                    )
                    
                    # Sync Outbound message to Chatwoot
                    try:
                        if chatwoot_conv_id:
                            cw_out_msg_id = chatwoot_client.create_outgoing_message(chatwoot_conv_id, reply_text)
                            if cw_out_msg_id:
                                outbound_db_msg.chatwoot_message_id = cw_out_msg_id
                                db.commit()
                    except Exception as ex:
                        logger.error(f"Orchestrator: Failed to sync outbound bot message to Chatwoot: {ex}")
                else:
                    logger.error(f"Orchestrator: Failed to send reply via WhatsApp: {send_result.get('error')}")

        # 9. Log decision in AuditLogs
        audit_payload = {
            "lead_id": lead.id,
            "message_received": normalized_msg.text,
            "decision": decision,
            "reply_text": reply_text,
            "reply_sent": reply_sent,
            "handoff_triggered": handoff_triggered,
            "qualification_state": {
                "objetivo": qualification.objetivo,
                "tipo_imovel": qualification.tipo_imovel,
                "bairro": qualification.bairro,
                "faixa_preco": qualification.faixa_preco,
                "urgencia": qualification.urgencia,
                "pronto_para_handoff": qualification.pronto_para_handoff
            }
        }
        DbRepository.create_audit_log(db, tenant_id, "orchestration_decision", audit_payload)

        return {
            "status": "success",
            "decision": decision,
            "reply_sent": reply_sent,
            "reply_text": reply_text,
            "handoff_triggered": handoff_triggered
        }
