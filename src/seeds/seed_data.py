import sys
import os
# Add root path to sys.path to run directly from cmd/docker
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.core.database import Base, engine, SessionLocal
from src.core.config import settings
from src.models.db_models import Tenant, TenantConfig, ChannelConfig
from src.core.logger import get_logger

logger = get_logger(__name__)

def run_seed():
    logger.info("Initializing database schema...")
    # This automatically creates tables if they do not exist
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    try:
        # Check if tenant already exists
        alfa_tenant = db.query(Tenant).filter(Tenant.name == "Imobiliária Alfa").first()
        if not alfa_tenant:
            logger.info("Seeding database...")
            # 1. Create Tenant
            tenant = Tenant(name="Imobiliária Alfa")
            db.add(tenant)
            db.flush() # Populate ID

            # 2. Create Tenant Config
            config = TenantConfig(
                tenant_id=tenant.id,
                prompt_base=(
                    "Você é o corretor virtual de atendimento inicial (SDR) da Imobiliária Alfa. "
                    "Seu objetivo é coletar o objetivo (comprar/alugar), tipo de imóvel (casa/apto), "
                    "bairro e faixa de preço desejada de forma atenciosa. Nunca invente preços ou imóveis."
                )
            )
            db.add(config)

            # 3. Create Channel Config (Evolution Provider)
            channel = ChannelConfig(
                tenant_id=tenant.id,
                name="WhatsApp Principal Evolution",
                provider="evolution",
                provider_instance_id=settings.EVOLUTION_INSTANCE_NAME or settings.EVOLUTION_INSTANCE,
                provider_token=settings.EVOLUTION_API_KEY or "sua-evolution-key",
                provider_url=settings.EVOLUTION_API_URL or "http://localhost:8080",
                status="active",
                chatwoot_inbox_id=1 # Default inbox ID mapping
            )
            db.add(channel)

            db.commit()
            logger.info("Seeding completed successfully!")

        else:
            logger.info("Tenant 'Imobiliária Alfa' already exists. Skipping seeding.")
    except Exception as e:
        db.rollback()
        logger.error(f"Error seeding database: {e}", exc_info=True)
        raise e
    finally:
        db.close()

if __name__ == "__main__":
    run_seed()
