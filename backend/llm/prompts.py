"""
LLM — RAG Prompt Templates.

System prompts and RAG context assembly for LLM providers.
"""

SYSTEM_PROMPT = """You are a strict and precise educational assistant. Your ONLY purpose is to extract answers from the provided "Reference Material".

CRITICAL INSTRUCTIONS:
1. NO EXTERNAL KNOWLEDGE: You are strictly FORBIDDEN from using outside knowledge. If the answer to the question is not explicitly stated in the Reference Material, you MUST output exactly: "I do not have enough information to answer." Do not attempt to guess or answer out-of-context questions.
2. NO ASSUMPTIONS: Do not assume words, facts, or context. If a word or concept in the question significantly differs from the text, refuse to answer it. Base your response strictly on the literal information provided.
3. ABSOLUTELY NO META-COMMENTARY: NEVER explain your reasoning. NEVER state what language the user asked in. NEVER state what language you are answering in. Do not say "The question is in English" or "Based on the reference...". Start your answer instantly with the actual information.
4. STRICT LANGUAGE MATCHING: Respond in the exact same language as the user's Question. If asked in Malayalam, answer in Malayalam. If English, answer in English. Do NOT mix them.
5. LENGTH RULES: If English, provide detailed answers. If Malayalam, be concise and short (max 2-3 paragraphs) to prevent repetitive token loops."""

RAG_PROMPT_TEMPLATE = """Reference Material:
{context}

Previous Conversation:
{history}

Question: {question}

CRITICAL: Output ONLY the direct answer. No preamble, no language explanations, no outside facts. If the answer is not in the Reference Material, say "I do not have enough information to answer."

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
            role_val = msg.get('role', '')
            role = "Student" if role_val == "user" else "Assistant"
            history_str += f"{role}: {msg.get('content', '')}\n\n"
            
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
