from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import settings

# Usamos pool_pre_ping para prevenir quedas de conexões inativas no pool
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db() -> Generator:
    """
    Dependência do FastAPI para obter uma sessão do banco de dados por requisição,
    garantindo o fechamento automático após o término.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
