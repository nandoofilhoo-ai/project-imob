import os
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

# Force sqlite database URL and default instance for tests
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["EVOLUTION_INSTANCE"] = "ImobiliariaAlfa"


from src.core.database import Base, get_db
from src.models import db_models  # Import models to register metadata in Base
from src.main import app
from src.seeds.seed_data import run_seed

from sqlalchemy.pool import StaticPool

# SQLite engine for tests
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="function")
def db_session():
    # Create tables
    Base.metadata.create_all(bind=engine)


    db = TestingSessionLocal()
    
    # Run seeding inside test DB
    # Create default tenant and channel config
    from src.models.db_models import Tenant, TenantConfig, ChannelConfig
    tenant = Tenant(id=1, name="Imobiliária Alfa")
    db.add(tenant)
    db.flush()
    
    config = TenantConfig(
        id=1,
        tenant_id=tenant.id,
        prompt_base="Você é o SDR da Alfa. Colete objetivo, tipo de imóvel, bairro e valor."
    )
    db.add(config)
    
    channel = ChannelConfig(
        id=1,
        tenant_id=tenant.id,
        name="WhatsApp Principal Evolution",
        provider="evolution",
        provider_instance_id="ImobiliariaAlfa",
        provider_token="mock-token",
        provider_url="http://localhost:8080",
        status="active",
        chatwoot_inbox_id=1
    )
    db.add(channel)
    db.commit()
    
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
            
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
