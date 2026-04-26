from groq import Groq
from backend.config import settings

def generate_answer(context, query, conversation_context: str = "", contact_hint: str = ""):
    if not context:
        return "No specific college data available. Please contact the relevant department or admin office for assistance."

    if not settings.GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is not configured")
    
    prompt = f"""You are REC Bijnor's Academic AI Assistant for students, faculty, and applicants.

Your Role:
- Provide accurate, helpful information about college departments, courses, placements, fees, clubs, scholarships, and student resources
- Be warm, human-like, and professional
- Keep responses concise but informative
- Format responses clearly for easy reading
- Handle follow-up questions naturally using recent conversation context

STRICT RULES:
1. ONLY use information from VERIFIED_COLLEGE_DATA below
2. NEVER use outside knowledge, make assumptions, or guess facts
3. If information is unavailable, say: "I don't have this information in the database. Please contact [relevant department] for details."
4. Keep responses concise (usually 3-6 lines; use more only when user asks for full details)
5. Use bullet points for lists and include year/date fields when available in context
6. Never mention source names, file names, or debug details

VERIFIED_COLLEGE_DATA:
{context}

STUDENT QUESTION:
{query}

RECENT CONVERSATION CONTEXT (if any):
{conversation_context or "N/A"}

ESCALATION HINT:
{contact_hint or "Contact the Admin Office for official confirmation."}

GUIDELINES:
- Academic queries: Be detailed and helpful
- Fee queries: Provide exact figures and clarify payment terms
- Placement queries: Highlight companies, packages, and placement rates
- Placement queries with "date/year": include year-wise details from context whenever available
- Club/Activity queries: Be encouraging and provide contact info if available
- General queries: Be warm and welcoming
- Unknown info: Suggest the right person/department to contact

RESPONSE STYLE:
- Start with a direct answer line
- Then add concise bullets or short sections when needed
- End with one useful next-step line only if helpful"""

    client = Groq(api_key=settings.GROQ_API_KEY)

    response = client.chat.completions.create(
        model=settings.GROQ_MODEL,
        temperature=0.1,
        max_tokens=350,
        messages=[
            {
                "role": "system",
                "content": "You are REC Bijnor's friendly and knowledgeable college assistant. Always be helpful, accurate, and professional."
            },
            {
                "role": "user",
                "content": (
                    f"Context:\n{context}\n\n"
                    f"Recent Conversation:\n{conversation_context or 'N/A'}\n\n"
                    f"Question:\n{query}\n\n"
                    f"Escalation Hint:\n{contact_hint or 'Contact the Admin Office for official confirmation.'}\n\n"
                    "Please provide a concise and informative answer based on the context. "
                    "If the information is not available, suggest the appropriate department to contact."
                )
            }
        ]
    )
    return response.choices[0].message.content.strip()


def generate_follow_up_suggestions(context, query, current_reply):
    """Generate suggested follow-up questions to help users explore more."""
    if not settings.GROQ_API_KEY:
        return []
    
    suggestion_prompt = f"""Based on this college query and answer, suggest 2-3 relevant follow-up questions a student might ask.
Return ONLY the questions as a simple list (one per line), without numbering or bullets.
Keep each question short (under 10 words).

Original Question: {query}
Answer Given: {current_reply}

Follow-up questions:"""

    try:
        client = Groq(api_key=settings.GROQ_API_KEY)
        response = client.chat.completions.create(
            model=settings.GROQ_MODEL,
            temperature=0.2,
            max_tokens=150,
            messages=[
                {
                    "role": "user",
                    "content": suggestion_prompt
                }
            ]
        )
        suggestions_text = response.choices[0].message.content.strip()
        suggestions = [q.strip() for q in suggestions_text.split('\n') if q.strip()]
        return suggestions[:3]
    except Exception:
        return []


def categorize_response(query):
    """Categorize the user query to determine response type."""
    query_lower = query.lower()
    
    category_keywords = {
        "Academic": ["course", "curriculum", "subject", "semester", "syllabus", "class", "exam", "exam schedule"],
        "Placement": ["placement", "placement", "company", "job", "package", "internship", "recruitment"],
        "Admission": ["admission", "apply", "cutoff", "eligibility", "registration"],
        "Fees": ["fee", "fees", "tuition", "payment", "hostel", "refund"],
        "Clubs & Activities": ["club", "club", "society", "activity", "extracurricular", "event", "sports"],
        "Scholarships": ["scholarship", "grant", "financial", "assistance", "sponsorship"],
        "Faculty": ["hod", "head of department", "faculty", "professor", "teacher"],
        "General": ["college", "campus", "facility", "infrastructure", "library", "lab"]
    }
    
    for category, keywords in category_keywords.items():
        if any(kw in query_lower for kw in keywords):
            return category
    
    return "General"