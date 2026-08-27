#!/usr/bin/env python3
"""
Database initialization script.
Creates tables, indexes, and sets up read-only role for SQL agent.
"""
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text

from db.connection import init_db, sync_engine


def create_readonly_role() -> None:
    """Create read-only role for SQL agent."""
    with sync_engine.connect() as conn:
        # Create read-only role
        conn.execute(text("""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'readonly') THEN
                    CREATE ROLE readonly WITH LOGIN PASSWORD 'readonly';
                END IF;
            END
            $$;
        """))

        # Grant usage on schema
        conn.execute(text("GRANT USAGE ON SCHEMA public TO readonly;"))

        # Grant select on all tables
        conn.execute(text("GRANT SELECT ON ALL TABLES IN SCHEMA public TO readonly;"))

        # Grant select on all sequences
        conn.execute(text("GRANT SELECT ON ALL SEQUENCES IN SCHEMA public TO readonly;"))

        # Set default privileges for future tables
        conn.execute(text("""
            ALTER DEFAULT PRIVILEGES IN SCHEMA public
            GRANT SELECT ON TABLES TO readonly;
        """))

        conn.execute(text("""
            ALTER DEFAULT PRIVILEGES IN SCHEMA public
            GRANT SELECT ON SEQUENCES TO readonly;
        """))

        conn.commit()
        print("Read-only role created and granted SELECT permissions")


def create_indexes() -> None:
    """Create additional indexes for analytical queries."""
    indexes = [
        # User segmentation indexes
        "CREATE INDEX IF NOT EXISTS ix_users_segment_status ON users(segment, status);",
        "CREATE INDEX IF NOT EXISTS ix_users_acquisition_channel ON users(acquisition_channel);",

        # Event analytics indexes
        "CREATE INDEX IF NOT EXISTS ix_events_properties_gin ON events USING GIN(event_properties);",

        # Subscription analytics
        "CREATE INDEX IF NOT EXISTS ix_subscriptions_plan_status ON subscriptions(plan_id, status);",
        "CREATE INDEX IF NOT EXISTS ix_subscriptions_started ON subscriptions(started_at);",

        # Payment analytics
        "CREATE INDEX IF NOT EXISTS ix_payments_amount ON payments(amount);",

        # Experiment analytics
        "CREATE INDEX IF NOT EXISTS ix_experiment_assignments_assigned ON experiment_assignments(assigned_at);",

        # Feedback analytics
        "CREATE INDEX IF NOT EXISTS ix_product_feedback_rating ON product_feedback(rating);",
        "CREATE INDEX IF NOT EXISTS ix_support_tickets_priority ON support_tickets(priority);",

        # Metric snapshots
        "CREATE INDEX IF NOT EXISTS ix_metric_snapshots_dimensions ON metric_snapshots USING GIN(dimensions);",
    ]

    with sync_engine.connect() as conn:
        for idx_sql in indexes:
            try:
                conn.execute(text(idx_sql))
                print(f"Created index: {idx_sql.split('IF NOT EXISTS ')[1].split(' ')[0]}")
            except Exception as e:
                print(f"Index creation warning: {e}")
        conn.commit()


def create_materialized_views() -> None:
    """Create materialized views for common analytical queries."""
    views = [
        # Daily active users
        """
        CREATE MATERIALIZED VIEW IF NOT EXISTS mv_dau AS
        SELECT 
            DATE(timestamp) as date,
            COUNT(DISTINCT user_id) as dau
        FROM events
        GROUP BY DATE(timestamp)
        WITH NO DATA;
        """,

        # Weekly active users
        """
        CREATE MATERIALIZED VIEW IF NOT EXISTS mv_wau AS
        SELECT 
            DATE_TRUNC('week', timestamp)::date as week_start,
            COUNT(DISTINCT user_id) as wau
        FROM events
        GROUP BY DATE_TRUNC('week', timestamp)
        WITH NO DATA;
        """,

        # Monthly active users
        """
        CREATE MATERIALIZED VIEW IF NOT EXISTS mv_mau AS
        SELECT 
            DATE_TRUNC('month', timestamp)::date as month_start,
            COUNT(DISTINCT user_id) as mau
        FROM events
        GROUP BY DATE_TRUNC('month', timestamp)
        WITH NO DATA;
        """,

        # User cohort retention
        """
        CREATE MATERIALIZED VIEW IF NOT EXISTS mv_cohort_retention AS
        WITH user_cohorts AS (
            SELECT 
                user_id,
                DATE_TRUNC('month', MIN(timestamp))::date as cohort_month
            FROM events
            GROUP BY user_id
        ),
        user_activity AS (
            SELECT 
                uc.cohort_month,
                DATE_TRUNC('month', e.timestamp)::date as activity_month,
                COUNT(DISTINCT e.user_id) as active_users
            FROM user_cohorts uc
            JOIN events e ON uc.user_id = e.user_id
            GROUP BY uc.cohort_month, DATE_TRUNC('month', e.timestamp)
        )
        SELECT 
            cohort_month,
            activity_month,
            active_users,
            LAG(active_users) OVER (PARTITION BY cohort_month ORDER BY activity_month) as prev_month_users,
            CASE 
                WHEN LAG(active_users) OVER (PARTITION BY cohort_month ORDER BY activity_month) > 0
                THEN ROUND(active_users::numeric / LAG(active_users) OVER (PARTITION BY cohort_month ORDER BY activity_month) * 100, 2)
            END as retention_rate_pct
        FROM user_activity
        WITH NO DATA;
        """,
    ]

    with sync_engine.connect() as conn:
        for view_sql in views:
            try:
                conn.execute(text(view_sql))
                print("Created materialized view")
            except Exception as e:
                print(f"Materialized view warning: {e}")
        conn.commit()


def refresh_materialized_views() -> None:
    """Refresh all materialized views."""
    views = ["mv_dau", "mv_wau", "mv_mau", "mv_cohort_retention"]
    with sync_engine.connect() as conn:
        for view in views:
            try:
                conn.execute(text(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {view};"))
                print(f"Refreshed {view}")
            except Exception as e:
                print(f"Refresh warning for {view}: {e}")
        conn.commit()


def main() -> None:
    print("Initializing database...")

    # Create tables
    print("Creating tables...")
    init_db()
    print("Tables created successfully")

    # Create read-only role
    print("Setting up read-only role...")
    create_readonly_role()

    # Create additional indexes
    print("Creating additional indexes...")
    create_indexes()

    # Create materialized views
    print("Creating materialized views...")
    create_materialized_views()

    print("\nDatabase initialization complete!")
    print("Run 'python scripts/refresh_mviews.py' to refresh materialized views after data load")


if __name__ == "__main__":
    main()
