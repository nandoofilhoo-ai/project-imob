import httpx
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from src.core.logger import get_logger
from src.models.db_models import ChannelConfig

logger = get_logger(__name__)

class NormalizedMessage:
    def __init__(
        self,
        instance_name: str,
        number: str,
        contact_name: Optional[str],
        text: Optional[str],
        timestamp: int,
        is_from_me: bool,
        is_group: bool,
        raw_payload: Dict[str, Any]
    ):
        self.instance_name = instance_name
        self.number = number
        self.contact_name = contact_name
        self.text = text
        self.timestamp = timestamp
        self.is_from_me = is_from_me
        self.is_group = is_group
        self.raw_payload = raw_payload


class WhatsAppProvider(ABC):
    @abstractmethod
    def provider_name(self) -> str:
        pass

    @abstractmethod
    def normalize_inbound(self, payload: Dict[str, Any]) -> Optional[NormalizedMessage]:
        pass

    @abstractmethod
    def send_text(self, channel_config: ChannelConfig, number: str, text: str) -> Dict[str, Any]:
        pass

    @abstractmethod
    def get_connection_state(self, channel_config: ChannelConfig) -> Dict[str, Any]:
        pass

    @abstractmethod
    def set_webhook(self, channel_config: ChannelConfig, webhook_url: str) -> Dict[str, Any]:
        pass


class EvolutionProvider(WhatsAppProvider):
    def provider_name(self) -> str:
        return "evolution"

    def normalize_inbound(self, payload: Dict[str, Any]) -> Optional[NormalizedMessage]:
        """
        Evolution API Inbound message format usually has 'event': 'messages.upsert' or 'MESSAGES_UPSERT'.
        Payload example:
        {
          "event": "messages.upsert",
          "instance": "ImobiliariaAlfa",
          "data": {
            "key": {
              "remoteJid": "5511999999999@s.whatsapp.net",
              "fromMe": false,
              "id": "XYZ"
            },
            "pushName": "John Doe",
            "message": {
              "conversation": "Hello there"
            },
            "messageTimestamp": 1670000000
          }
        }
        """
        try:
            event = payload.get("event", "")
            # We only handle messages.upsert / MESSAGES_UPSERT for inbound messages
            if "messages.upsert" not in event.lower():
                return None

            instance_name = payload.get("instance")
            data = payload.get("data", {})
            key = data.get("key", {})
            
            is_from_me = key.get("fromMe", False)
            remote_jid = key.get("remoteJid", "")
            
            is_group = "@g.us" in remote_jid
            
            # Extract clean number
            number = remote_jid.split("@")[0] if remote_jid else ""
            
            contact_name = data.get("pushName")
            
            # Get text message contents
            message_obj = data.get("message", {})
            text = None
            if message_obj:
                # Text could be in "conversation" or "extendedTextMessage"
                if "conversation" in message_obj:
                    text = message_obj["conversation"]
                elif "extendedTextMessage" in message_obj:
                    text = message_obj["extendedTextMessage"].get("text")
                elif "imageMessage" in message_obj:
                    text = message_obj["imageMessage"].get("caption")
                elif "videoMessage" in message_obj:
                    text = message_obj["videoMessage"].get("caption")
            
            timestamp = data.get("messageTimestamp", 0)

            if not number:
                return None

            return NormalizedMessage(
                instance_name=instance_name,
                number=number,
                contact_name=contact_name,
                text=text,
                timestamp=timestamp,
                is_from_me=is_from_me,
                is_group=is_group,
                raw_payload=payload
            )
        except Exception as e:
            logger.error(f"Error normalizing Evolution inbound payload: {e}", exc_info=True)
            return None

    def send_text(self, channel_config: ChannelConfig, number: str, text: str) -> Dict[str, Any]:
        url = channel_config.provider_url or "http://localhost:8080"
        instance = channel_config.provider_instance_id
        token = channel_config.provider_token
        
        endpoint = f"{url.rstrip('/')}/message/sendText/{instance}"
        
        headers = {
            "apikey": token,
            "Content-Type": "application/json"
        }
        
        body = {
            "number": number,
            "options": {
                "delay": 1200,
                "presence": "composing"
            },
            "textMessage": {
                "text": text
            }
        }
        
        logger.info(f"EvolutionProvider: Sending text message to {number} via instance {instance}")
        try:
            with httpx.Client() as client:
                response = client.post(endpoint, json=body, headers=headers, timeout=10.0)
                response_json = response.json()
                logger.info(f"EvolutionProvider Response: {response.status_code} - {response_json}")
                return {
                    "status_code": response.status_code,
                    "data": response_json,
                    "success": response.status_code in [200, 201]
                }
        except Exception as e:
            logger.error(f"EvolutionProvider failed to send text to {number}: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def get_connection_state(self, channel_config: ChannelConfig) -> Dict[str, Any]:
        url = channel_config.provider_url or "http://localhost:8080"
        instance = channel_config.provider_instance_id
        token = channel_config.provider_token
        
        endpoint = f"{url.rstrip('/')}/instance/connectionState/{instance}"
        
        headers = {
            "apikey": token
        }
        
        try:
            with httpx.Client() as client:
                response = client.get(endpoint, headers=headers, timeout=5.0)
                response_json = response.json()
                return {
                    "success": response.status_code == 200,
                    "status_code": response.status_code,
                    "data": response_json
                }
        except Exception as e:
            logger.error(f"EvolutionProvider failed to get connection state for {instance}: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def set_webhook(self, channel_config: ChannelConfig, webhook_url: str) -> Dict[str, Any]:
        url = channel_config.provider_url or "http://localhost:8080"
        instance = channel_config.provider_instance_id
        token = channel_config.provider_token
        
        endpoint = f"{url.rstrip('/')}/webhook/set/{instance}"
        
        headers = {
            "apikey": token,
            "Content-Type": "application/json"
        }
        
        body = {
            "enabled": True,
            "url": webhook_url,
            "webhook_by_events": False,
            "events": [
                "MESSAGES_UPSERT"
            ]
        }
        
        try:
            with httpx.Client() as client:
                response = client.post(endpoint, json=body, headers=headers, timeout=5.0)
                response_json = response.json()
                return {
                    "success": response.status_code in [200, 201],
                    "status_code": response.status_code,
                    "data": response_json
                }
        except Exception as e:
            logger.error(f"EvolutionProvider failed to set webhook for {instance}: {e}")
            return {
                "success": False,
                "error": str(e)
            }


class MetaCloudProvider(WhatsAppProvider):
    def provider_name(self) -> str:
        return "meta"

    def normalize_inbound(self, payload: Dict[str, Any]) -> Optional[NormalizedMessage]:
        """
        Meta Cloud API Webhook format.
        Structure:
        {
          "object": "whatsapp_business_account",
          "entry": [
            {
              "id": "WABA_ID",
              "changes": [
                {
                  "value": {
                    "messaging_product": "whatsapp",
                    "metadata": {
                      "display_phone_number": "123456",
                      "phone_number_id": "phone_id_abc"
                    },
                    "contacts": [
                      {
                        "profile": {
                          "name": "Jane Doe"
                        },
                        "wa_id": "5511999999999"
                      }
                    ],
                    "messages": [
                      {
                        "from": "5511999999999",
                        "id": "message_id_1",
                        "timestamp": "1670000000",
                        "text": {
                          "body": "Hello SDR"
                        },
                        "type": "text"
                      }
                    ]
                  },
                  "field": "messages"
                }
              ]
            }
          ]
        }
        """
        try:
            if payload.get("object") != "whatsapp_business_account":
                return None

            entry_list = payload.get("entry", [])
            if not entry_list:
                return None

            changes = entry_list[0].get("changes", [])
            if not changes:
                return None

            value = changes[0].get("value", {})
            metadata = value.get("metadata", {})
            phone_number_id = metadata.get("phone_number_id", "")  # Map to channel provider_instance_id

            messages = value.get("messages", [])
            if not messages:
                return None

            msg = messages[0]
            from_number = msg.get("from")
            text = msg.get("text", {}).get("body") if msg.get("type") == "text" else None
            timestamp = int(msg.get("timestamp", 0))

            contacts = value.get("contacts", [])
            contact_name = contacts[0].get("profile", {}).get("name") if contacts else None

            # Meta webhook doesn't deliver our own outbound replies in typical inbox flows
            # but if it does, we can verify. Usually it's inbound only.
            is_from_me = False
            is_group = False  # Meta API is 1:1 business chat only

            if not from_number:
                return None

            return NormalizedMessage(
                instance_name=phone_number_id,
                number=from_number,
                contact_name=contact_name,
                text=text,
                timestamp=timestamp,
                is_from_me=is_from_me,
                is_group=is_group,
                raw_payload=payload
            )
        except Exception as e:
            logger.error(f"Error normalizing Meta inbound payload: {e}", exc_info=True)
            return None

    def send_text(self, channel_config: ChannelConfig, number: str, text: str) -> Dict[str, Any]:
        # URL for Meta Graph API
        url = channel_config.provider_url or "https://graph.facebook.com/v19.0"
        phone_number_id = channel_config.provider_instance_id
        token = channel_config.provider_token
        
        endpoint = f"{url.rstrip('/')}/{phone_number_id}/messages"
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        body = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": number,
            "type": "text",
            "text": {
                "preview_url": False,
                "body": text
            }
        }
        
        logger.info(f"MetaCloudProvider (Stub/Real): Sending text message to {number} via phone_number_id {phone_number_id}")
        try:
            # For stub or real depending on token availability
            if not token or token == "stub-token":
                logger.info("MetaCloudProvider: Using stub response (no token)")
                return {
                    "success": True,
                    "data": {"message_status": "accepted_by_stub", "to": number, "body": text},
                    "status_code": 200
                }

            with httpx.Client() as client:
                response = client.post(endpoint, json=body, headers=headers, timeout=10.0)
                response_json = response.json()
                logger.info(f"MetaCloudProvider Response: {response.status_code} - {response_json}")
                return {
                    "status_code": response.status_code,
                    "data": response_json,
                    "success": response.status_code in [200, 201]
                }
        except Exception as e:
            logger.error(f"MetaCloudProvider failed to send text to {number}: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def get_connection_state(self, channel_config: ChannelConfig) -> Dict[str, Any]:
        # Meta Cloud API is cloud-hosted by Meta and doesn't require typical QR code pairing
        return {
            "success": True,
            "data": {"state": "CONNECTED", "details": "Meta Cloud API does not require QR authentication"}
        }

    def set_webhook(self, channel_config: ChannelConfig, webhook_url: str) -> Dict[str, Any]:
        # Webhook for Meta is configured globally on the Facebook Developer Console, not per instance programmatically
        return {
            "success": True,
            "data": {"details": "Configure webhook URL globally in Meta Developer Console under WhatsApp configuration"}
        }


# Factory to get correct provider
def get_whatsapp_provider(provider_name: str) -> WhatsAppProvider:
    if provider_name.lower() == "evolution":
        return EvolutionProvider()
    elif provider_name.lower() == "meta":
        return MetaCloudProvider()
    else:
        raise ValueError(f"Unknown WhatsApp provider: {provider_name}")
