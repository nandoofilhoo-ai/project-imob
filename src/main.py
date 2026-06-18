from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.core.config import settings
from src.core.database import Base, engine, SessionLocal
from src.core.logger import get_logger
from src.models.db_models import Tenant, ChannelConfig

# Import routers
from src.api.routes import health, webhooks, debug, testing, channels

logger = get_logger(__name__)

# Create tables automatically on startup (fallback to ease local runs without alembic)
try:
    logger.info("Verifying and creating database tables...")
    Base.metadata.create_all(bind=engine)
except Exception as e:
    logger.error(f"Error creating database tables on startup: {e}")


def sync_evolution_channel_from_env() -> None:
    if not settings.AUTO_SYNC_EVOLUTION_CHANNEL:
        logger.info("AUTO_SYNC_EVOLUTION_CHANNEL disabled. Skipping Evolution channel sync.")
        return

    instance_name = settings.EVOLUTION_INSTANCE_NAME or settings.EVOLUTION_INSTANCE
    if not instance_name:
        logger.info("No Evolution instance configured. Skipping Evolution channel sync.")
        return

    db = SessionLocal()
    try:
        tenant = db.query(Tenant).filter(Tenant.name == settings.DEFAULT_TENANT_NAME).first()
        if not tenant:
            logger.warning(
                f"Tenant '{settings.DEFAULT_TENANT_NAME}' not found. Skipping Evolution channel sync."
            )
            return

        channel = db.query(ChannelConfig).filter(ChannelConfig.provider == "evolution").order_by(ChannelConfig.id.asc()).first()

        if channel:
            channel.tenant_id = tenant.id
            channel.name = settings.EVOLUTION_CHANNEL_NAME
            channel.provider_instance_id = instance_name
            channel.provider_url = settings.EVOLUTION_API_URL
            channel.provider_token = settings.EVOLUTION_API_KEY
            channel.status = "active"
            logger.info(
                f"Updated Evolution channel id={channel.id} to instance '{instance_name}'."
            )
        else:
            channel = ChannelConfig(
                tenant_id=tenant.id,
                name=settings.EVOLUTION_CHANNEL_NAME,
                provider="evolution",
                provider_instance_id=instance_name,
                provider_token=settings.EVOLUTION_API_KEY,
                provider_url=settings.EVOLUTION_API_URL,
                status="active",
                chatwoot_inbox_id=1,
            )
            db.add(channel)
            logger.info(
                f"Created Evolution channel for instance '{instance_name}'."
            )

        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to sync Evolution channel from environment: {e}", exc_info=True)
    finally:
        db.close()

app = FastAPI(
    title=settings.APP_NAME,
    description="Backend MVP para atendimento imobiliário SDR integrado com Evolution API/Meta Cloud API e Chatwoot.",
    version="1.0.0"
)

# CORS middleware for development ease
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routes
app.include_router(health.router, tags=["Health"])
app.include_router(webhooks.router, tags=["Webhooks"])
app.include_router(debug.router, tags=["Debug"])
app.include_router(testing.router, tags=["Testing"])
app.include_router(channels.router, tags=["Channels"])


@app.get("/")
def read_root():
    return {
        "message": f"Welcome to {settings.APP_NAME}",
        "docs_url": "/docs",
        "health_url": "/health"
    }

logger.info("Application initialized successfully.")
sync_evolution_channel_from_env()
