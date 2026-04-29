"""SQLAlchemy declarative base.

Every ORM model in `backend/db/` inherits from `Base` so its table is
registered on `Base.metadata`. `alembic/env.py` imports that metadata
to autogenerate migrations.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
