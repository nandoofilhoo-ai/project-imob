from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any
from datetime import datetime
from src.models.db_models import (
    Tenant, TenantConfig, ChannelConfig, Lead,
    Conversation, Message, LeadQualification, Handoff, AuditLog
)

class DbRepository:
    @staticmethod
    def get_tenant(db: Session, tenant_id: int) -> Optional[Tenant]:
        return db.query(Tenant).filter(Tenant.id == tenant_id).first()

    @staticmethod
    def get_tenant_config(db: Session, tenant_id: int) -> Optional[TenantConfig]:
        return db.query(TenantConfig).filter(TenantConfig.tenant_id == tenant_id).first()

    @staticmethod
    def get_channel_by_instance(db: Session, provider: str, instance_id: str) -> Optional[ChannelConfig]:
        return db.query(ChannelConfig).filter(
            ChannelConfig.provider == provider,
            ChannelConfig.provider_instance_id == instance_id,
            ChannelConfig.status == "active"
        ).first()

    @staticmethod
    def get_channel_by_id(db: Session, channel_id: int) -> Optional[ChannelConfig]:
        return db.query(ChannelConfig).filter(ChannelConfig.id == channel_id).first()

    @staticmethod
    def list_active_channels(db: Session) -> List[ChannelConfig]:
        return db.query(ChannelConfig).filter(ChannelConfig.status == "active").all()

    @staticmethod
    def get_lead_by_number(db: Session, tenant_id: int, number: str) -> Optional[Lead]:
        return db.query(Lead).filter(
            Lead.tenant_id == tenant_id,
            Lead.number == number
        ).first()

    @staticmethod
    def create_lead(db: Session, tenant_id: int, number: str, name: Optional[str] = None, email: Optional[str] = None) -> Lead:
        lead = Lead(tenant_id=tenant_id, number=number, name=name, email=email)
        db.add(lead)
        db.commit()
        db.refresh(lead)
        
        # Create corresponding blank qualification
        DbRepository.create_qualification(db, lead.id)
        
        return lead

    @staticmethod
    def get_or_create_lead(db: Session, tenant_id: int, number: str, name: Optional[str] = None) -> Lead:
        lead = DbRepository.get_lead_by_number(db, tenant_id, number)
        if not lead:
            lead = DbRepository.create_lead(db, tenant_id, number, name=name)
        elif name and not lead.name:
            lead.name = name
            db.commit()
            db.refresh(lead)
        return lead

    @staticmethod
    def get_active_conversation(db: Session, tenant_id: int, lead_id: int, channel_config_id: int) -> Optional[Conversation]:
        # An active conversation is one with status 'open' or 'handoff' or 'takeover'
        # In a real system, you might only consider 'open'
        return db.query(Conversation).filter(
            Conversation.tenant_id == tenant_id,
            Conversation.lead_id == lead_id,
            Conversation.channel_config_id == channel_config_id,
            Conversation.status != "closed"
        ).order_by(Conversation.updated_at.desc()).first()

    @staticmethod
    def create_conversation(db: Session, tenant_id: int, lead_id: int, channel_config_id: int) -> Conversation:
        conversation = Conversation(
            tenant_id=tenant_id,
            lead_id=lead_id,
            channel_config_id=channel_config_id,
            status="open"
        )
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
        return conversation

    @staticmethod
    def get_or_create_conversation(db: Session, tenant_id: int, lead_id: int, channel_config_id: int) -> Conversation:
        conversation = DbRepository.get_active_conversation(db, tenant_id, lead_id, channel_config_id)
        if not conversation:
            conversation = DbRepository.create_conversation(db, tenant_id, lead_id, channel_config_id)
        return conversation

    @staticmethod
    def create_message(
        db: Session,
        conversation_id: int,
        sender_type: str,
        text: str,
        payload: Optional[Dict[str, Any]] = None,
        chatwoot_message_id: Optional[int] = None
    ) -> Message:
        message = Message(
            conversation_id=conversation_id,
            sender_type=sender_type,
            text=text,
            payload=payload,
            chatwoot_message_id=chatwoot_message_id
        )
        db.add(message)
        
        # Touch conversation updated_at
        conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
        if conversation:
            conversation.updated_at = datetime.utcnow()
            
        db.commit()
        db.refresh(message)
        return message

    @staticmethod
    def get_qualification(db: Session, lead_id: int) -> Optional[LeadQualification]:
        return db.query(LeadQualification).filter(LeadQualification.lead_id == lead_id).first()

    @staticmethod
    def create_qualification(db: Session, lead_id: int) -> LeadQualification:
        qualification = LeadQualification(lead_id=lead_id)
        db.add(qualification)
        db.commit()
        db.refresh(qualification)
        return qualification

    @staticmethod
    def update_qualification(db: Session, qualification_id: int, update_data: Dict[str, Any]) -> LeadQualification:
        qualification = db.query(LeadQualification).filter(LeadQualification.id == qualification_id).first()
        if qualification:
            for key, value in update_data.items():
                if hasattr(qualification, key):
                    setattr(qualification, key, value)
            qualification.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(qualification)
        return qualification

    @staticmethod
    def create_handoff(
        db: Session,
        lead_id: int,
        conversation_id: int,
        reason: Optional[str] = None,
        details: Optional[str] = None
    ) -> Handoff:
        handoff = Handoff(
            lead_id=lead_id,
            conversation_id=conversation_id,
            reason=reason,
            details=details,
            status="pending"
        )
        db.add(handoff)
        
        # Update Lead status
        lead = db.query(Lead).filter(Lead.id == lead_id).first()
        if lead:
            lead.status = "handoff"
            
        # Update Conversation status
        conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
        if conversation:
            conversation.status = "handoff"
            
        db.commit()
        db.refresh(handoff)
        return handoff

    @staticmethod
    def create_audit_log(db: Session, tenant_id: Optional[int], event_type: str, payload: Any) -> AuditLog:
        audit_log = AuditLog(tenant_id=tenant_id, event_type=event_type, payload=payload)
        db.add(audit_log)
        db.commit()
        db.refresh(audit_log)
        return audit_log
