from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from src.models.db_models import Lead, Conversation, LeadQualification
from src.repositories.db_repositories import DbRepository
from src.core.logger import get_logger

logger = get_logger(__name__)

class RuleEngine:
    @staticmethod
    def evaluate(
        db: Session,
        lead: Lead,
        conversation: Conversation,
        qualification: LeadQualification,
        message_text: str
    ) -> Dict[str, Any]:
        """
        Evaluates rules to make a routing and response decision.
        Returns:
            {
                "should_respond": bool,
                "action": str,         # 'bot_reply', 'handoff', 'none'
                "reason": str,
                "suggested_reply": Optional[str],
                "next_missing_field": Optional[str]
            }
        """
        text_lower = message_text.lower()

        # Rule 1: Takeover check
        # If the lead or conversation is marked as 'takeover' or 'agent' handled, the bot must keep quiet.
        if lead.status == "takeover" or conversation.status == "takeover":
            logger.info(f"RuleEngine: Takeover active for lead {lead.id} / conversation {conversation.id}. Bot will not respond.")
            return {
                "should_respond": False,
                "action": "none",
                "reason": "takeover_active",
                "suggested_reply": None,
                "next_missing_field": None
            }

        # Rule 2: Explicit handoff/human keywords, visits, or complaints
        handoff_keywords = [
            "corretor", "humano", "atendente", "falar com pessoa", "pessoa física",
            "falar com alguém", "falar com alguem", "atendimento humano", "ligar",
            "telefonar", "visita", "visitar", "agendar", "gerente", "reclamação", 
            "reclamacao", "denúncia", "denuncia", "ruim", "problema", "suporte"
        ]
        if any(keyword in text_lower for keyword in handoff_keywords):
            logger.info(f"RuleEngine: Handoff triggered by keyword in message: '{message_text}'")
            return {
                "should_respond": True,
                "action": "handoff",
                "reason": "human_requested_or_complaint",
                "suggested_reply": "Entendido. Vou te transferir agora para um de nossos corretores humanos para te ajudar da melhor forma. Um momento, por favor!",
                "next_missing_field": None
            }

        # Rule 3: Check if lead qualification is complete and marked for handoff
        if qualification.pronto_para_handoff:
            logger.info(f"RuleEngine: Handoff triggered because qualification is complete for lead {lead.id}")
            return {
                "should_respond": True,
                "action": "handoff",
                "reason": "qualification_completed",
                "suggested_reply": "Perfeito! Já entendi o que você procura. Vou transferir o nosso chat para um corretor especialista para te passar as opções de imóveis disponíveis. Só um instante!",
                "next_missing_field": None
            }

        # Rule 4: Identify the next missing qualification field
        next_missing_field = None
        suggested_question = None

        if not qualification.objetivo:
            next_missing_field = "objetivo"
            suggested_question = "Você está buscando comprar ou alugar um imóvel?"
        elif not qualification.tipo_imovel:
            next_missing_field = "tipo_imovel"
            suggested_question = "Legal! E qual tipo de imóvel você prefere? (ex: casa, apartamento, terreno)"
        elif not qualification.bairro:
            next_missing_field = "bairro"
            suggested_question = "E em qual bairro ou região você tem preferência?"
        elif not qualification.faixa_preco:
            next_missing_field = "faixa_preco"
            suggested_question = "Perfeito. E qual seria a sua faixa de preço ou orçamento máximo planejado?"

        # If we have a missing field, we can let the LLM generate a natural response using this prompt context,
        # or fall back to this suggested question if LLM is disabled/mocked.
        return {
            "should_respond": True,
            "action": "bot_reply",
            "reason": "continue_qualification",
            "suggested_reply": suggested_question,
            "next_missing_field": next_missing_field
        }
