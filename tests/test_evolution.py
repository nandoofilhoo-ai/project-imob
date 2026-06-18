from src.integrations.whatsapp_provider import EvolutionProvider
from src.models.db_models import AuditLog, Message, Lead

def test_evolution_payload_normalization():
    provider = EvolutionProvider()
    
    # Typical Evolution messages.upsert payload
    payload = {
        "event": "messages.upsert",
        "instance": "ImobiliariaAlfa",
        "data": {
            "key": {
                "remoteJid": "5511999999999@s.whatsapp.net",
                "fromMe": False,
                "id": "XYZ"
            },
            "pushName": "John Doe",
            "message": {
                "conversation": "Olá, estou buscando comprar um apartamento"
            },
            "messageTimestamp": 1670000000
        }
    }
    
    normalized = provider.normalize_inbound(payload)
    
    assert normalized is not None
    assert normalized.instance_name == "ImobiliariaAlfa"
    assert normalized.number == "5511999999999"
    assert normalized.contact_name == "John Doe"
    assert normalized.text == "Olá, estou buscando comprar um apartamento"
    assert normalized.is_from_me is False
    assert normalized.is_group is False


def test_webhook_evolution_endpoint(client, db_session):
    payload = {
        "event": "messages.upsert",
        "instance": "ImobiliariaAlfa",
        "data": {
            "key": {
                "remoteJid": "5511999999999@s.whatsapp.net",
                "fromMe": False,
                "id": "XYZ"
            },
            "pushName": "John Doe",
            "message": {
                "conversation": "Quero comprar uma casa no Centro"
            },
            "messageTimestamp": 1670000000
        }
    }
    
    response = client.post("/webhook/evolution", json=payload)
    assert response.status_code == 200
    
    data = response.json()
    assert data["status"] == "success"
    
    # Assert database persistence
    # 1. Audit log contains raw
    logs = db_session.query(AuditLog).all()
    assert len(logs) > 0
    assert any(log.event_type == "webhook_raw_evolution" for log in logs)
    
    # 2. Lead was created
    lead = db_session.query(Lead).filter(Lead.number == "5511999999999").first()
    assert lead is not None
    assert lead.name == "John Doe"
    
    # 3. Message was created
    messages = db_session.query(Message).all()
    assert len(messages) > 0
    assert any(m.text == "Quero comprar uma casa no Centro" for m in messages)


def test_test_send_evolution_mock(client):
    # Call the test send route
    payload = {
        "number": "5511999999999",
        "text": "Mensagem de teste",
        "instance_name": "ImobiliariaAlfa"
    }
    
    # Since we need to mock the external httpx.Client.post inside EvolutionProvider.send_text,
    # let's monkeypatch it or test the router behavior
    # We can mock EvolutionProvider.send_text directly
    import src.integrations.whatsapp_provider
    original_send = src.integrations.whatsapp_provider.EvolutionProvider.send_text
    
    src.integrations.whatsapp_provider.EvolutionProvider.send_text = lambda self, channel_config, number, text: {
        "success": True,
        "data": {"status": "success", "message": "delivered"}
    }
    
    try:
        response = client.post("/test/send/evolution", json=payload)
        assert response.status_code == 200
        assert response.json()["status"] == "success"
        assert response.json()["recipient"] == "5511999999999"
    finally:
        src.integrations.whatsapp_provider.EvolutionProvider.send_text = original_send

