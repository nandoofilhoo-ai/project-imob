from src.services.chatwoot_client import ChatwootClient
from src.models.db_models import Lead, Conversation, Handoff
from src.repositories.db_repositories import DbRepository

def test_chatwoot_client_mock_mode():
    client = ChatwootClient()
    assert client.is_mock is True
    
    # 1. Contact creation mock returns mock ID
    contact_id = client.find_or_create_contact("5511999999999", "John Test")
    assert contact_id is not None
    assert isinstance(contact_id, int)
    
    # 2. Conversation creation mock returns mock ID
    conv_id = client.find_or_create_conversation(contact_id, inbox_id=1)
    assert conv_id is not None
    assert isinstance(conv_id, int)
    
    # 3. Message synchronization mock
    msg_in_id = client.create_incoming_message(conv_id, "Inbound test text")
    assert msg_in_id is not None
    
    msg_out_id = client.create_outgoing_message(conv_id, "Outbound reply text")
    assert msg_out_id is not None
    
    note_id = client.add_private_note(conv_id, "This is a private note")
    assert note_id is not None
    
    label_success = client.add_label(conv_id, "sdr-handoff")
    assert label_success is True


def test_handoff_integration_logic(client, db_session):
    # Triggers handoff through webhook text
    payload = {
        "event": "messages.upsert",
        "instance": "ImobiliariaAlfa",
        "data": {
            "key": {
                "remoteJid": "5511888889999@s.whatsapp.net",
                "fromMe": False,
                "id": "HND1"
            },
            "pushName": "Alice Handoff",
            "message": {
                "conversation": "Quero falar com um corretor humano por favor"
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
        assert data["handoff_triggered"] is True
        assert "corretor" in data["reply_text"].lower()
        
        # Verify db states
        lead = db_session.query(Lead).filter(Lead.number == "5511888889999").first()
        assert lead.status == "handoff"
        
        conversation = db_session.query(Conversation).filter(Conversation.lead_id == lead.id).first()
        assert conversation.status == "handoff"
        
        # Verify handoff entry was created
        handoff = db_session.query(Handoff).filter(Handoff.lead_id == lead.id).first()
        assert handoff is not None
        assert handoff.reason == "human_requested_or_complaint"
    finally:
        src.integrations.whatsapp_provider.EvolutionProvider.send_text = original_send
