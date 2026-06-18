from pydantic import BaseModel, Field
from typing import Optional, Any, Dict
from datetime import datetime

# Tenant Schemas
class TenantBase(BaseModel):
    name: str

class TenantCreate(TenantBase):
    pass

class TenantResponse(TenantBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Tenant Config Schemas
class TenantConfigBase(BaseModel):
    prompt_base: Optional[str] = None

class TenantConfigCreate(TenantConfigBase):
    tenant_id: int

class TenantConfigResponse(TenantConfigBase):
    id: int
    tenant_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Channel Config Schemas
class ChannelConfigBase(BaseModel):
    name: str
    provider: str  # 'evolution' or 'meta'
    provider_instance_id: str
    provider_token: Optional[str] = None
    provider_url: Optional[str] = None
    status: Optional[str] = "active"
    chatwoot_inbox_id: Optional[int] = None

class ChannelConfigCreate(ChannelConfigBase):
    tenant_id: int

class ChannelConfigResponse(ChannelConfigBase):
    id: int
    tenant_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Lead Schemas
class LeadBase(BaseModel):
    number: str
    name: Optional[str] = None
    email: Optional[str] = None
    status: Optional[str] = "active"
    chatwoot_contact_id: Optional[int] = None

class LeadCreate(LeadBase):
    tenant_id: int

class LeadResponse(LeadBase):
    id: int
    tenant_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Lead Qualification Schemas
class LeadQualificationBase(BaseModel):
    objetivo: Optional[str] = None
    tipo_imovel: Optional[str] = None
    bairro: Optional[str] = None
    faixa_preco: Optional[str] = None
    urgencia: Optional[str] = None
    pronto_para_handoff: Optional[bool] = False
    resumo_atual: Optional[str] = None

class LeadQualificationUpdate(LeadQualificationBase):
    pass

class LeadQualificationResponse(LeadQualificationBase):
    id: int
    lead_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Message Schemas
class MessageBase(BaseModel):
    sender_type: str  # 'lead', 'bot', 'agent'
    text: str
    payload: Optional[Dict[str, Any]] = None
    chatwoot_message_id: Optional[int] = None

class MessageCreate(MessageBase):
    conversation_id: int

class MessageResponse(MessageBase):
    id: int
    conversation_id: int
    created_at: datetime

    class Config:
        from_attributes = True

# Conversation Schemas
class ConversationBase(BaseModel):
    status: Optional[str] = "open"
    chatwoot_conversation_id: Optional[int] = None

class ConversationCreate(ConversationBase):
    tenant_id: int
    lead_id: int
    channel_config_id: int

class ConversationResponse(ConversationBase):
    id: int
    tenant_id: int
    lead_id: int
    channel_config_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Handoff Schemas
class HandoffBase(BaseModel):
    reason: Optional[str] = None
    details: Optional[str] = None
    status: Optional[str] = "pending"

class HandoffCreate(HandoffBase):
    lead_id: int
    conversation_id: int

class HandoffResponse(HandoffBase):
    id: int
    lead_id: int
    conversation_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Audit Log Schemas
class AuditLogResponse(BaseModel):
    id: int
    tenant_id: Optional[int]
    event_type: str
    payload: Optional[Dict[str, Any]]
    created_at: datetime

    class Config:
        from_attributes = True

# Custom Request/Response Schemas
class TestSendRequest(BaseModel):
    number: str
    text: str
    instance_name: Optional[str] = None

class TestGenerateRequest(BaseModel):
    tenant_id: int
    text: str
    number: str
