from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from backend.config import settings
import logging


def _normalize_database_url(raw_url: str) -> str:
	url = (raw_url or "").strip().strip('"').strip("'")
	if not url:
		raise ValueError("DATABASE_URL is required")
	
	if url.startswith("postgresql") and "sslmode=" not in url:
		separator = "&" if "?" in url else "?"
		url = url + separator + "sslmode=require"
	
	return url


DATABASE_URL = _normalize_database_url(settings.DATABASE_URL)

logging.basicConfig(level=logging.INFO)
logging.info("Database Connected")
engine_kwargs = {
	"pool_pre_ping": True,
}

# Keep startup responsive on platforms like Render when DB is temporarily unreachable.
if DATABASE_URL.startswith("postgresql"):
	engine_kwargs["connect_args"] = {"connect_timeout": 5}

engine = create_engine(DATABASE_URL, **engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()