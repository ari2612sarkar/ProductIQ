"""
Unit tests for metric calculations.
"""
import pytest
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db.schema.models import User, Event, Subscription
from analytics.metrics.calculator import MetricCalculator
from analytics.anomaly.detector import AnomalyDetector


@pytest.fixture
def db_engine():
    engine = create_engine("sqlite:///:memory:")
    from db.connection import Base
    from db.schema.models import Base as ModelsBase
    ModelsBase.metadata.create_all(engine)
    return engine


@pytest.fixture
def db_session(db_engine):
    SessionLocal = sessionmaker(bind=db_engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


class TestMetricCalculator:
    """Tests for metric calculations."""

    def test_dau_calculation(self, db_session):
        """Test DAU calculation."""
        # Create test users and events
        users = []
        for i in range(10):
            user = User(email=f"user{i}@test.com", acquisition_channel="organic")
            users.append(user)
        db_session.add_all(users)
        db_session.commit()

        # Create events for today
        today = datetime.utcnow().date()
        for i, user in enumerate(users):
            event = Event(
                user_id=user.id,
                event_name="page_view",
                event_properties={},
                timestamp=datetime.combine(today, datetime.min.time()) + timedelta(hours=i),
            )
            db_session.add(event)
        db_session.commit()

        calculator = MetricCalculator(db_session)
        dau = calculator.calculate_dau(today)
        assert dau == 10

    def test_retention_calculation(self, db_session):
        """Test retention calculation."""
        # Create cohort of users who signed up 30 days ago
        cohort_date = datetime.utcnow().date() - timedelta(days=30)

        users = []
        for i in range(20):
            user = User(
                email=f"retention{i}@test.com",
                acquisition_channel="organic",
            )
            user.created_at = datetime.combine(cohort_date, datetime.min.time())
            users.append(user)
        db_session.add_all(users)
        db_session.commit()

        # 10 users active on day 30
        for i in range(10):
            event = Event(
                user_id=users[i].id,
                event_name="page_view",
                event_properties={},
                timestamp=datetime.utcnow() - timedelta(hours=i),
            )
            db_session.add(event)
        db_session.commit()

        calculator = MetricCalculator(db_session)
        retention = calculator.calculate_n_day_retention(30, cohort_date)
        assert retention == 0.5  # 10/20


class TestAnomalyDetector:
    """Tests for anomaly detection."""

    def test_z_score_detection(self, db_session):
        """Test Z-score based anomaly detection."""
        # Create metric snapshots with a clear anomaly
        from db.schema.models import MetricSnapshot
        from datetime import date

        for i in range(30):
            value = 100 + (i * 0.1)  # Gradual increase
            if i == 25:  # Anomaly on day 25
                value = 200  # Spike

            snapshot = MetricSnapshot(
                metric_name="test_metric",
                period_start=datetime.combine(date.today() - timedelta(days=29-i), datetime.min.time()),
                period_end=datetime.combine(date.today() - timedelta(days=28-i), datetime.min.time()),
                value=value,
                sample_size=1000,
            )
            db_session.add(snapshot)
        db_session.commit()

        detector = AnomalyDetector(db_session)
        anomalies = detector.detect_z_score("test_metric", window=14, threshold=2.0)

        # Should detect the spike
        assert len(anomalies) > 0
        assert any(a.current_value == 200 for a in anomalies)

    def test_percentage_change_detection(self, db_session):
        """Test percentage change anomaly detection."""
        from db.schema.models import MetricSnapshot
        from datetime import date

        for i in range(30):
            value = 100.0
            if i == 29:  # Last day has 50% drop
                value = 50.0

            snapshot = MetricSnapshot(
                metric_name="conversion_rate",
                period_start=datetime.combine(date.today() - timedelta(days=29-i), datetime.min.time()),
                period_end=datetime.combine(date.today() - timedelta(days=28-i), datetime.min.time()),
                value=value,
                sample_size=1000,
            )
            db_session.add(snapshot)
        db_session.commit()

        detector = AnomalyDetector(db_session)
        anomalies = detector.detect_percentage_change("conversion_rate", threshold_pct=0.3)

        assert len(anomalies) > 0
        assert anomalies[0].relative_change < -0.3