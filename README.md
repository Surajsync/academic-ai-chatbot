# REC Bijnor Academic AI Chatbot

An academic chatbot for Rajkiya Engineering College, Bijnor. The app combines structured college data, FAQ retrieval, semantic search, and an LLM fallback to answer student and faculty questions about fees, departments, placements, clubs, scholarships, and account management.

## What It Does

- Answers college-domain questions with structured lookups first, then FAQ and semantic retrieval, then LLM fallback.
- Supports OTP-based signup, login, password reset, and JWT-protected chat access.
- Tracks conversations, messages, failed queries, and admin audit data.
- Lets users edit a profile with a photo and optional personal details.
- Lets users delete the currently selected chat from the UI and backend.
- Uses Groq when enabled, with OpenAI and Gemini configuration slots already supported in settings.
- Exposes admin-only views for chatbot health, FAQ management, and dashboard metrics.

## Tech Stack

- FastAPI
- SQLAlchemy
- PostgreSQL
- Pydantic Settings
- Groq LLM
- Sentence Transformers for semantic FAQ search
- JWT authentication with bcrypt password hashing

## Project Layout

```text
backend/
├── app.py                 # Main FastAPI application and most routes
├── config.py              # Environment-driven settings
├── database/
│   ├── database.py        # SQLAlchemy engine/session
│   └── models.py          # Users, profiles, conversations, FAQs, college data
├── routes/
│   └── chat_routes.py     # Lightweight /api/chat endpoint
├── security/
│   └── security.py        # Password hashing and token helpers
├── services/
│   ├── ai_service.py      # Groq integration and response helpers
│   ├── auth_service.py    # JWT creation
│   └── chatbot_service.py # Retrieval, semantic search, fallback logic
└── utils/
    └── helpers.py         # Database helper

templates/
├── chat_ui.html
├── admin_ui.html
├── auth_ui.html
└── reset_password.html

requirements.txt
```

## Quick Start

```bash
cd /home/suraj-singh/Desktop/chatbot_project
source projectenv/bin/activate
pip install -r requirements.txt

# create a .env file in the repository root
# set DATABASE_URL and SECRET_KEY at minimum

uvicorn backend.app:app --reload
```

Open http://127.0.0.1:8000 after the server starts. The home page serves the auth UI.

## FAQ Seeding (Production Safe)

The FAQ seeder now supports validation, deduplication, upsert modes, optional embedding generation, and dry-run preview.
It also supports strict validation mode and JSON reports for CI/CD.

Default source file:

- `backend/data/faq_optimized.csv`

Run from project root:

```bash
source projectenv/bin/activate

# 1) Validate input and preview DB changes only
python3 backend/database/seed/seed_faq.py --dry-run

# 2) Apply updates (upsert by normalized question)
python3 backend/database/seed/seed_faq.py --mode merge

# 3) Optional: deactivate stale FAQs not present in source
python3 backend/database/seed/seed_faq.py --mode merge --deactivate-missing

# 4) Optional: generate embeddings for rows that do not have one
python3 backend/database/seed/seed_faq.py --mode merge --embed-missing

# 5) Optional: fail fast if any rows are rejected by validation
python3 backend/database/seed/seed_faq.py --dry-run --strict

# 6) Optional: write machine-readable summary for pipelines
python3 backend/database/seed/seed_faq.py --mode merge --report-json backend/data/seed_report.json

# 7) Optional: generate a cleaned FAQ source file (drop rejected rows + dedupe)
python3 backend/database/seed/seed_faq.py --clean-output backend/data/faq_cleaned.csv --clean-only

# 8) Strict-validate cleaned source before production import
python3 backend/database/seed/seed_faq.py --source backend/data/faq_cleaned.csv --dry-run --strict
```

Supported sources:

- CSV with columns like `question,answer,keywords` (recommended)
- JSON array with keys like `question,answer,keywords,embedding,is_active`

Importer modes:

- `merge`: update existing questions and insert new ones
- `append`: insert only new questions, skip existing
- `replace`: deactivate all existing FAQs, then upsert source rows

Additional safety flags:

- `--strict`: fails the run if any source rows are rejected by validation
- `--report-json <path>`: writes a JSON summary including rejected rows and DB upsert stats
- `--clean-output <path>`: writes validated + deduplicated rows to CSV/JSON
- `--clean-only`: stops after writing cleaned output (no DB upsert)

What is filtered automatically:

- Empty question/answer rows
- Low-quality rows like short placeholders
- Metadata leak rows such as answers starting with `Source:` or containing raw spreadsheet file references

## Deploy / Redeploy Checklist

Use this sequence for production updates (Render or similar platform):

```bash
# A) Update FAQ dataset (edit backend/data/faq_optimized.csv)

# B) Preview seeding results locally
python3 backend/database/seed/seed_faq.py --dry-run --strict --report-json backend/data/seed_report.json

# C) Apply seeding locally or in a release job
python3 backend/database/seed/seed_faq.py --mode merge --deactivate-missing

# D) Rebuild embeddings from final FAQ content (recommended)
python3 backend/scripts/embed_faqs.py

# E) Commit and push code/data changes
git add backend/database/seed/seed_faq.py backend/data/faq_optimized.csv README.md
git commit -m "upgrade faq seeding pipeline"
git push
```

Render configuration reminders:

- Build command: `pip install -r requirements.txt`
- Start command: `uvicorn backend.app:app --host 0.0.0.0 --port $PORT`
- Health check path: `/healthz`
- Required env vars: `DATABASE_URL`, `SECRET_KEY`
- LLM env vars as needed: `ENABLE_LLM`, `GROQ_API_KEY`, `GROQ_MODEL`

Post-deploy verification:

1. Check `/healthz`
2. Open `/admin/faqs` and verify FAQ count and sample entries
3. Test greeting, fee, placement, hostel, and scholarship queries
4. Confirm no response leaks `Source:` or raw file names

## FAQ Quality Gate (New)

Automated FAQ data-quality checks now run in CI on push/PR via GitHub Actions:

- `.github/workflows/faq-data-quality.yml`

It validates:

- CSV schema (`question,answer,keywords`)
- non-empty question/answer rows
- duplicate normalized questions
- accidental editor lock files in `backend/data/`

Run the same checks locally before pushing:

```bash
./projectenv/bin/python -m unittest discover -s tests -p "test_faq_data_quality.py" -q
```

## Render Deployment Notes

Use these settings for a FastAPI Web Service on Render:

- Build command: `pip install -r requirements.txt`
- Start command: `uvicorn backend.app:app --host 0.0.0.0 --port $PORT`
- Health check path: `/healthz`

Required environment variables:

- `DATABASE_URL`
- `SECRET_KEY`

Optional environment variables:

- `ENABLE_LLM`, `GROQ_API_KEY`, `GROQ_MODEL`
- `OPENAI_API_KEY`, `LLM_MODEL`
- `GEMINI_API_KEY`, `GEMINI_MODEL`
- `GMAIL_ADDRESS`, `GMAIL_APP_PASSWORD`, `APP_BASE_URL`

## Main API Endpoints

Authentication and account management:

- `POST /auth/send-otp`
- `POST /auth/verify-otp`
- `POST /auth/register`
- `POST /auth/login`
- `POST /auth/forgot-password`
- `POST /auth/reset-password`

Chat and user history:

- `POST /chat` for the main authenticated chatbot flow
- `GET /chat/history`
- `DELETE /chat/conversations/{conversation_id}`
- `POST /api/chat` for the lightweight alternate chat route

Profile:

- `GET /profile/me`
- `PUT /profile/me`

Admin endpoints:

- `GET /admin/dashboard`
- `GET /admin/ai-status`
- `GET /admin/faqs`
- `POST /admin/faqs`
- `DELETE /admin/faqs/{faq_id}`

## How The Bot Answers

`backend/services/chatbot_service.py` uses a layered response strategy:

1. Detects intent such as fee, hod, club, placement, or scholarship.
2. Tries deterministic structured lookups first for direct answers.
3. Pulls the most relevant FAQs with intent-aware filtering.
4. Builds a college context from departments, fees, clubs, placements, and scholarship records.
5. Falls back to Groq when `ENABLE_LLM=true`.
6. Uses a semantic search path based on sentence embeddings for FAQ matching.

The AI service also generates short follow-up suggestions for successful LLM replies.

## Database Models

The current schema includes:

- `User`
- `FAQ`
- `Conversation`
- `Message`
- `FailedQuery`
- `AuditLog`
- `SystemSetting`
- `PasswordResetToken`
- `Department`
- `FeeStructure`
- `Club`
- `Placement`
- `ScholarshipCell`

## Notes

- The app is designed around REC Bijnor data and should stay within the college-domain boundary.
- If the Groq key is missing or LLM use is disabled, the bot falls back to FAQ and structured responses.
- Both `/chat` and `/api/chat` respond, but `/chat` is the primary authenticated flow.
- Manually added FAQs are normalized to active on insert, and legacy FAQs with a missing active flag are corrected during startup.
