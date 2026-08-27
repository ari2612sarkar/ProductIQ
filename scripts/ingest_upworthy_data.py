#!/usr/bin/env python3
"""
Ingest Upworthy A/B test data from the Upworthy Research Archive.
Dataset: 32,487 experiments, 150,817 experiment arms, 538M participant assignments
Available at: https://osf.io/jd64p/download
"""
import csv
import logging
import os
import sys
import uuid
import zipfile
from collections.abc import Iterator
from datetime import datetime
from decimal import Decimal
from typing import Any

import requests

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session

from db.connection import get_sync_session
from db.schema.models import Experiment, ExperimentAssignment, ExperimentStatus, ExperimentVariant, User, UserStatus

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class UpworthyDataIngester:
    """Ingest Upworthy A/B test data into PostgreSQL."""

    def __init__(self, sample_size: int | None = None):
        self.sample_size = sample_size
        self.batch_size = 1000
        self.experiment_cache: dict[str, uuid.UUID] = {}
        self.user_cache: dict[str, uuid.UUID] = {}
        self.stats = {
            "experiments": 0,
            "assignments": 0,
            "arms": 0,
            "users": 0,
        }

    def download_dataset(self) -> str:
        """Download the Upworthy dataset from OSF with progress."""
        url = "https://osf.io/jd64p/download"
        logger.info(f"Downloading Upworthy dataset from {url}")

        response = requests.get(url, stream=True, timeout=600)  # 10 min timeout
        response.raise_for_status()

        total_size = int(response.headers.get('content-length', 0))
        temp_path = "/tmp/upworthy_data.zip"
        
        logger.info(f"File size: {total_size / 1024 / 1024:.1f} MB")
        
        downloaded = 0
        with open(temp_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0 and downloaded % (1024 * 1024) == 0:  # Log every MB
                        pct = (downloaded / total_size) * 100
                        logger.info(f"Downloaded: {downloaded / 1024 / 1024:.1f} MB / {total_size / 1024 / 1024:.1f} MB ({pct:.1f}%)")

        logger.info(f"Downloaded to {temp_path}")
        return temp_path

    def extract_csv(self, zip_path: str) -> str:
        """Extract CSV from zip file."""
        extract_dir = "/tmp/upworthy_extracted"
        os.makedirs(extract_dir, exist_ok=True)

        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(extract_dir)

        # Find CSV file
        for root, dirs, files in os.walk(extract_dir):
            for file in files:
                if file.endswith(".csv"):
                    csv_path = os.path.join(root, file)
                    logger.info(f"Found CSV: {csv_path}")
                    return csv_path

        raise FileNotFoundError("No CSV file found in extracted data")

    def load_csv(self, csv_path: str) -> Iterator[dict[str, Any]]:
        """Load and parse the Upworthy CSV with progress."""
        logger.info(f"Loading CSV: {csv_path}")

        with open(csv_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            count = 0
            for row in reader:
                if self.sample_size and count >= self.sample_size:
                    break
                yield self._transform_row(row)
                count += 1

                if count % 5000 == 0:
                    logger.info(f"Processed {count} rows...")

    def _transform_row(self, row: dict[str, Any]) -> dict[str, Any]:
        """Transform Upworthy CSV row to our schema."""
        # Upworthy columns: created_at, test_week, clickability_test_id, impressions,
        # headline, eyecatcher_id, excerpt, clicks

        test_id = row.get("clickability_test_id", "")
        impressions = int(row.get("impressions", 0))
        clicks = int(row.get("clicks", 0))

        # Parse date
        created_at_str = row.get("created_at", "")
        try:
            created_at = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
        except ValueError:
            created_at = datetime.utcnow()

        return {
            "test_id": test_id,
            "impressions": impressions,
            "clicks": clicks,
            "headline": row.get("headline", ""),
            "eyecatcher_id": row.get("eyecatcher_id", ""),
            "excerpt": row.get("excerpt", ""),
            "created_at": created_at,
            "ctr": clicks / impressions if impressions > 0 else 0,
        }

    def _get_or_create_user(self, session: Session, upworthy_user_id: str) -> uuid.UUID:
        """Get or create user from Upworthy user ID."""
        if upworthy_user_id in self.user_cache:
            return self.user_cache[upworthy_user_id]

        # Check if user exists
        user = session.query(User).filter(User.email == f"upworthy_{upworthy_user_id}@upworthy.com").first()
        if user:
            self.user_cache[upworthy_user_id] = user.id
            return user.id

        # Create new user
        user_id = uuid.uuid5(uuid.NAMESPACE_DNS, f"upworthy_user_{upworthy_user_id}")
        user = User(
            id=user_id,
            email=f"upworthy_{upworthy_user_id}@upworthy.com",
            acquisition_channel="upworthy",
            segment="upworthy_participant",
            status=UserStatus.ACTIVE,
            first_seen_at=datetime.utcnow(),
            metadata_={"upworthy_user_id": upworthy_user_id},
        )
        session.add(user)
        session.flush()

        self.user_cache[upworthy_user_id] = user_id
        self.stats["users"] += 1
        return user_id

    def _get_or_create_experiment(self, session: Session, test_id: str, first_row: dict) -> uuid.UUID:
        """Get or create experiment from test_id."""
        if test_id in self.experiment_cache:
            return self.experiment_cache[test_id]

        exp = session.query(Experiment).filter(
            Experiment.metadata_["upworthy_test_id"].astext == test_id
        ).first()

        if not exp:
            exp_id = uuid.uuid5(uuid.NAMESPACE_DNS, f"upworthy_{test_id}")
            exp = Experiment(
                id=exp_id,
                name=f"Upworthy Headline Test {test_id}",
                hypothesis="Testing headline variations for click-through rate optimization",
                description=f"Upworthy A/B test {test_id} with {first_row.get('impressions', 0)} impressions",
                status=ExperimentStatus.COMPLETED,
                started_at=first_row["created_at"],
                ended_at=first_row["created_at"],  # Approximate
                control_variant="control",
                treatment_variant="treatment",
                traffic_allocation=Decimal("0.5"),
                target_metric="click_through_rate",
                metadata_={
                    "upworthy_test_id": test_id,
                    "source": "upworthy_research_archive",
                    "eyecatcher_id": first_row.get("eyecatcher_id"),
                },
            )
            session.add(exp)
            session.flush()
            self.stats["experiments"] += 1

        self.experiment_cache[test_id] = exp.id
        return exp.id

    def _create_experiment_arms(self, session: Session, experiment_id: uuid.UUID, rows: list[dict]) -> None:
        """Create experiment arms (variants) from rows with same test_id using bulk insert."""
        assignments = []
        for i, row in enumerate(rows):
            variant = ExperimentVariant.CONTROL if i == 0 else ExperimentVariant.TREATMENT

            # Create/get user for this variant
            upworthy_user_id = f"{row['test_id']}_{i}"
            user_id = self._get_or_create_user(session, upworthy_user_id)

            assignment = ExperimentAssignment(
                experiment_id=experiment_id,
                user_id=user_id,
                variant=variant,
                assigned_at=row["created_at"],
                exposed_at=row["created_at"],
            )
            assignments.append(assignment)
        
        # Bulk insert all assignments at once
        session.bulk_save_objects(assignments)
        self.stats["assignments"] += len(assignments)
        self.stats["arms"] += len(assignments)

    def ingest(self) -> None:
        """Main ingestion method."""
        logger.info("Starting Upworthy data ingestion")

        # Check if we have a local CSV or need to download
        csv_path = os.environ.get("UPWORTHY_CSV_PATH")

        if not csv_path:
            # Try to download
            try:
                zip_path = self.download_dataset()
                csv_path = self.extract_csv(zip_path)
            except Exception as e:
                logger.error(f"Failed to download Upworthy dataset: {e}")
                logger.info("Please download manually from https://osf.io/jd64p/download and set UPWORTHY_CSV_PATH")
                return

        if not os.path.exists(csv_path):
            logger.error(f"CSV not found: {csv_path}")
            return

        with get_sync_session() as session:
            # Check if data already exists
            existing_count = session.query(Experiment).filter(
                Experiment.metadata_["source"].astext == "upworthy_research_archive"
            ).count()
            
            if existing_count > 0:
                logger.info(f"Found {existing_count} existing Upworthy experiments. Skipping ingestion.")
                logger.info("Set UPWORTHY_CSV_PATH and delete existing data to re-ingest.")
                return

            # Group rows by test_id
            test_groups: dict[str, list[dict]] = {}

            for row in self.load_csv(csv_path):
                test_id = row["test_id"]
                if test_id not in test_groups:
                    test_groups[test_id] = []
                test_groups[test_id].append(row)

            # Process each experiment
            for test_id, rows in test_groups.items():
                try:
                    experiment_id = self._get_or_create_experiment(session, test_id, rows[0])
                    self._create_experiment_arms(session, experiment_id, rows)

                    if len(self.experiment_cache) % 50 == 0:
                        session.flush()
                        logger.info(f"Stats: {self.stats}")

                except Exception as e:
                    logger.error(f"Error processing experiment {test_id}: {e}")
                    session.rollback()
                    continue

            session.commit()
            logger.info(f"Final stats: {self.stats}")


def main():
    """Main entry point."""
    import argparse
    parser = argparse.ArgumentParser(description="Ingest Upworthy A/B test data")
    parser.add_argument("--sample", type=int, default=None, help="Sample size")
    parser.add_argument("--csv-path", type=str, default=None, help="Path to CSV file")
    args = parser.parse_args()

    if args.csv_path:
        os.environ["UPWORTHY_CSV_PATH"] = args.csv_path

    ingester = UpworthyDataIngester(sample_size=args.sample)
    ingester.ingest()


if __name__ == "__main__":
    main()
