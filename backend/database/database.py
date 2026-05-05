from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from backend.config import settings
import logging
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit



def _normalize_database_url(raw_url: str) -> str:
	url = (raw_url or "").strip().strip('"').strip("'")
	if not url:
		raise ValueError("DATABASE_URL is required")

	parts = urlsplit(url)
	if parts.scheme.startswith("postgresql"):
		query = dict(parse_qsl(parts.query, keep_blank_values=True))
		query.setdefault("sslmode", "require")
		url = urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))

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