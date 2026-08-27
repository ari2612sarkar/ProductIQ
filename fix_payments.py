from db.connection import get_sync_session
from sqlalchemy import text
from datetime import datetime

with get_sync_session() as db:
    db.execute(text("UPDATE payments SET paid_at = '2026-08-01' WHERE paid_at > '2026-09-01'"))
    db.commit()
    print('Fixed payments dates')