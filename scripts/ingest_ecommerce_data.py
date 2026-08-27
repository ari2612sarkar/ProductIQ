#!/usr/bin/env python3
"""
Ingest real e-commerce behavior data from HuggingFace dataset.
Dataset: kevykibbz/ecommerce-behavior-data-from-multi-category-store_oct-nov_2019
~110M rows of events (view, cart, purchase) with users, sessions, products
"""
import logging
import os
import sys
import uuid
from collections.abc import Iterator
from datetime import datetime
from decimal import Decimal
from typing import Any

# Fix HuggingFace cache directory on Windows
os.environ["HF_HOME"] = "D:/Temp/huggingface"
os.environ["HF_DATASETS_CACHE"] = "D:/Temp/huggingface/datasets"
os.environ["HF_HUB_CACHE"] = "D:/Temp/huggingface/hub"

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import datasets
datasets.config.HF_DATASETS_CACHE = "D:/Temp/huggingface/datasets"
datasets.config.HF_HUB_CACHE = "D:/Temp/huggingface/hub"

from datasets import load_dataset
from sqlalchemy.orm import Session

from config.settings import settings
from db.connection import get_sync_session
from db.schema.models import (
    Event,
    Plan,
    User,
    UserStatus,
)
from db.schema.models import Session as SessionModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class EcommerceDataIngester:
    """Ingest e-commerce behavior data into PostgreSQL."""

    def __init__(self, sample_size: int | None = None):
        self.sample_size = sample_size or settings.data_sample_size
        self.batch_size = settings.hf_batch_size
        self.user_cache: dict[str, uuid.UUID] = {}
        self.session_cache: dict[str, uuid.UUID] = {}
        self.product_cache: dict[int, uuid.UUID] = {}
        self.plan_cache: dict[str, uuid.UUID] = {}
        self.stats = {
            "users": 0,
            "sessions": 0,
            "events": 0,
            "products": 0,
        }

    def load_dataset(self) -> Iterator[dict[str, Any]]:
        """Load and stream the HuggingFace dataset."""
        logger.info(f"Loading dataset: {settings.hf_dataset_name}")

        dataset = load_dataset(
            settings.hf_dataset_name,
            split=settings.hf_split,
            streaming=settings.hf_streaming,
        )

        count = 0
        for row in dataset:
            if self.sample_size and count >= self.sample_size:
                break
            yield self._transform_row(row)
            count += 1

            if count % 10000 == 0:
                logger.info(f"Processed {count} rows...")

    def _transform_row(self, row: dict[str, Any]) -> dict[str, Any]:
        """Transform raw dataset row to our schema."""
        # Parse timestamp
        event_time = row.get("event_time")
        if isinstance(event_time, str):
            timestamp = datetime.fromisoformat(event_time.replace("Z", "+00:00"))
        else:
            timestamp = event_time

        # Map event types
        event_type_map = {
            "view": "page_view",
            "cart": "add_to_cart",
            "remove_from_cart": "remove_from_cart",
            "purchase": "purchase",
        }
        event_name = event_type_map.get(row.get("event_type", "view"), "page_view")

        # Extract properties
        properties = {
            "product_id": row.get("product_id"),
            "category_id": row.get("category_id"),
            "category_code": row.get("category_code"),
            "brand": row.get("brand"),
            "price": float(row.get("price", 0)) if row.get("price") else 0,
        }

        return {
            "event_time": timestamp,
            "event_name": event_name,
            "user_id": row.get("user_id"),
            "user_session": row.get("user_session"),
            "properties": properties,
        }

    def _get_or_create_user(self, session: Session, external_id: str) -> uuid.UUID:
        """Get or create user from external ID."""
        if external_id in self.user_cache:
            return self.user_cache[external_id]

        # Check if user exists
        user = session.query(User).filter(User.email == f"user_{external_id}@example.com").first()
        if user:
            self.user_cache[external_id] = user.id
            return user.id

        # Create new user
        user_id = uuid.uuid4()
        user = User(
            id=user_id,
            email=f"user_{external_id}@example.com",
            plan_id=self._get_default_plan(session),
            acquisition_channel="organic",
            segment="ecommerce_customer",
            status=UserStatus.ACTIVE,
            first_seen_at=datetime.utcnow(),
            metadata_={"external_id": external_id},
        )
        session.add(user)
        session.flush()

        self.user_cache[external_id] = user_id
        self.stats["users"] += 1
        return user_id

    def _get_or_create_session(self, session: Session, user_id: uuid.UUID, external_session_id: str) -> uuid.UUID:
        """Get or create session from external ID."""
        cache_key = f"{user_id}:{external_session_id}"
        if cache_key in self.session_cache:
            return self.session_cache[cache_key]

        # Create new session
        try:
            sess_id = uuid.UUID(external_session_id) if self._is_uuid(external_session_id) else uuid.uuid4()
        except ValueError:
            sess_id = uuid.uuid4()

        sess = SessionModel(
            id=sess_id,
            user_id=user_id,
            started_at=datetime.utcnow(),
            device_type="desktop",
            platform="web",
            country="US",
        )
        session.add(sess)
        session.flush()

        self.session_cache[cache_key] = sess_id
        self.stats["sessions"] += 1
        return sess_id

    def _is_uuid(self, val: str) -> bool:
        """Check if string is a valid UUID."""
        try:
            uuid.UUID(val)
            return True
        except ValueError:
            return False

    def _get_or_create_product(self, session: Session, row_props: dict) -> uuid.UUID | None:
        """Product model doesn't exist, return None."""
        return None

    def _get_default_plan(self, session: Session) -> uuid.UUID:
        """Get or create default plan."""
        if "default" in self.plan_cache:
            return self.plan_cache["default"]

        # Use existing "Free" plan
        plan = session.query(Plan).filter(Plan.name == "Free").first()
        if not plan:
            # Fallback to first available plan
            plan = session.query(Plan).first()
        
        if not plan:
            raise RuntimeError("No plans available in database. Run derive_subscriptions.py first.")
        
        self.plan_cache["default"] = plan.id
        return plan.id

    def ingest(self) -> None:
        """Main ingestion method."""
        logger.info(f"Starting ingestion (sample size: {self.sample_size})")

        with get_sync_session() as session:
            batch = []

            for row in self.load_dataset():
                try:
                    # Get or create user
                    user_id = self._get_or_create_user(session, row["user_id"])

                    # Get or create session
                    session_id = self._get_or_create_session(session, user_id, row["user_session"])

                    # Create event
                    event = Event(
                        user_id=user_id,
                        session_id=session_id,
                        event_name=row["event_name"],
                        event_properties=row["properties"],
                        timestamp=row["event_time"],
                    )
                    session.add(event)
                    batch.append(event)
                    self.stats["events"] += 1

                    # Flush batch
                    if len(batch) >= self.batch_size:
                        session.flush()
                        batch = []
                        logger.info(f"Stats: {self.stats}")

                except Exception as e:
                    logger.error(f"Error processing row: {e}")
                    session.rollback()
                    # Re-create caches since rolled back
                    self.user_cache.clear()
                    self.session_cache.clear()
                    continue

            # Flush remaining
            if batch:
                session.flush()

            session.commit()
            logger.info(f"Final stats: {self.stats}")


def main():
    """Main entry point."""
    import argparse
    parser = argparse.ArgumentParser(description="Ingest e-commerce data")
    parser.add_argument("--sample", type=int, default=None, help="Sample size (default: from settings)")
    parser.add_argument("--batch-size", type=int, default=10000, help="Batch size")
    args = parser.parse_args()

    ingester = EcommerceDataIngester(sample_size=args.sample)
    ingester.batch_size = args.batch_size
    ingester.ingest()


if __name__ == "__main__":
    main()
