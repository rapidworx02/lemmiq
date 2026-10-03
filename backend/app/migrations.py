"""Small compatibility migrations for private-beta upgrades.

SQLAlchemy create_all() creates new tables but does not add columns to an
existing table. V2.3 voice-note tables did not include transcribed_at, so
V2.4 adds those columns safely on startup when needed.
"""
from sqlalchemy import inspect, text

def apply_compat_migrations(engine):
    inspector=inspect(engine)
    existing=set(inspector.get_table_names())
    changes=[
        ("voice_notes","transcribed_at","TIMESTAMP"),
        ("group_voice_notes","transcribed_at","TIMESTAMP"),
    ]
    for table,column,sql_type in changes:
        if table not in existing:
            continue
        cols={c["name"] for c in inspect(engine).get_columns(table)}
        if column in cols:
            continue
        # Fixed internal identifiers only; no user-controlled SQL.
        with engine.begin() as conn:
            conn.execute(text(f'ALTER TABLE "{table}" ADD COLUMN "{column}" {sql_type}'))
