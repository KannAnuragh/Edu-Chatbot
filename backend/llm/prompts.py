"""
LLM — RAG Prompt Templates.

System prompts and RAG context assembly for LLM providers.
"""

SYSTEM_PROMPT = """You are a highly capable educational assistant. Answer clearly and accurately based ONLY on the provided reference material.

CRITICAL RULES:
1. LANGUAGE MATCHING (STRICT): You MUST reply in the EXACT SAME language as the user's Question.
   - If the user asks in English, you MUST reply entirely in English. DO NOT use Malayalam.
   - If the user asks in Malayalam, you MUST reply entirely in Malayalam.
   - Do NOT mix languages.
2. FACTS ONLY: Base your answers STRICTLY on the facts in the "Reference Material". If the answer is not in the material, say "I do not have enough information to answer."
3. DESCRIPTIVE & LONG ANSWERS: By default, provide very long, detailed, and highly descriptive answers. Break down complex topics thoroughly. Use paragraphs or bullet points. (Unless the user explicitly asks for a short or specific type of answer).
4. NO META-COMMENTARY: Do not say "Based on the reference material..." or mention the language you are speaking. Just answer directly."""

RAG_PROMPT_TEMPLATE = """Reference Material:
{context}

Previous Conversation:
{history}

Question: {question}

Answer:"""

def build_rag_prompt(
    context_chunks: list,
    conversation_history: list,
    question: str,
) -> str:
    """
    Build the full RAG prompt with context, history, and question.

    Args:
        context_chunks: List of dicts with text, filename, page_number, score.
        conversation_history: List of dicts with role and content.
        question: The user's current question.

    Returns:
        Formatted prompt string.
    """
    # Format context with relevance scores
    context_parts = []
    for i, chunk in enumerate(context_chunks, 1):
        score = chunk.get('score', 0.0)
        filename = chunk.get('filename', 'Unknown')
        page = chunk.get('page_number', '?')
        text = chunk.get('text', '')
        
        context_parts.append(
            f"--- Document {i} (Score: {score:.2f}) ---\n"
            f"Source: {filename}, Page: {page}\n"
            f"{text}\n"
        )
        
    context_str = "\n".join(context_parts) if context_parts else "No reference material available."
    
    # Format history
    history_str = ""
    if conversation_history:
        for msg in conversation_history:
            role = "Student" if msg.role == "user" else "Assistant"
            history_str += f"{role}: {msg.content}\n\n"
            
    return RAG_PROMPT_TEMPLATE.format(
        context=context_str,
        history=history_str or "No previous conversation.",
        question=question
    )

QUERY_OPTIMIZATION_PROMPT = """You are a search engine optimization expert. Your task is to convert the user's latest message into a highly effective English search query for a vector database.

Conversation History:
{history}

User's Latest Message: {query}

Instructions:
1. If the message is a greeting or casual chat, just return the exact message.
2. If the message refers to previous context (e.g. "tell me more about it"), include the relevant context in the search query.
3. The query MUST be in English.
4. ONLY return the optimized query string. Do NOT add quotes or explanations.

Optimized Query:"""
