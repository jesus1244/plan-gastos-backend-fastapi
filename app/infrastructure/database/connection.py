from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.infrastructure.database.config import settings

engine = create_engine(
	settings.database_url,
	pool_pre_ping=True,
	connect_args={'connect_timeout': 5},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
