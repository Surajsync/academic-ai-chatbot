import re
import json
import threading

np = None
SentenceTransformer = None

from backend.database.database import SessionLocal
from sqlalchemy.orm import Session

from backend.database.models import FAQ, Department, FeeStructure, Club, Placement, ScholarshipCell
from backend.services.ai_service import generate_answer
from backend.config import settings


_EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"
_embedding_model = None
_embedding_model_lock = threading.Lock()


def _get_numpy():
    global np
    if np is None:
        try:
            import numpy as _np
            np = _np
        except ImportError:
            return None
    return np


def _get_sentence_transformer_class():
    global SentenceTransformer
    if SentenceTransformer is None:
        try:
            from sentence_transformers import SentenceTransformer as _SentenceTransformer
            SentenceTransformer = _SentenceTransformer
        except ImportError:
            return None
    return SentenceTransformer


def _get_embedding_model():
    sentence_transformer_class = _get_sentence_transformer_class()
    if sentence_transformer_class is None:
        return None

    global _embedding_model
    if _embedding_model is None:
        with _embedding_model_lock:
            if _embedding_model is None:
                try:
                    _embedding_model = sentence_transformer_class(_EMBEDDING_MODEL_NAME)
                except RuntimeError as exc:
                    # Retry once for transient hub/http client lifecycle glitches.
                    if "client has been closed" not in str(exc).lower():
                        raise
                    _embedding_model = sentence_transformer_class(_EMBEDDING_MODEL_NAME)
    return _embedding_model

_embedding_model = None

def get_embedding_model():
    global _embedding_model

    if _embedding_model is None:
        with _embedding_model_lock:
            if _embedding_model is None:
                ST = _get_sentence_transformer_class()
                if ST is None:
                    return None
                _embedding_model = ST(_EMBEDDING_MODEL_NAME)

    return _embedding_model


OUT_OF_SCOPE_REPLY = "I don't have information about that in the college database. Please contact the Admin Office or the relevant department for assistance. You can also visit the college website or reach out to Student Services."

ALIAS_MAP = {
    "it": "information technology",
    "cse": "computer science engineering",
    "cs": "computer science",
    "ece": "electronics communication",
    "ee": "electrical engineering",
    "me": "mechanical engineering",
    "ce": "civil engineering",
    "hod": "head of department",
}

STOPWORDS = {
    "a", "an", "the", "is", "are", "of", "for", "to", "and", "in", "on", "at",
    "with", "by", "from", "me", "you", "your", "please", "tell", "about", "what",
    "which", "who", "where", "when", "why", "how", "do", "does", "did", "can", "could",
    "should", "would", "branch", "department", "details", "info", "information", "college",
}

FOLLOW_UP_TOKENS = {
    "date", "dates", "year", "years", "detail", "details", "more", "also",
    "that", "those", "their", "them", "it", "and", "same", "exact",
}

FEE_QUERY_HINTS = {"fee", "fees", "tuition", "hostel"}
HOD_QUERY_HINTS = {"hod", "head", "faculty"}
CLUB_QUERY_HINTS = {"club", "clubs", "society", "activities", "extracurricular"}
PLACEMENT_QUERY_HINTS = {"placement", "placements", "job", "company", "companies", "recruit", "internship"}
SCHOLARSHIP_QUERY_HINTS = {"scholarship", "scholarships", "grant", "financial", "assistance"}
ADMISSION_QUERY_HINTS = {"admission", "admissions", "apply", "eligibility", "cutoff", "registration"}
EXAM_QUERY_HINTS = {"exam", "exams", "examination", "result", "results", "marksheet", "backlog", "arrear"}
TIMETABLE_QUERY_HINTS = {"timetable", "schedule", "routine", "calendar", "class timing", "semester"}
CONTACT_QUERY_HINTS = {"contact", "email", "phone", "address", "location", "office"}

FEE_RECORD_HINTS = {"fee", "fees", "tuition", "fee structure", "hostel fee"}
HOD_RECORD_HINTS = {"hod", "head of department", "head"}
CLUB_RECORD_HINTS = {"club", "clubs", "society", "activity"}
PLACEMENT_RECORD_HINTS = {"placement", "placements", "company", "companies", "job", "recruit"}
SCHOLARSHIP_RECORD_HINTS = {"scholarship", "scholarships", "grant", "financial", "assistance"}

GREETING_TOKENS = {
    "hi", "hii", "hiii", "hello", "hey", "yo", "hola", "namaste", "hlo", "sup"
}
THANKS_TOKENS = {"thanks", "thank", "thx", "thankyou", "thankyou!", "thankyou."}

DOMAIN_KEYWORDS = {
    "rec", "bijnor", "aktu", "department", "branch", "fee", "hostel", "placement",
    "scholarship", "college", "faculty", "hod", "syllabus", "exam", "result", "admission",
    "club", "campus", "semester", "timetable", "library", "lab", "attendance",
}

OUT_OF_SCOPE_SIGNALS = {
    "weather", "temperature", "news", "stock", "crypto", "movie", "song", "politics",
    "prime minister", "president", "ipl", "cricket score", "bitcoin", "share market",
}


def _is_llm_enabled() -> bool:
    return bool(settings.ENABLE_LLM or settings.GROQ_API_KEY or settings.GEMINI_API_KEY or settings.OPENAI_API_KEY)


def _faq_keyword_text(faq: FAQ) -> str:
    return (getattr(faq, "keyword", None) or getattr(faq, "keywords", None) or getattr(faq, "question", None) or "")


def _faq_response_text(faq: FAQ) -> str:
    return (getattr(faq, "response", None) or getattr(faq, "answer", None) or "")


def _clean_reply_text(reply: str) -> str:
    """Remove noisy metadata-like lines before sending reply to UI."""
    if not reply:
        return OUT_OF_SCOPE_REPLY

    cleaned_lines = []
    for line in reply.splitlines():
        stripped = line.strip()
        if not stripped:
            cleaned_lines.append("")
            continue

        lowered = stripped.lower()
        if lowered.startswith("source:"):
            continue

        # Drop common leaked metadata patterns from seeded/legacy content.
        if any(token in lowered for token in [".csv", ".xlsx", "amount:", "year:", "sheet:"]):
            continue

        cleaned_lines.append(stripped)

    cleaned = "\n".join(cleaned_lines).strip()
    return cleaned or OUT_OF_SCOPE_REPLY


def _clean_spaces(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "")).strip()


def _detect_intent(query_tokens: set[str]) -> str:
    if query_tokens.intersection(FEE_QUERY_HINTS):
        return "fee"
    if query_tokens.intersection(HOD_QUERY_HINTS):
        return "hod"
    if query_tokens.intersection(CLUB_QUERY_HINTS):
        return "club"
    if query_tokens.intersection(PLACEMENT_QUERY_HINTS):
        return "placement"
    if query_tokens.intersection(SCHOLARSHIP_QUERY_HINTS):
        return "scholarship"
    if query_tokens.intersection(ADMISSION_QUERY_HINTS):
        return "admission"
    if query_tokens.intersection(EXAM_QUERY_HINTS):
        return "exam"
    if query_tokens.intersection(TIMETABLE_QUERY_HINTS):
        return "timetable"
    if query_tokens.intersection(CONTACT_QUERY_HINTS):
        return "contact"
    return "general"


def _is_probably_out_of_scope(normalized_message: str, query_tokens: set[str]) -> bool:
    if not normalized_message:
        return False

    if any(signal in normalized_message for signal in OUT_OF_SCOPE_SIGNALS):
        return True

    # Keep generic short messages in-domain so greetings/small talk work naturally.
    if len(query_tokens) <= 2:
        return False

    has_domain_signal = bool(query_tokens.intersection(DOMAIN_KEYWORDS))
    return not has_domain_signal


def _intent_contact_hint(intent: str) -> str:
    hints = {
        "admission": "For admission-specific updates, contact the Admission Cell.",
        "exam": "For exam schedules and result corrections, contact the Exam Cell.",
        "timetable": "For timetable changes, contact your Department Office.",
        "placement": "For placements, contact the Training and Placement Cell.",
        "scholarship": "For scholarship support, contact the Scholarship Cell.",
        "contact": "For official communication, contact the Admin Office.",
    }
    return hints.get(intent, "For official confirmation, contact the Admin Office.")


def _build_recent_history_context(conversation_history: list[dict] | None) -> str:
    if not conversation_history:
        return ""

    lines = []
    for item in conversation_history[-6:]:
        role = (item.get("role") or "").strip().lower()
        content = _clean_spaces(item.get("content") or "")
        if not content or role not in {"user", "bot"}:
            continue
        lines.append(f"{role.upper()}: {content}")
    return "\n".join(lines)


def get_intent_guided_suggestions(message: str) -> list[str]:
    query_tokens = _tokenize(_expand_aliases(message or ""))
    intent = _detect_intent(query_tokens)

    suggestions = {
        "fee": ["Ask fee breakup by year", "Ask hostel fee details", "Ask payment schedule"],
        "hod": ["Ask department faculty list", "Ask department contact details", "Ask office timings"],
        "placement": ["Ask top recruiters", "Ask average package by branch", "Ask placement details with year"],
        "scholarship": ["Ask scholarship eligibility", "Ask required documents", "Ask scholarship deadlines"],
        "admission": ["Ask admission eligibility", "Ask required documents", "Ask admission deadlines"],
        "exam": ["Ask exam schedule", "Ask result portal details", "Ask backlog exam process"],
        "timetable": ["Ask semester calendar", "Ask class timings", "Ask lab schedule"],
        "contact": ["Ask official email", "Ask office phone number", "Ask campus address"],
        "general": ["Ask department information", "Ask fee structure", "Ask placement details"],
    }
    return suggestions.get(intent, suggestions["general"])[:3]


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", text.lower())).strip()


def _normalize_token_variant(token: str) -> str:
    if len(token) <= 3:
        return token

    if token.endswith("ies") and len(token) > 4:
        return token[:-3] + "y"
    if token.endswith("es") and len(token) > 4:
        return token[:-2]
    if token.endswith("s") and len(token) > 3:
        return token[:-1]

    return token


def _tokenize(text: str) -> set[str]:
    normalized = _normalize(text)
    base_tokens = {t for t in normalized.split() if len(t) > 1 and t not in STOPWORDS}
    expanded_tokens = set(base_tokens)
    for token in base_tokens:
        token_variant = _normalize_token_variant(token)
        if len(token_variant) > 1:
            expanded_tokens.add(token_variant)
    return expanded_tokens


def _expand_aliases(text: str) -> str:
    tokens = _normalize(text).split()
    expanded = []
    for token in tokens:
        expanded.append(token)
        alias_value = ALIAS_MAP.get(token)
        if alias_value:
            expanded.extend(alias_value.split())
    return " ".join(expanded)


def _score_overlap(query_tokens: set[str], candidate_text: str) -> int:
    candidate_tokens = _tokenize(candidate_text)
    if not candidate_tokens:
        return 0
    return len(query_tokens.intersection(candidate_tokens))


def _top_scored_records(records, query_tokens: set[str], text_getter, limit: int = 3, min_score: int = 1):
    ranked = []
    for record in records:
        score = _score_overlap(query_tokens, text_getter(record))
        if score >= min_score:
            ranked.append((score, record))

    ranked.sort(key=lambda row: row[0], reverse=True)
    return [record for _score, record in ranked[:limit]]


def _small_talk_reply(normalized_message: str, query_tokens: set[str]) -> tuple[str, str] | None:
    if not normalized_message:
        return None

    if query_tokens.intersection(GREETING_TOKENS):
        return (
                "Hey there. Great to meet you. I'm here to help with everything about REC Bijnor, including departments, placements, fees, scholarships, and campus life. What can I help you explore today?",
            "smalltalk",
        )

    if query_tokens.intersection(THANKS_TOKENS):
            return ("Happy to help. Anytime you have questions about the college, I'm here for you. Feel free to ask.", "smalltalk")

    if normalized_message in {"ok", "okay", "great", "nice"}:
            return ("Great. Go ahead and ask me whatever you'd like.", "smalltalk")

    return None


def _looks_like_follow_up(query_tokens: set[str]) -> bool:
    if not query_tokens:
        return False
    if len(query_tokens) > 6:
        return False
    return bool(query_tokens.intersection(FOLLOW_UP_TOKENS))


def _resolve_follow_up_query(
    original_message: str,
    expanded_query: str,
    query_tokens: set[str],
    conversation_history: list[dict] | None,
) -> tuple[str, set[str]]:
    if _detect_intent(query_tokens) != "general":
        return expanded_query, query_tokens
    if not _looks_like_follow_up(query_tokens):
        return expanded_query, query_tokens
    if not conversation_history:
        return expanded_query, query_tokens

    previous_user_messages = [
        _clean_spaces(item.get("content") or "")
        for item in conversation_history
        if (item.get("role") or "").strip().lower() == "user"
    ]
    if not previous_user_messages:
        return expanded_query, query_tokens

    last_user_query = previous_user_messages[-1]
    if not last_user_query:
        return expanded_query, query_tokens

    merged = f"{_expand_aliases(last_user_query)} {_expand_aliases(original_message)}"
    return merged, _tokenize(merged)


def _collect_relevant_faqs(
    db: Session,
    expanded_query: str,
    query_tokens: set[str],
    intent: str,
    limit: int = 6,
) -> list[FAQ]:
    ranked = []
    faqs = db.query(FAQ).filter(FAQ.is_active == True).all()

    for faq in faqs:
        keyword_text = _faq_keyword_text(faq)
        response_text = _faq_response_text(faq)
        searchable_text = f"{keyword_text} {response_text}".lower()

        # Intent-aware filtering to avoid noise in focused queries.
        if intent == "fee" and not any(hint in searchable_text for hint in FEE_RECORD_HINTS):
            continue
        if intent == "hod" and not any(hint in searchable_text for hint in HOD_RECORD_HINTS):
            continue
        if intent == "club" and not any(hint in searchable_text for hint in CLUB_RECORD_HINTS):
            continue
        if intent == "placement" and not any(hint in searchable_text for hint in PLACEMENT_RECORD_HINTS):
            continue
        if intent == "scholarship" and not any(hint in searchable_text for hint in SCHOLARSHIP_RECORD_HINTS):
            continue

        best_score = 0
        for phrase in keyword_text.lower().split(","):
            phrase = phrase.strip()
            if not phrase:
                continue

            score = _score_overlap(query_tokens, phrase)
            if phrase and phrase in expanded_query:
                score += 3

            if intent == "fee" and "fee" in phrase:
                score += 1
            if intent == "hod" and ("hod" in phrase or "head" in phrase):
                score += 1
            if intent == "club" and ("club" in phrase or "society" in phrase):
                score += 1
            if intent == "placement" and ("placement" in phrase or "company" in phrase):
                score += 1
            if intent == "scholarship" and ("scholarship" in phrase or "grant" in phrase):
                score += 1

            best_score = max(best_score, score)

        # Skip weak matches to reduce noisy context.
        min_score = 1 if intent in {"fee", "hod", "club", "placement", "scholarship"} or len(query_tokens) <= 3 else 2
        if best_score >= min_score:
            ranked.append((best_score, faq))

    ranked.sort(key=lambda row: row[0], reverse=True)
    return [faq for _score, faq in ranked[:limit]]


def _best_department_match(db: Session, query_tokens: set[str]) -> Department | None:
    best_match = None
    best_score = 0

    for dept in db.query(Department).all():
        score = _score_overlap(query_tokens, dept.name)
        if score > best_score:
            best_score = score
            best_match = dept

    if best_score >= 1:
        return best_match
    return None


def _best_fee_match(db: Session, query_tokens: set[str]) -> FeeStructure | None:
    best_match = None
    best_score = 0

    for fee in db.query(FeeStructure).all():
        score = _score_overlap(query_tokens, fee.branch)
        if score > best_score:
            best_score = score
            best_match = fee

    if best_score >= 1:
        return best_match
    return None


def _direct_structured_answer(db: Session, query_tokens: set[str]) -> tuple[str, str] | None:
    if query_tokens.intersection(HOD_QUERY_HINTS):
        department = _best_department_match(db, query_tokens)
        if department:
            return f"HOD of {department.name} is {department.hod}.", "structured"

    if query_tokens.intersection(FEE_QUERY_HINTS):
        fee = _best_fee_match(db, query_tokens)
        if fee:
            return f"Fee Structure for {fee.branch}: {fee.amount}", "structured"

    if query_tokens.intersection(PLACEMENT_QUERY_HINTS):
        placements = db.query(Placement).all()
        if placements:
            top_placements = _top_scored_records(
                placements,
                query_tokens,
                lambda placement: f"{placement.student_name} {placement.branch} {placement.company_name} {placement.placement_year}",
                limit=6,
                min_score=0,
            )

            if not top_placements:
                top_placements = sorted(
                    placements,
                    key=lambda row: str(row.placement_year or ""),
                    reverse=True,
                )[:6]

            branches = sorted({row.branch for row in placements if row.branch})
            companies = sorted({row.company_name for row in placements if row.company_name})

            lines = ["Placement snapshot (latest records):"]
            for row in top_placements:
                year = row.placement_year or "N/A"
                package = f"{row.package_lpa} LPA" if row.package_lpa else "Package data unavailable"
                lines.append(f"- {row.student_name} ({row.branch}) -> {row.company_name}, {package}, Year: {year}")

            if branches:
                lines.append(f"Branches covered: {', '.join(branches[:8])}")
            if companies:
                lines.append(f"Recruiters in database: {', '.join(companies[:10])}")

            return "\n".join(lines), "structured"

    return None


def build_context(db: Session, message: str) -> str:
    lines = []
    
    # College Header Info
    lines.append("=== REC BIJNOR - OFFICIAL COLLEGE INFORMATION ===")
    lines.append("College: Rajkiya Engineering College, Bijnor")
    lines.append("Type: Government Engineering Institute")
    lines.append("Recognition: Approved by AICTE, affiliated with AKTU, Lucknow")
    lines.append("")
    
    expanded_query = _expand_aliases(message)
    query_tokens = _tokenize(expanded_query)
    intent = _detect_intent(query_tokens)

    relevant_faqs = _collect_relevant_faqs(db, expanded_query, query_tokens, intent)
    if relevant_faqs:
        lines.append("VERIFIED FAQS & INFORMATION:")
        for faq in relevant_faqs:
            keyword = _faq_keyword_text(faq).strip()
            response = _faq_response_text(faq).strip()
            if keyword and response:
                lines.append(f"  Q: {keyword}")
                lines.append(f"  A: {response}")
        lines.append("")

    departments = db.query(Department).all()
    top_departments = _top_scored_records(
        departments,
        query_tokens,
        lambda dept: f"{dept.name} {dept.hod}",
        limit=3,
    )
    department_lines = [f"  • {dept.name} - HOD: {dept.hod}" for dept in top_departments]

    if department_lines:
        lines.append("DEPARTMENTS:")
        lines.extend(department_lines[:6])
        lines.append("")

    fees = db.query(FeeStructure).all()
    top_fees = _top_scored_records(
        fees,
        query_tokens,
        lambda fee: f"{fee.branch} {fee.amount}",
        limit=3,
    )
    fee_lines = [f"  • {fee.branch}: ₹{fee.amount}" for fee in top_fees]

    if fee_lines:
        lines.append("FEE STRUCTURE:")
        lines.extend(fee_lines[:6])
        lines.append("")

    clubs = db.query(Club).all()
    top_clubs = _top_scored_records(
        clubs,
        query_tokens,
        lambda club: f"{club.name} {club.category}",
        limit=4,
        min_score=0 if intent == "club" else 1,
    )

    if top_clubs:
        lines.append("CLUBS & ACTIVITIES:")
        for club in top_clubs:
            lines.append(f"  • {club.name} ({club.category}): {club.description}")
        lines.append("")

    placements = db.query(Placement).all()
    if intent == "placement" or any(token in expanded_query for token in ["company", "placement", "companies"]):
        companies = set()
        branches = set()
        placement_lines = []
        
        top_placements = _top_scored_records(
            placements,
            query_tokens,
            lambda placement: f"{placement.student_name} {placement.company_name} {placement.branch}",
            limit=5,
            min_score=0 if intent == "placement" else 1,
        )

        for placement in placements:
            companies.add(placement.company_name)
            branches.add(placement.branch)

        for placement in top_placements:
            placement_lines.append(
                f"  • {placement.student_name} ({placement.branch}): {placement.company_name}, ₹{placement.package_lpa} LPA, Year: {placement.placement_year}"
            )
        
        if placement_lines:
            lines.append("PLACEMENT RECORDS:")
            lines.extend(placement_lines)
        elif companies or branches:
            lines.append("PLACEMENT SUMMARY:")
            if companies:
                lines.append(f"  Companies: {', '.join(sorted(list(companies))[:12])}")
            if branches:
                lines.append(f"  Branches: {', '.join(sorted(list(branches)))}")
        lines.append("")
    else:
        # Show top placements by default
        top_placements = sorted(placements, key=lambda p: float(p.package_lpa) if p.package_lpa else 0, reverse=True)[:3]
        if top_placements:
            lines.append("TOP PLACEMENTS:")
            for placement in top_placements:
                lines.append(
                    f"  • {placement.student_name} ({placement.branch}): {placement.company_name}, ₹{placement.package_lpa} LPA, Year: {placement.placement_year}"
                )

    scholarships = db.query(ScholarshipCell).all()
    top_scholarships = _top_scored_records(
        scholarships,
        query_tokens,
        lambda scholarship: f"{scholarship.name} {scholarship.designation}",
        limit=4,
        min_score=0 if intent == "scholarship" else 1,
    )
    scholarship_lines = [
        f"  • {scholarship.name} ({scholarship.designation}): {scholarship.category}, Ph: {scholarship.contact_no}"
        for scholarship in top_scholarships
    ]

    if scholarship_lines:
        lines.append("")
        lines.append("🏆 SCHOLARSHIPS & FINANCIAL AID:")
        lines.extend(scholarship_lines[:6])

    return "\n".join(lines)


def _generate_reply_with_source(
    db: Session,
    message: str,
    conversation_history: list[dict] | None = None,
    user_context: str = "",
):
    original_message = message.strip()
    normalized_message = original_message.lower()

    expanded_query = _expand_aliases(normalized_message)
    query_tokens = _tokenize(expanded_query)

    expanded_query, query_tokens = _resolve_follow_up_query(
        original_message,
        expanded_query,
        query_tokens,
        conversation_history,
    )

    if _is_probably_out_of_scope(normalized_message, query_tokens):
        reply = (
            "I can help only with REC Bijnor academic and campus queries, such as admissions, fees, "
            "departments, timetable, exams, placements, clubs, and scholarships."
        )
        return _clean_reply_text(reply), "scope-guard"

    small_talk = _small_talk_reply(normalized_message, query_tokens)
    if small_talk:
        return _clean_reply_text(small_talk[0]), small_talk[1]

    intent = _detect_intent(query_tokens)

    direct_answer = _direct_structured_answer(db, query_tokens)
    if direct_answer:
        return _clean_reply_text(direct_answer[0]), direct_answer[1]

    top_faq = _collect_relevant_faqs(db, expanded_query, query_tokens, intent, limit=1)
    if top_faq and intent == "fee":
        # Deterministic fast path for fee queries when a strong FAQ exists.
        return _clean_reply_text(_faq_response_text(top_faq[0])), "faq"

    context = build_context(db, normalized_message)
    if not context:
        return _clean_reply_text(OUT_OF_SCOPE_REPLY), "fallback"

    contact_hint = _intent_contact_hint(intent)
    recent_history = _build_recent_history_context(conversation_history)
    if user_context:
        profile_line = _clean_spaces(user_context)
        recent_history = f"USER_PROFILE: {profile_line}\n{recent_history}".strip()

    if _is_llm_enabled():
        try:
            ai_reply = generate_answer(
                context,
                original_message,
                conversation_context=recent_history,
                contact_hint=contact_hint,
            )
            if ai_reply:
                return _clean_reply_text(ai_reply), "groq"
        except Exception as exc:
            # print(f"AI provider error: {exc}")
            pass

    fallback_faqs = _collect_relevant_faqs(db, expanded_query, query_tokens, intent, limit=1)
    if fallback_faqs:
        return _clean_reply_text(_faq_response_text(fallback_faqs[0])), "faq"

    semantic_fallback = semantic_faq_search(original_message)
    if semantic_fallback:
        return _clean_reply_text(semantic_fallback[0]), "semantic"

    return _clean_reply_text(OUT_OF_SCOPE_REPLY), "fallback"


def generate_reply(db: Session, message: str):
    reply, _source = _generate_reply_with_source(db, message)
    return reply


def generate_reply_with_source(
    db: Session,
    message: str,
    conversation_history: list[dict] | None = None,
    user_context: str = "",
):
    return _generate_reply_with_source(
        db,
        message,
        conversation_history=conversation_history,
        user_context=user_context,
    )


# Semantic search implementation using sentence embeddings for improved relevance ranking.
def cosine_similarity(a,b):
    np_module = _get_numpy()
    if np_module is None:
        return 0.0
    return np_module.dot(a, b) / (np_module.linalg.norm(a) * np_module.linalg.norm(b))

def semantic_faq_search(query: str):
    np_module = _get_numpy()
    sentence_transformer_class = _get_sentence_transformer_class()
    if np_module is None or sentence_transformer_class is None:
        return None

    db = SessionLocal()

    try:
        model = _get_embedding_model()
        if model is None:
            return None

        query_embedding = model.encode(_expand_aliases(query), normalize_embeddings=True)
        faqs = db.query(FAQ).filter(FAQ.is_active == True).all()

        best_score = -1.0
        best_faq = None

        for faq in faqs:
            if not getattr(faq, "embedding", None):
                continue

            try:
                stored_embedding = np_module.array(json.loads(faq.embedding), dtype=float)
            except Exception:
                continue

            score = cosine_similarity(query_embedding, stored_embedding)

            if score > best_score:
                best_score = score
                best_faq = faq

        if best_faq is not None and best_score >= 0.65:
            return _faq_response_text(best_faq), "semantic", best_score
        return None
    finally:
        db.close()


# Main entry point for chatbot response generation, combining structured lookup, semantic search, and LLM fallback.
def get_response(query: str):
    db = SessionLocal()

    try:
        expanded_query = _expand_aliases(query)
        query_tokens = _tokenize(expanded_query)

        # 1. Structured answer
        structured = _direct_structured_answer(db, query_tokens)
        if structured:
            return {
                "answer": structured[0],
                "type": "structured"
            }

        # 2. Semantic search
        semantic = semantic_faq_search(query)
        if semantic:
            return {
                "answer": semantic[0],
                "type": "semantic",
                "score": semantic[2]
            }

        # 3. LLM fallback
        context = build_context(db, query)
        if _is_llm_enabled() and context:
            try:
                answer = generate_answer(context, query)
            except Exception:
                answer = OUT_OF_SCOPE_REPLY
        else:
            answer = OUT_OF_SCOPE_REPLY

        return {
            "answer": answer,
            "type": "llm"
        }

    finally:
        db.close()