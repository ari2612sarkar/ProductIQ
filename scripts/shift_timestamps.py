#!/usr/bin/env python3
"""Shift event timestamps to recent dates for dashboard."""
from datetime import datetime, timedelta
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.connection import get_sync_session
from sqlalchemy import text


def main():
    with get_sync_session() as db:
        # Get the current max timestamp and shift to be recent
        # We want the data to span the last 30 days
        result = db.execute(text("SELECT MIN(timestamp), MAX(timestamp) FROM events"))
        row = result.fetchone()
        old_min = row[0]
        old_max = row[1]
        
        # Shift so max is now, min is 30 days ago
        new_max = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        new_min = new_max - timedelta(days=30)
        
        old_range = (old_max - old_min).total_seconds()
        new_range = (new_max - new_min).total_seconds()
        
        print(f"Old range: {old_min} to {old_max}")
        print(f"New range: {new_min} to {new_max}")
        
        # Shift events
        db.execute(text("""
            UPDATE events 
            SET timestamp = :new_min + (timestamp - :old_min) * :ratio,
                updated_at = now()
        """), {
            "new_min": new_min,
            "old_min": old_min,
            "ratio": new_range / old_range if old_range > 0 else 1
        })
        
        # Shift sessions
        db.execute(text("""
            UPDATE sessions 
            SET started_at = :new_min + (started_at - :old_min) * :ratio,
                updated_at = now()
            WHERE started_at IS NOT NULL
        """), {
            "new_min": new_min,
            "old_min": old_min,
            "ratio": new_range / old_range if old_range > 0 else 1
        })
        
        # Shift user first_seen_at
        db.execute(text("""
            UPDATE users 
            SET first_seen_at = :new_min + (first_seen_at - :old_min) * :ratio,
                updated_at = now()
            WHERE first_seen_at IS NOT NULL
        """), {
            "new_min": new_min,
            "old_min": old_min,
            "ratio": new_range / old_range if old_range > 0 else 1
        })
        
        # Also shift payments paid_at
        db.execute(text("""
            UPDATE payments 
            SET paid_at = :new_min + (paid_at - :old_min) * :ratio,
                updated_at = now()
            WHERE paid_at IS NOT NULL
        """), {
            "new_min": new_min,
            "old_min": old_min,
            "ratio": new_range / old_range if old_range > 0 else 1
        })
        
        # Shift experiment started_at/ended_at - skip due to timestamp overflow
        # db.execute(text("""
        #     UPDATE experiments 
        #     SET started_at = :new_min + (started_at - :old_min) * :ratio,
        #         ended_at = :new_min + (ended_at - :old_min) * :ratio,
        #         updated_at = now()
        #     WHERE started_at IS NOT NULL
        # """), {
        #     "new_min": new_min,
        #     "old_min": old_min,
        #     "ratio": new_range / old_range if old_range > 0 else 1
        # })
        
        # Shift experiment assignments - skip due to timestamp overflow
        # db.execute(text("""
        #     UPDATE experiment_assignments 
        #     SET assigned_at = :new_min + (assigned_at - :old_min) * :ratio,
        #         exposed_at = :new_min + (exposed_at - :old_min) * :ratio,
        #         updated_at = now()
        #     WHERE assigned_at IS NOT NULL
        # """), {
        #     "new_min": new_min,
        #     "old_min": old_min,
        #     "ratio": new_range / old_range if old_range > 0 else 1
        # })
        
        # Shift support tickets
        db.execute(text("""
            UPDATE support_tickets 
            SET created_at = :new_min + (created_at - :old_min) * :ratio,
                updated_at = now()
            WHERE created_at IS NOT NULL
        """), {
            "new_min": new_min,
            "old_min": old_min,
            "ratio": new_range / old_range if old_range > 0 else 1
        })
        
        # Shift product feedback
        db.execute(text("""
            UPDATE product_feedback 
            SET created_at = :new_min + (created_at - :old_min) * :ratio,
                updated_at = now()
            WHERE created_at IS NOT NULL
        """), {
            "new_min": new_min,
            "old_min": old_min,
            "ratio": new_range / old_range if old_range > 0 else 1
        })
        
        db.commit()
        print("Done!")
        
        # Verify
        result = db.execute(text("SELECT MIN(timestamp), MAX(timestamp) FROM events"))
        row = result.fetchone()
        print(f"New events range: {row[0]} to {row[1]}")


if __name__ == "__main__":
    main()