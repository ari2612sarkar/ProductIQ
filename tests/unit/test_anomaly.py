"""
Unit tests for anomaly detection.
"""
import pytest
from datetime import datetime, timedelta, date
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db.schema.models import MetricSnapshot
from analytics.anomaly.detector import AnomalyDetector


@pytest.fixture
def db_engine():
    from sqlalchemy import create_engine
    from db.connection import Base
    from db.schema.models import Base as ModelsBase
    engine = create_engine("sqlite:///:memory:")
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


class TestAnomalyDetector:
    """Tests for anomaly detection algorithms."""

    def setup_method(self):
        self.detector = None

    def create_detector(self, db_session):
        self.detector = AnomalyDetector(db_session)

    def test_z_score_detection(self, db_session):
        """Test Z-score based anomaly detection."""
        # Create metric snapshots with a clear anomaly
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

    def test_rolling_mean_detection(self, db_session):
        """Test rolling mean anomaly detection."""
        for i in range(30):
            value = 100.0
            if i >= 25:  # Sudden shift at day 25
                value = 150.0

            snapshot = MetricSnapshot(
                metric_name="revenue",
                period_start=datetime.combine(date.today() - timedelta(days=29-i), datetime.min.time()),
                period_end=datetime.combine(date.today() - timedelta(days=28-i), datetime.min.time()),
                value=value,
                sample_size=1000,
            )
            db_session.add(snapshot)
        db_session.commit()

        detector = AnomalyDetector(db_session)
        anomalies = detector.detect_rolling_mean("revenue", window=7, threshold_pct=0.2)

        assert len(anomalies) > 0

    def test_no_false_positives_on_stable_data(self, db_session):
        """Test that stable data doesn't produce false positives."""
        for i in range(30):
            value = 100.0 + (i * 0.01)  # Very slight gradual increase

            snapshot = MetricSnapshot(
                metric_name="stable_metric",
                period_start=datetime.combine(date.today() - timedelta(days=29-i), datetime.min.time()),
                period_end=datetime.combine(date.today() - timedelta(days=28-i), datetime.min.time()),
                value=value,
                sample_size=1000,
            )
            db_session.add(snapshot)
        db_session.commit()

        detector = AnomalyDetector(db_session)
        anomalies = detector.detect_z_score("stable_metric", window=14, threshold=2.0)

        # Should not detect anomalies in stable data
        assert len(anomalies) == 0