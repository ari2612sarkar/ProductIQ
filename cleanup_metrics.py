from db.connection import get_sync_session
from sqlalchemy import text

with get_sync_session() as db:
    db.execute(text("DELETE FROM metric_snapshots WHERE metric_name = 'revenue' AND period_start > '2026-09-01'"))
    db.commit()
    print('Cleaned up bad revenue metrics')