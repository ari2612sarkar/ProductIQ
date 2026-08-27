#!/usr/bin/env python3
"""
Refresh materialized views for analytical queries.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging

from sqlalchemy import text

from db.connection import sync_engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    """Refresh all materialized views."""
    views = [
        "mv_dau",
        "mv_wau",
        "mv_mau",
        "mv_cohort_retention",
    ]

    with sync_engine.connect() as conn:
        for view in views:
            try:
                logger.info(f"Refreshing {view}...")
                conn.execute(text(f"REFRESH MATERIALIZED VIEW {view};"))
                conn.commit()
                logger.info(f"  Refreshed {view}")
            except Exception as e:
                logger.error(f"  Failed to refresh {view}: {e}")
                conn.rollback()

    logger.info("Materialized view refresh complete!")


if __name__ == "__main__":
    main()
