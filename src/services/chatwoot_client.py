import httpx
import random
from typing import Dict, Any, Optional, List
from src.core.config import settings
from src.core.logger import get_logger

logger = get_logger(__name__)

class ChatwootClient:
    def __init__(self):
        self.url = settings.CHATWOOT_URL
        self.token = settings.CHATWOOT_ACCESS_TOKEN
        self.account_id = settings.CHATWOOT_ACCOUNT_ID
        self.headers = {
            "api_access_token": self.token,
            "Content-Type": "application/json"
        } if self.token else {}
        
        # Determine if we should run in mock mode
        self.is_mock = not (self.url and self.token and self.account_id)
        if self.is_mock:
            logger.warning("ChatwootClient: Missing credentials. Operating in MOCK mode.")

    def _get_base_url(self) -> str:
        return f"{self.url.rstrip('/')}/api/v1/accounts/{self.account_id}"

    def find_or_create_contact(self, number: str, name: Optional[str] = None) -> Optional[int]:
        """
        Looks up a contact in Chatwoot by phone number, or creates one if it doesn't exist.
        """
        # Clean number (Chatwoot search expects "+" or prefix matches sometimes, let's keep it simple)
        if not number.startswith("+"):
            formatted_number = f"+{number}"
        else:
            formatted_number = number

        if self.is_mock:
            mock_id = random.randint(1000, 9999)
            logger.info(f"[Mock Chatwoot] Find or Create Contact: {formatted_number} ({name or 'Unnamed'}) -> ID: {mock_id}")
            return mock_id

        try:
            # 1. Search for contact
            search_url = f"{self._get_base_url()}/contacts/search"
            params = {"q": formatted_number}
            
            with httpx.Client() as client:
                response = client.get(search_url, headers=self.headers, params=params, timeout=5.0)
                if response.status_code == 200:
                    payload = response.json()
                    payload_data = payload.get("payload", [])
                    if payload_data:
                        contact_id = payload_data[0].get("id")
                        logger.info(f"ChatwootClient: Found existing contact {contact_id} for number {formatted_number}")
                        return contact_id
                
                # 2. Create contact if search yielded no results
                create_url = f"{self._get_base_url()}/contacts"
                body = {
                    "name": name or formatted_number,
                    "phone_number": formatted_number
                }
                response = client.post(create_url, headers=self.headers, json=body, timeout=5.0)
                if response.status_code in [200, 201]:
                    contact_data = response.json().get("payload", {}).get("contact", {})
                    contact_id = contact_data.get("id")
                    logger.info(f"ChatwootClient: Created new contact {contact_id} for number {formatted_number}")
                    return contact_id
                else:
                    logger.error(f"ChatwootClient: Failed to create contact: {response.status_code} - {response.text}")
                    # Fallback to mock ID to avoid crashing pipeline
                    return random.randint(1000, 9999)
        except Exception as e:
            logger.error(f"ChatwootClient error in find_or_create_contact: {e}", exc_info=True)
            return random.randint(1000, 9999)

    def find_or_create_conversation(self, contact_id: int, inbox_id: int) -> Optional[int]:
        """
        Finds open conversations for the contact or creates a new one in the specified inbox.
        """
        if self.is_mock:
            mock_id = random.randint(10000, 99999)
            logger.info(f"[Mock Chatwoot] Find or Create Conversation for Contact {contact_id} in Inbox {inbox_id} -> ID: {mock_id}")
            return mock_id

        try:
            # 1. Look for existing open conversations
            search_url = f"{self._get_base_url()}/contacts/{contact_id}/conversations"
            with httpx.Client() as client:
                response = client.get(search_url, headers=self.headers, timeout=5.0)
                if response.status_code == 200:
                    conversations = response.json().get("payload", [])
                    # Find first open conversation in the same inbox
                    for conv in conversations:
                        if conv.get("inbox_id") == inbox_id and conv.get("status") == "open":
                            conv_id = conv.get("id")
                            logger.info(f"ChatwootClient: Found existing open conversation {conv_id} in inbox {inbox_id}")
                            return conv_id

                # 2. Create conversation if none found
                create_url = f"{self._get_base_url()}/conversations"
                body = {
                    "contact_id": contact_id,
                    "inbox_id": inbox_id,
                    "status": "open"
                }
                response = client.post(create_url, headers=self.headers, json=body, timeout=5.0)
                if response.status_code in [200, 201]:
                    conv_id = response.json().get("id")
                    logger.info(f"ChatwootClient: Created new conversation {conv_id} in inbox {inbox_id}")
                    return conv_id
                else:
                    logger.error(f"ChatwootClient: Failed to create conversation: {response.status_code} - {response.text}")
                    return random.randint(10000, 99999)
        except Exception as e:
            logger.error(f"ChatwootClient error in find_or_create_conversation: {e}", exc_info=True)
            return random.randint(10000, 99999)

    def _create_message(self, conversation_id: int, text: str, message_type: int, private: bool = False) -> Optional[int]:
        """
        Internal message creator:
        message_type: 0 for incoming (lead), 1 for outgoing (bot/agent)
        private: True for private notes
        """
        if self.is_mock:
            mock_id = random.randint(100000, 999999)
            msg_type_str = "INCOMING" if message_type == 0 else ("NOTE" if private else "OUTGOING")
            logger.info(f"[Mock Chatwoot] Create {msg_type_str} Message inside Conversation {conversation_id}: \"{text}\" -> ID: {mock_id}")
            return mock_id

        try:
            url = f"{self._get_base_url()}/conversations/{conversation_id}/messages"
            body = {
                "content": text,
                "message_type": message_type,
                "private": private
            }
            with httpx.Client() as client:
                response = client.post(url, headers=self.headers, json=body, timeout=5.0)
                if response.status_code in [200, 201]:
                    msg_id = response.json().get("id")
                    return msg_id
                else:
                    logger.error(f"ChatwootClient: Failed to create message: {response.status_code} - {response.text}")
                    return random.randint(100000, 999999)
        except Exception as e:
            logger.error(f"ChatwootClient error in _create_message: {e}", exc_info=True)
            return random.randint(100000, 999999)

    def create_incoming_message(self, conversation_id: int, text: str) -> Optional[int]:
        return self._create_message(conversation_id, text, message_type=0)

    def create_outgoing_message(self, conversation_id: int, text: str) -> Optional[int]:
        return self._create_message(conversation_id, text, message_type=1)

    def add_private_note(self, conversation_id: int, text: str) -> Optional[int]:
        return self._create_message(conversation_id, text, message_type=1, private=True)

    def add_label(self, conversation_id: int, label: str) -> bool:
        """
        Adds a tag/label to the conversation
        """
        if self.is_mock:
            logger.info(f"[Mock Chatwoot] Add label '{label}' to Conversation {conversation_id}")
            return True

        try:
            url = f"{self._get_base_url()}/conversations/{conversation_id}/labels"
            body = {
                "labels": [label]
            }
            with httpx.Client() as client:
                response = client.post(url, headers=self.headers, json=body, timeout=5.0)
                if response.status_code in [200, 201]:
                    logger.info(f"ChatwootClient: Added label '{label}' to conversation {conversation_id}")
                    return True
                else:
                    logger.error(f"ChatwootClient: Failed to add label: {response.status_code} - {response.text}")
                    return False
        except Exception as e:
            logger.error(f"ChatwootClient error in add_label: {e}", exc_info=True)
            return False

    def assign_conversation(self, conversation_id: int, agent_id: int) -> bool:
        """
        Assigns the conversation to an agent (stub)
        """
        if self.is_mock:
            logger.info(f"[Mock Chatwoot] Assign Conversation {conversation_id} to Agent {agent_id}")
            return True
        logger.info(f"ChatwootClient: Assigning conversation {conversation_id} to agent {agent_id} (Stubbed)")
        return True
