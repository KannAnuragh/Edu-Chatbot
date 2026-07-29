"""
LLM — RAG Prompt Templates.

System prompts and RAG context assembly for Gemini.
"""

SYSTEM_PROMPT = """You are an expert AI Educational Assistant. Your primary objective is to answer user questions based on the provided PDF document context.

LANGUAGE & RESPONSE GUIDELINES:
1. RESPONSE LANGUAGE: Match the language of the user's question. 
   - If the user asks in English, answer in English.
   - If the user asks in Malayalam or Manglish, answer in Malayalam (മലയാളം).
   - EXPLICIT USER PREFERENCE: If the user explicitly asks to respond in a specific language (e.g., "answer in Malayalam", "explain in English"), ALWAYS follow the user's explicit request.
2. MULTILINGUAL CONTEXT SUPPORT: The document context chunks may be in Malayalam, English, or other languages. Understand facts written in any language/script. Seamlessly translate and synthesize information from the context into the required response language.
3. TECHNICAL TERMS: When helpful, include relevant technical terms in parentheses alongside their translation (e.g., "Commercial Banks (വാണിജ്യ ബാങ്കുകൾ)").
4. DIRECT & CLEAR ANSWERS: Provide clear, direct, and well-structured answers using bullet points or numbered lists. DO NOT use introductory filler phrases (e.g., DO NOT say "Based on the provided documents," or "ലഭ്യമായ വിവരങ്ങൾ അനുസരിച്ച്").
5. NO INLINE CITATION TAGS: Do NOT cite sources inline or include raw page brackets in the text.
6. NO CONTEXT FALLBACK: If no relevant context is found in the provided documents, politely state in the user's language that the information was not found in the course materials.
"""

RAG_PROMPT_TEMPLATE = """## Document Context Chunks

{context}

## Recent Conversation

{history}

## User Question:

{question}

---

Provide a clear, detailed, and accurate answer to the user's question based on the Document Context Chunks above. Match the language of the user's question unless a specific language was requested. Do NOT use introductory filler phrases."""


def build_rag_prompt(
    context_chunks: list,
    conversation_history: list,
    question: str,
) -> str:
    """
    Build the full RAG prompt with context, history, and question.

    Args:
        context_chunks: List of dicts with text, filename, page_number.
        conversation_history: List of dicts with role and content.
        question: The user's current question.

    Returns:
        Formatted prompt string.
    """
    # Format context
    context_parts = []
    for i, chunk in enumerate(context_chunks, 1):
        context_parts.append(f"**Source {i}**:\n{chunk['text']}\n")

    context = "\n".join(context_parts) if context_parts else "No relevant context found in documents."

    # Format conversation history (last 10 messages)
    history_parts = []
    recent_history = conversation_history[-10:] if conversation_history else []
    for msg in recent_history:
        role = "User" if msg["role"] == "user" else "Assistant"
        history_parts.append(f"**{role}:** {msg['content']}")

    history = "\n\n".join(history_parts) if history_parts else "No previous conversation."

    return RAG_PROMPT_TEMPLATE.format(
        context=context,
        history=history,
        question=question,
    )

