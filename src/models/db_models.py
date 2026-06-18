from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from src.core.database import Base

class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    configs = relationship("TenantConfig", back_populates="tenant", cascade="all, delete-orphan")
    channels = relationship("ChannelConfig", back_populates="tenant", cascade="all, delete-orphan")
    leads = relationship("Lead", back_populates="tenant", cascade="all, delete-orphan")
    conversations = relationship("Conversation", back_populates="tenant", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="tenant", cascade="all, delete-orphan")


class TenantConfig(Base):
    __tablename__ = "tenant_configs"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, unique=True)
    prompt_base = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    tenant = relationship("Tenant", back_populates="configs")


class ChannelConfig(Base):
    __tablename__ = "channel_configs"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    provider = Column(String(50), nullable=False)  # 'evolution' or 'meta'
    provider_instance_id = Column(String(255), nullable=False, index=True)  # instance_name for Evolution, phone_number_id for Meta
    provider_token = Column(String(500), nullable=True)
    provider_url = Column(String(500), nullable=True)
    status = Column(String(50), default="active")  # 'active', 'inactive'
    chatwoot_inbox_id = Column(Integer, nullable=True) # Mapped Chatwoot Inbox
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    tenant = relationship("Tenant", back_populates="channels")
    conversations = relationship("Conversation", back_populates="channel")


class Lead(Base):
    __tablename__ = "leads"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    number = Column(String(50), nullable=False, index=True)  # WhatsApp Number e.g. 5511999999999
    name = Column(String(255), nullable=True)
    email = Column(String(255), nullable=True)
    status = Column(String(50), default="active")  # 'active', 'handoff', 'takeover'
    chatwoot_contact_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    tenant = relationship("Tenant", back_populates="leads")
    conversations = relationship("Conversation", back_populates="lead", cascade="all, delete-orphan")
    qualifications = relationship("LeadQualification", back_populates="lead", cascade="all, delete-orphan", uselist=False)
    handoffs = relationship("Handoff", back_populates="lead", cascade="all, delete-orphan")


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    lead_id = Column(Integer, ForeignKey("leads.id", ondelete="CASCADE"), nullable=False)
    channel_config_id = Column(Integer, ForeignKey("channel_configs.id", ondelete="CASCADE"), nullable=False)
    status = Column(String(50), default="open")  # 'open', 'closed', 'handoff', 'takeover'
    chatwoot_conversation_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    tenant = relationship("Tenant", back_populates="conversations")
    lead = relationship("Lead", back_populates="conversations")
    channel = relationship("ChannelConfig", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")
    handoffs = relationship("Handoff", back_populates="conversation", cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
    sender_type = Column(String(50), nullable=False)  # 'lead', 'bot', 'agent' (human)
    text = Column(Text, nullable=False)
    payload = Column(JSON, nullable=True)  # raw provider payload
    chatwoot_message_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    conversation = relationship("Conversation", back_populates="messages")


class LeadQualification(Base):
    __tablename__ = "lead_qualifications"

    id = Column(Integer, primary_key=True, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, unique=True)
    objetivo = Column(String(50), nullable=True)  # 'compra', 'aluguel'
    tipo_imovel = Column(String(100), nullable=True)  # 'casa', 'apartamento', 'terreno', etc.
    bairro = Column(String(255), nullable=True)
    faixa_preco = Column(String(100), nullable=True)
    urgencia = Column(String(100), nullable=True)  # 'alta', 'media', 'baixa'
    pronto_para_handoff = Column(Boolean, default=False)
    resumo_atual = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    lead = relationship("Lead", back_populates="qualifications")


class Handoff(Base):
    __tablename__ = "handoffs"

    id = Column(Integer, primary_key=True, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id", ondelete="CASCADE"), nullable=False)
    conversation_id = Column(Integer, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
    reason = Column(String(255), nullable=True)
    details = Column(Text, nullable=True)
    status = Column(String(50), default="pending")  # 'pending', 'resolved'
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    lead = relationship("Lead", back_populates="handoffs")
    conversation = relationship("Conversation", back_populates="handoffs")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True)
    event_type = Column(String(100), nullable=False)  # 'webhook_raw', 'orchestration_decision', etc.
    payload = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    tenant = relationship("Tenant", back_populates="audit_logs")
