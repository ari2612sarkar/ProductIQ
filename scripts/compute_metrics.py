#!/usr/bin/env python3
"""Compute and populate metric snapshots from event data."""
from datetime import datetime, timedelta
from decimal import Decimal
import uuid
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.connection import get_sync_session
from sqlalchemy import text


def main():
    with get_sync_session() as db:
        # Compute DAU from events
        print("Computing DAU...")
        result = db.execute(text("""
            SELECT DATE(timestamp) as date, COUNT(DISTINCT user_id) as dau
            FROM events
            GROUP BY DATE(timestamp)
        """))
        for row in result:
            print(f"  DAU: {row.date} = {row.dau}")
            db.execute(text("""
                INSERT INTO metric_snapshots (id, metric_name, period_start, period_end, value, sample_size, dimensions)
                VALUES (:id, :metric_name, :period_start, :period_end, :value, :sample_size, :dimensions)
                ON CONFLICT (metric_name, period_start, dimensions) DO UPDATE SET value = :value
            """), {
                "id": uuid.uuid4(),
                "metric_name": "dau",
                "period_start": row.date,
                "period_end": row.date + timedelta(days=1),
                "value": Decimal(str(row.dau)),
                "sample_size": row.dau,
                "dimensions": "{}"
            })

        # Compute MAU
        print("Computing MAU...")
        result = db.execute(text("""
            SELECT DATE_TRUNC('month', timestamp)::date as month_start, COUNT(DISTINCT user_id) as mau
            FROM events
            GROUP BY DATE_TRUNC('month', timestamp)
        """))
        for row in result:
            print(f"  MAU: {row.month_start} = {row.mau}")
            db.execute(text("""
                INSERT INTO metric_snapshots (id, metric_name, period_start, period_end, value, sample_size, dimensions)
                VALUES (:id, :metric_name, :period_start, :period_end, :value, :sample_size, :dimensions)
                ON CONFLICT (metric_name, period_start, dimensions) DO UPDATE SET value = :value
            """), {
                "id": uuid.uuid4(),
                "metric_name": "mau",
                "period_start": row.month_start,
                "period_end": row.month_start + timedelta(days=30),
                "value": Decimal(str(row.mau)),
                "sample_size": row.mau,
                "dimensions": "{}"
            })

        # Compute retention (simplified)
        print("Computing retention...")
        result = db.execute(text("""
            WITH user_cohorts AS (
                SELECT user_id, DATE_TRUNC('month', MIN(timestamp))::date as cohort_month
                FROM events
                GROUP BY user_id
            ),
            user_activity AS (
                SELECT uc.cohort_month,
                       DATE_TRUNC('month', e.timestamp)::date as activity_month,
                       COUNT(DISTINCT e.user_id) as active_users
                FROM user_cohorts uc
                JOIN events e ON uc.user_id = e.user_id
                GROUP BY uc.cohort_month, DATE_TRUNC('month', e.timestamp)
            )
            SELECT cohort_month, activity_month, active_users,
                   LAG(active_users) OVER (PARTITION BY cohort_month ORDER BY activity_month) as prev_month_users,
                   CASE 
                       WHEN LAG(active_users) OVER (PARTITION BY cohort_month ORDER BY activity_month) > 0
                       THEN ROUND(active_users::numeric / LAG(active_users) OVER (PARTITION BY cohort_month ORDER BY activity_month) * 100, 2)
                   END as retention_rate_pct
            FROM user_activity
        """))
        for row in result:
            if row.retention_rate_pct is not None:
                print(f"  Retention: {row.cohort_month} -> {row.activity_month} = {row.retention_rate_pct}%")
                db.execute(text("""
                    INSERT INTO metric_snapshots (id, metric_name, period_start, period_end, value, sample_size, dimensions)
                    VALUES (:id, :metric_name, :period_start, :period_end, :value, :sample_size, :dimensions)
                    ON CONFLICT (metric_name, period_start, dimensions) DO UPDATE SET value = :value
                """), {
                    "id": uuid.uuid4(),
                    "metric_name": "retention",
                    "period_start": row.activity_month,
                    "period_end": row.activity_month + timedelta(days=30),
                    "value": Decimal(str(row.retention_rate_pct)),
                    "sample_size": row.active_users,
                    "dimensions": f'{{\"cohort\": \"{row.cohort_month}\"}}'
                })

        # Compute revenue from payments
        print("Computing revenue...")
        result = db.execute(text("""
            SELECT DATE_TRUNC('month', paid_at)::date as month_start, SUM(amount) as revenue
            FROM payments
            WHERE status = 'succeeded' AND paid_at IS NOT NULL
            GROUP BY DATE_TRUNC('month', paid_at)
        """))
        for row in result:
            print(f"  Revenue: {row.month_start} = {row.revenue}")
            db.execute(text("""
                INSERT INTO metric_snapshots (id, metric_name, period_start, period_end, value, sample_size, dimensions)
                VALUES (:id, :metric_name, :period_start, :period_end, :value, :sample_size, :dimensions)
                ON CONFLICT (metric_name, period_start, dimensions) DO UPDATE SET value = :value
            """), {
                "id": uuid.uuid4(),
                "metric_name": "revenue",
                "period_start": row.month_start,
                "period_end": row.month_start + timedelta(days=30),
                "value": Decimal(str(row.revenue)),
                "sample_size": 1,
                "dimensions": "{}"
            })

        db.commit()
        print("Done!")


if __name__ == "__main__":
    main()