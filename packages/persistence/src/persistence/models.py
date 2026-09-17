"""SQLAlchemy 2.0 declarative models (see README for the table list).

TODO:
- Base = DeclarativeBase subclass.
- One mapped class per table, tenant_id on every domain table.
- external_signals: scope_type, scope_key, signal_type, value, observed_at, source. NO user column.
- recommendations.status with CHECK constraints (migration adds trigger).
"""
