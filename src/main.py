from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.core.config import settings
from src.core.database import Base, engine
from src.core.logger import get_logger

# Import routers
from src.api.routes import health, webhooks, debug, testing, channels

logger = get_logger(__name__)

# Create tables automatically on startup (fallback to ease local runs without alembic)
try:
    logger.info("Verifying and creating database tables...")
    Base.metadata.create_all(bind=engine)
except Exception as e:
    logger.error(f"Error creating database tables on startup: {e}")

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
