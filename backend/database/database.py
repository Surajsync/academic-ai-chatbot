from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from backend.config import settings
import logging

DATABASE_URL = settings.DATABASE_URL

logging.basicConfig(level=logging.INFO)
logging.info("Database Connected")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()