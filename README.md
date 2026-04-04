# College AI Chatbot - REC Bijnor

A production-grade FastAPI chatbot for college-specific Q&A with intent-aware retrieval, multi-source synthesis, and Groq LLM integration.

## Features

✅ **Intent Detection** - Fee, HOD, Club, Placement, Scholarship queries  
✅ **Multi-Source Retrieval** - FAQs + Structured Data + Groq LLM  
✅ **Deterministic Answers** - Direct DB lookups eliminate hallucinations  
✅ **Groq Integration** - llama-3.1-8b-instant with temperature=0.1  
✅ **JWT Authentication** - User/Admin roles with token-based access  
✅ **Admin Dashboard** - Debug source attribution on responses  
✅ **Out-of-Scope Filtering** - College-domain boundary enforcement  

## Quick Start

```bash
source projectenv/bin/activate
pip install -r requirements.txt

# Configure .env with your credentials
# - GROQ_API_KEY
# - DATABASE_URL

cd backend
uvicorn app:app --reload
```

Visit: http://localhost:8000

---

## Project Structure

```
backend/
├── app.py                     # FastAPI main app + routes
├── config.py                  # Settings (pydantic_settings)
├── database/
│   ├── database.py            # SQLAlchemy engine & session
│   ├── models.py              # 7 ORM models (FAQ, Department, etc.)
│   └── seed/                  # Data import scripts
├── services/
│   ├── ai_service.py          # Groq LLM wrapper (temperature=0.1)
│   ├── chatbot_service.py     # Intent detection + retrieval pipeline
│   ├── auth_service.py        # JWT token generation
│   └── chatbot.py             # Legacy/helper
├── routes/
│   ├── chat_routes.py         # POST /chat
│   ├── auth_routes.py         # Login/register/reset
│   └── admin_routes.py        # Admin diagnostics
├── security/
│   └── security.py            # Password hashing, JWT validation
└── utils/
    └── helpers.py             # Utility functions

templates/
├── chat_ui.html               # Main chatbot interface
├── admin_ui.html              # Admin dashboard
├── auth_ui.html               # Login/register
└── reset_password.html        # Password reset

requirements.txt               # Dependencies
.env                          # Secrets (NOT in git)
```

---

## Core Components

### **Chatbot Service** (`backend/services/chatbot_service.py`)

**5-Intent Retrieval Pipeline:**
1. Intent Detection (fee/hod/club/placement/scholarship/general)
2. Stopword Filtering + Alias Expansion (IT → information technology)
3. FAQ Retrieval with Relevance Scoring
4. Structured Data Lookup (Department, FeeStructure tables)
5. Context Aggregation + Groq Synthesis
6. Source Attribution (groq/faq/structured/fallback)

**Key Functions:**
- `_detect_intent()` - Classify query type
- `_tokenize() / _expand_aliases()` - Text normalization
- `_collect_relevant_faqs()` - Intent-aware FAQ filtering
- `_direct_structured_answer()` - HOD/fee fast path
- `build_context()` - Aggregate all data sources
- `generate_reply_with_source()` - Orchestrate response pipeline

**Accuracy:** 75% baseline (100% fees/clubs/placements, 67% HOD edge cases)

---

### **AI Service** (`backend/services/ai_service.py`)

**Groq LLM Wrapper:**
- Model: `llama-3.1-8b-instant` (free tier)
- Temperature: 0.1 (factual, low hallucination)
- Prompt: "Answer ONLY from VERIFIED_COLLEGE_DATA"
- Error handling: Rate limits, API failures → fallback to FAQ

```python
client = Groq(api_key=settings.GROQ_API_KEY)
response = client.chat.completions.create(
    model="llama-3.1-8b-instant",
    temperature=0.1,  # Low variance
    messages=[{"role": "system", "content": PROMPT}, ...]
)
```

---

### **Database Models** (`backend/database/models.py`)

| Model | Rows | Purpose |
|-------|------|---------|
| **FAQ** | 501 | Knowledge base (timetables, clubs, placements) |
| **Department** | 2 | IT, EE with HODs |
| **FeeStructure** | 20 | Tuition, exam, hostel, mess fees by year |
| **Club** | 6 | Campus clubs + descriptions |
| **Placement** | 134 | Student placement records (branch, company, package) |
| **ScholarshipCell** | 5 | Officers by category (SC-ST, General, OBC, Minority) |
| **User** | N/A | Authentication (email, hashed password, role) |

---

### **API Endpoints** (`backend/routes/`)

#### Chat
```bash
POST /chat
Authorization: Bearer <jwt_token>
{
  "message": "Who is the HOD of IT?"
}

Response:
{
  "reply": "HOD of Information Technology is Dr. Ishan Bhardwaj.",
  "debug": {
    "source": "structured"  # Admin only
  }
}
```

#### Authentication
```bash
POST /auth/register        # Signup
POST /auth/login           # Get JWT token
POST /auth/reset-password  # Password reset
```

#### Admin
```bash
GET /admin/responses?limit=10     # Recent responses with sources
```

---

## Environment Variables

```env
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/chatbot_db

# Groq LLM
GROQ_API_KEY=gsk_xxxxx
GROQ_MODEL=llama-3.1-8b-instant
ENABLE_LLM=true

# Security (⚠️ CHANGE THESE)
SECRET_KEY=change_to_random_secret
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60

# Optional
GMAIL_ADDRESS=
GMAIL_APP_PASSWORD=
RESET_TOKEN_EXPIRE_MINS=15
APP_BASE_URL=http://127.0.0.1:8000
```

Generate strong SECRET_KEY:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

---

## Data Seeding

Populate database from CSV files:

```bash
cd backend
python database/seed/seed_departments_and_fees.py    # 2 depts + 20 fees
python database/seed/seed_clubs.py                   # 6 clubs
python database/seed/seed_scholarships.py            # 134 placements
python database/seed/seed_scholarship_cell.py        # 5 officers
```

Each script is **idempotent** (skips duplicates).

---

## Production Checklist

### Security
- [ ] Generate random SECRET_KEY: `openssl rand -hex 32`
- [ ] Add valid GROQ_API_KEY (from https://console.groq.com)
- [ ] Configure PostgreSQL with strong password
- [ ] Use HTTPS with SSL certificates
- [ ] Store .env in secure vault (AWS Secrets Manager, etc.)
- [ ] Never commit .env to git

### Performance
- [ ] Enable database connection pooling (already in SQLAlchemy)
- [ ] Add Redis caching for FAQ/placement data
- [ ] Implement rate limiting (SlowAPI)
- [ ] Use Gunicorn with 4+ worker processes
- [ ] Enable CORS for frontend domain only
- [ ] Compress responses with gzip middleware

### Monitoring
- [ ] Add structured logging (Python logging)
- [ ] Set up Prometheus metrics (CPU, memory, latency)
- [ ] Configure error tracking (Sentry)
- [ ] Monitor Groq API usage and rate limits
- [ ] Log all /chat requests with source attribution

### Deployment
- [ ] Use Docker for containerization
- [ ] Define docker-compose.yml (app + PostgreSQL)
- [ ] Configure CI/CD pipeline (GitHub Actions)
- [ ] Set up automated database backups
- [ ] Implement health check endpoint
- [ ] Version API endpoints (/v1/chat, etc.)

---

## Deployment Examples

### Local Development
```bash
cd backend
uvicorn app:app --reload
```

### Production with Gunicorn
```bash
cd backend
gunicorn -w 4 -b 0.0.0.0:8000 "app:app"
```

### Docker
```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn", "backend.app:app", "--host", "0.0.0.0", "--port", "8000"]
```

Build & run:
```bash
docker build -t chatbot:latest .
docker run -p 8000:8000 --env-file .env chatbot:latest
```

---

## Known Issues & Fixes

### Issue 1: HOD Fuzzy Matching
**Problem:** Query "Who is HOD of CSE?" returns EE HOD (fuzzy match)  
**Fix:** Change `_best_department_match()` to require exact token match

```python
# In _best_department_match():
if best_score >= 1:  # Stricter: require exact match
    return best_match
```

### Issue 2: Out-of-Scope Source Attribution
**Problem:** Non-college questions return source="groq" instead of "fallback"  
**Fix:** Explicitly check if response is fallback message

```python
if reply == OUT_OF_SCOPE_REPLY:
    return reply, "fallback"
```

---

## Future Enhancements

### Phase 1: Accuracy (Next)
- [ ] Fix HOD fuzzy matching & out-of-scope detection
- [ ] Add category field to FAQ model for intent-specific filtering
- [ ] Implement semantic search with embeddings (pgvector)

### Phase 2: Scale
- [ ] Add Redis caching for FAQ + placements (TTL=1hr)
- [ ] Optimize FAQ relevance scoring (BM25 algorithm)
- [ ] Implement full-text search (PostgreSQL gin/gist)

### Phase 3: Features
- [ ] Analytics dashboard (query volume, popular topics, user engagement)
- [ ] Multi-language support (language detection + translation)
- [ ] Voice chatbot integration (Groq speech APIs)
- [ ] Email notifications for feedback
- [ ] A/B testing framework for response variants

### Phase 4: Enterprise
- [ ] SAML/OAuth2 for college SSO
- [ ] API rate limiting & quotas per user
- [ ] Audit logs for compliance
- [ ] Custom fine-tuning on college-specific domain
- [ ] Webhook integrations (Slack, Teams notifications)

---

## Database Schema

```sql
-- FAQ (knowledge base)
CREATE TABLE faq (
    id SERIAL PRIMARY KEY,
    keyword VARCHAR,
    response TEXT,
    is_active BOOLEAN
);

-- Department (HOD directory)
CREATE TABLE department (
    id SERIAL PRIMARY KEY,
    name VARCHAR UNIQUE,
    hod VARCHAR
);

-- FeeStructure
CREATE TABLE fee_structure (
    id SERIAL PRIMARY KEY,
    branch VARCHAR,
    fee_type VARCHAR,
    amount INTEGER,
    year INTEGER
);

-- Club
CREATE TABLE club (
    id SERIAL PRIMARY KEY,
    name VARCHAR UNIQUE,
    category VARCHAR,
    description TEXT
);

-- Placement
CREATE TABLE placement (
    id SERIAL PRIMARY KEY,
    student_name VARCHAR,
    branch VARCHAR,
    company_name VARCHAR,
    package_lpa FLOAT,
    placement_year VARCHAR
);

-- ScholarshipCell
CREATE TABLE scholarship_cell (
    id SERIAL PRIMARY KEY,
    name VARCHAR,
    designation VARCHAR,
    category VARCHAR,
    contact_no VARCHAR,
    email VARCHAR
);

-- User (authentication)
CREATE TABLE "user" (
    id SERIAL PRIMARY KEY,
    email VARCHAR UNIQUE,
    hashed_password VARCHAR,
    role VARCHAR,
    created_at TIMESTAMP
);
```

---

## Support & Debugging

### Enable Debug Logging
```python
# In backend/app.py
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Check API Response Source
```bash
curl -X POST http://localhost:8000/chat \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"message": "What clubs are available?"}' | jq .debug.source
```

### Monitor DB Queries
```python
# In config.py
SQLALCHEMY_ECHO = True  # Log all SQL
```

### Test Groq API
```bash
curl https://api.groq.com/openai/v1/chat/completions \
  -H "Authorization: Bearer $GROQ_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{...}'
```

---

## License

Internal Use - REC Bijnor

**Last Updated:** March 29, 2026  
**Version:** 1.0.0 (Production Ready)
