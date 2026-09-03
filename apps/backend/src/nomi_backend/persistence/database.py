from __future__ import annotations

import os
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from dotenv import load_dotenv

load_dotenv() 

DEFAULT_DATABASE_URL = "sqlite:///./nomi_verification.db?sslmode=require"


def get_database_url() -> str:
  return os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)


def create_db_engine(database_url: str | None = None):
  url = database_url or get_database_url()
  connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
  return create_engine(url, future=True, connect_args=connect_args)


engine = create_db_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_session() -> Generator[Session, None, None]:
  session = SessionLocal()
  try:
    yield session
  finally:
    session.close()
