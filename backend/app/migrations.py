"""Small compatibility migrations for private-beta upgrades.

SQLAlchemy ``create_all`` creates new tables but does not alter existing tables.
This module keeps upgrades additive and idempotent for both SQLite development
and PostgreSQL/Render deployments.
"""
from sqlalchemy import inspect, text


def _add_column_if_missing(engine, table: str, column: str, ddl: str) -> bool:
    inspector = inspect(engine)
    if table not in set(inspector.get_table_names()):
        return False
    cols = {c["name"] for c in inspect(engine).get_columns(table)}
    if column in cols:
        return False
    # Identifiers and DDL strings are fixed in source; no user-controlled SQL.
    with engine.begin() as conn:
        conn.execute(text(f'ALTER TABLE "{table}" ADD COLUMN "{column}" {ddl}'))
    return True


def apply_compat_migrations(engine):
    # Earlier voice-note compatibility migrations.
    _add_column_if_missing(engine, "voice_notes", "transcribed_at", "TIMESTAMP")
    _add_column_if_missing(engine, "group_voice_notes", "transcribed_at", "TIMESTAMP")

    # V2.10.6: distinguish voice and video calls without changing old history.
    _add_column_if_missing(engine, "call_records", "call_type", "VARCHAR(12) DEFAULT 'VOICE'")

    # V2.10.5: Q Predict moves new predictions from isolated Predict Credits to
    # the authoritative V2.8 Q wallet. Existing rows are explicitly marked PC
    # so historical test positions are never converted 1:1 into Q.
    wallet_unit_added = _add_column_if_missing(
        engine, "q_predict_markets", "wallet_unit", "VARCHAR(8) DEFAULT 'PC'"
    )

    # Backend-editable Q Predict limits. These are Q micros (1 Q = 1,000,000).
    _add_column_if_missing(engine, "q_predict_config", "minimum_stake_micros", "BIGINT DEFAULT 1000000")
    _add_column_if_missing(engine, "q_predict_config", "maximum_stake_micros", "BIGINT DEFAULT 100000000")
    _add_column_if_missing(engine, "q_predict_config", "per_market_limit_micros", "BIGINT DEFAULT 250000000")
    _add_column_if_missing(engine, "q_predict_config", "daily_exposure_limit_micros", "BIGINT DEFAULT 500000000")
    _add_column_if_missing(engine, "q_predict_config", "weekly_exposure_limit_micros", "BIGINT DEFAULT 1500000000")

    # Only execute the PC -> Q mode switch on the deployment where the market
    # unit column is first introduced. Subsequent restarts respect Admin choices.
    if wallet_unit_added:
        existing = set(inspect(engine).get_table_names())
        with engine.begin() as conn:
            conn.execute(text(
                "UPDATE q_predict_markets SET wallet_unit='PC' "
                "WHERE wallet_unit IS NULL OR wallet_unit=''"
            ))
            if "q_predict_config" in existing:
                conn.execute(text(
                    "UPDATE q_predict_config SET real_q_enabled=TRUE, test_mode=FALSE"
                ))
