from sqlalchemy.orm import Session
from src.services.qualification_service import QualificationService
from src.services.rule_engine import RuleEngine
from src.models.db_models import Lead, Conversation, LeadQualification
from src.repositories.db_repositories import DbRepository
from src.services.llm_adapter import get_llm_provider, PromptBuilder, finalize_reply

def test_qualification_heuristics(db_session):
    # Create test lead
    lead = DbRepository.create_lead(db_session, tenant_id=1, number="5511888888888", name="Mary")
    
    # 1. Test objective and property type heuristics
    text_1 = "Gostaria de alugar um apartamento"
    updates = QualificationService.process_incoming_message(db_session, lead.id, text_1)
    
    qualification = DbSession_get_qualification(db_session, lead.id)
    assert qualification.objetivo == "aluguel"
    assert qualification.tipo_imovel == "apartamento"
    
    # 2. Test neighborhood extraction and pricing heuristics
    text_2 = "Estou procurando no Jardim Paulista, com preço máximo de 4000 reais"
    updates = QualificationService.process_incoming_message(db_session, lead.id, text_2)
    
    qualification = DbSession_get_qualification(db_session, lead.id)
    assert qualification.bairro == "Jardim Paulista"
    assert qualification.faixa_preco is not None
    assert "4000" in qualification.faixa_preco

    # Since objetivo (aluguel), tipo_imovel (apartamento), bairro (Jardim Paulista) and price are filled:
    assert qualification.pronto_para_handoff is True


def test_rule_engine_decisions(db_session):
    lead = DbRepository.create_lead(db_session, tenant_id=1, number="5511888888888", name="Mary")
    conversation = DbRepository.create_conversation(db_session, tenant_id=1, lead_id=lead.id, channel_config_id=1)
    qualification = DbRepository.get_qualification(db_session, lead.id)
    
    # Check rule evaluation when qualification is completely empty
    decision = RuleEngine.evaluate(db_session, lead, conversation, qualification, "Oi")
    assert decision["should_respond"] is True
    assert decision["action"] == "bot_reply"
    assert decision["next_missing_field"] == "objetivo"
    assert "comprar ou alugar" in decision["suggested_reply"]

    # Check rule evaluation when human broker is requested
    decision_human = RuleEngine.evaluate(db_session, lead, conversation, qualification, "Quero falar com um corretor humano por favor")
    assert decision_human["should_respond"] is True
    assert decision_human["action"] == "handoff"
    assert decision_human["reason"] == "human_requested_or_complaint"
    
    # Check rule evaluation under takeover mode
    lead.status = "takeover"
    db_session.commit()
    decision_takeover = RuleEngine.evaluate(db_session, lead, conversation, qualification, "Qual o preço?")
    assert decision_takeover["should_respond"] is False
    assert decision_takeover["action"] == "none"


def test_orchestrator_mock_mode(client, db_session):
    # Test via Webhook to invoke full orchestrator route
    payload = {
        "event": "messages.upsert",
        "instance": "ImobiliariaAlfa",
        "data": {
            "key": {
                "remoteJid": "5511777777777@s.whatsapp.net",
                "fromMe": False,
                "id": "XYZ123"
            },
            "pushName": "Bob",
            "message": {
                "conversation": "Quero comprar"
            },
            "messageTimestamp": 1670000000
        }
    }
    
    # Mock outbound whatsapp sender
    import src.integrations.whatsapp_provider
    original_send = src.integrations.whatsapp_provider.EvolutionProvider.send_text
    src.integrations.whatsapp_provider.EvolutionProvider.send_text = lambda self, channel_config, number, text: {
        "success": True,
        "data": {}
    }
    
    try:
        response = client.post("/webhook/evolution", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["reply_sent"] is True
        # PromptBuilder asks about property type next
        assert "tipo" in data["reply_text"].lower() or "casa" in data["reply_text"].lower()
    finally:
        src.integrations.whatsapp_provider.EvolutionProvider.send_text = original_send


def test_gemini_provider_mock(monkeypatch):
    import httpx
    
    class MockResponse:
        status_code = 200
        def json(self):
            return {
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "text": "Olá! Você prefere casa ou apartamento?"
                                }
                            ]
                        }
                    }
                ]
            }

    monkeypatch.setattr(httpx.Client, "post", lambda *args, **kwargs: MockResponse())
    
    from src.services.llm_adapter import GeminiProvider
    provider = GeminiProvider(api_key="mock-gemini-key")
    reply = provider.generate_reply(prompt="Oi", system_instruction="Instrucao")
    assert reply == "Olá! Você prefere casa ou apartamento?"


def test_gemini_provider_joins_multiple_text_parts(monkeypatch):
    import httpx

    class MockResponse:
        status_code = 200
        def json(self):
            return {
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {"text": "Olá! Que ótimo que você quer comprar uma casa. "},
                                {"text": "E em qual bairro ou região você tem preferência?"}
                            ]
                        }
                    }
                ]
            }

    monkeypatch.setattr(httpx.Client, "post", lambda *args, **kwargs: MockResponse())

    from src.services.llm_adapter import GeminiProvider
    provider = GeminiProvider(api_key="mock-gemini-key")
    reply = provider.generate_reply(prompt="Oi", system_instruction="Instrucao")
    assert reply == "Olá! Que ótimo que você quer comprar uma casa. E em qual bairro ou região você tem preferência?"


def test_finalize_reply_recovers_truncated_generation():
    reply = finalize_reply(
        "Olá! Que ótimo que",
        "E em qual bairro ou região você tem preferência?"
    )
    assert reply == "Entendi! E em qual bairro ou região você tem preferência?"


def test_finalize_reply_recovers_incomplete_sentence_even_when_longer():
    reply = finalize_reply(
        "Olá! Que ótimo que você",
        "E em qual bairro ou região você tem preferência?"
    )
    assert reply == "Entendi! E em qual bairro ou região você tem preferência?"


def test_finalize_reply_appends_missing_question_when_needed():
    reply = finalize_reply(
        "Perfeito, vou te ajudar",
        "E em qual bairro ou região você tem preferência?"
    )
    assert reply == "Perfeito, vou te ajudar. E em qual bairro ou região você tem preferência?"


# Helpers
def DbSession_get_qualification(db: Session, lead_id: int) -> LeadQualification:
    return db.query(LeadQualification).filter(LeadQualification.lead_id == lead_id).first()

