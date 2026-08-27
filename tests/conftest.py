"""
Pytest configuration and shared fixtures.
"""
import pytest
import asyncio
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from db.connection import Base
from db.schema.models import User, Plan, Event, Subscription, Payment


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
def db_engine():
    """Create an in-memory SQLite database for testing."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)


@pytest.fixture(scope="function")
def db_session(db_engine):
    """Create a database session for testing."""
    SessionLocal = sessionmaker(bind=db_engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def sample_user(db_session):
    """Create a sample user for testing."""
    user = User(
        email="test@example.com",
        plan_id=None,
        acquisition_channel="organic",
        segment="test",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def sample_plan(db_session):
    """Create a sample plan for testing."""
    plan = Plan(
        name="Test Plan",
        price_monthly=9.99,
        price_yearly=99.99,
        features={"test": True},
    )
    db_session.add(plan)
    db_session.commit()
    db_session.refresh(plan)
    return plan


@pytest.fixture
def sample_event(db_session, sample_user):
    """Create a sample event for testing."""
    event = Event(
        user_id=sample_user.id,
        event_name="page_view",
        event_properties={"page": "/home"},
    )
    db_session.add(event)
    db_session.commit()
    db_session.refresh(event)
    return event


@pytest.fixture
def sample_subscription(db_session, sample_user, sample_plan):
    """Create a sample subscription for testing."""
    from datetime import datetime, timedelta
    sub = Subscription(
        user_id=sample_user.id,
        plan_id=sample_plan.id,
        status="active",
        started_at=datetime.utcnow(),
        current_period_start=datetime.utcnow(),
        current_period_end=datetime.utcnow() + timedelta(days=30),
        billing_cycle="monthly",
    )
    db_session.add(sub)
    db_session.commit()
    db_session.refresh(sub)
    return sub


# Test data constants
TEST_METRICS = {
    "dau": 10000,
    "mau": 50000,
    "retention": 0.32,
    "conversion": 0.045,
    "revenue": 125000.50,
    "arpu": 25.50,
}

TEST_ANOMALIES = [
    {
        "metric_name": "retention",
        "baseline_value": 0.35,
        "current_value": 0.28,
        "absolute_change": -0.07,
        "relative_change": -0.2,
        "detection_method": "z_score",
        "severity": "high",
    },
]

TEST_INVESTIGATION = {
    "question": "Why did retention drop?",
    "trigger": "anomaly",
    "anomaly_id": "test-anomaly-id",
}

TEST_RECOMMENDATION = {
    "title": "Fix onboarding flow",
    "description": "Onboarding V3 is causing drop-off",
    "priority": "P1",
    "rice_score": 850.5,
    "reach": 50000,
    "impact": 2.5,
    "confidence": 0.85,
    "effort": 3,
}