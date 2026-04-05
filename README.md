# REC Bijnor Academic AI Chatbot

An academic chatbot for Rajkiya Engineering College, Bijnor. The app combines structured college data, FAQ retrieval, semantic search, and an LLM fallback to answer student and faculty questions about fees, departments, placements, clubs, scholarships, and account management.

## What It Does

- Answers college-domain questions with structured lookups first, then FAQ and semantic retrieval, then LLM fallback.
- Supports OTP-based signup, login, password reset, and JWT-protected chat access.
- Tracks conversations, messages, failed queries, and admin audit data.
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
│   └── models.py          # Users, conversations, FAQs, college data
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
- `POST /api/chat` for the lightweight alternate chat route

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
