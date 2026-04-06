from groq import Groq
from backend.config import settings

def generate_answer(context, query):
    if not context:
        return "No specific college data available. Please contact the relevant department or admin office for assistance."

    if not settings.GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is not configured")
    
    prompt = f"""You are the official REC Bijnor (Rajkiya Engineering College, Bijnor) Academic AI Assistant.

Your Role:
- Provide accurate, helpful information about college departments, courses, placements, fees, clubs, scholarships, and student resources
- Be friendly, professional, and supportive to students and faculty
- Keep responses concise but informative
- Format responses clearly for easy reading

STRICT RULES:
1. ONLY use information from VERIFIED_COLLEGE_DATA below
2. NEVER use outside knowledge, make assumptions, or guess facts
3. If information is unavailable, say: "I don't have this information in the database. Please contact [relevant department] for details."
4. Keep responses concise (2-4 sentences max, unless asking for detailed info)
5. Use bullet points or clear formatting for lists
6. Never mention source names, file names, or debug details

VERIFIED_COLLEGE_DATA:
{context}

STUDENT QUESTION:
{query}

GUIDELINES:
- Academic queries: Be detailed and helpful
- Fee queries: Provide exact figures and clarify payment terms
- Placement queries: Highlight companies, packages, and placement rates
- Club/Activity queries: Be encouraging and provide contact info if available
- General queries: Be warm and welcoming
- Unknown info: Suggest the right person/department to contact"""

    client = Groq(api_key=settings.GROQ_API_KEY)

    response = client.chat.completions.create(
        model=settings.GROQ_MODEL,
        temperature=0.3,  # Slightly higher for more natural responses
        max_tokens=500,
        messages=[
            {
                "role": "system",
                "content": "You are REC Bijnor's friendly and knowledgeable college assistant. Always be helpful, accurate, and professional."
            },
            {
                "role": "user",
                "content": f"Context:\n{context}\n\nQuestion:\n{query}\n\nPlease provide a concise and informative answer based on the context. If the information is not available, suggest the appropriate department to contact."
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
            temperature=0.5,
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