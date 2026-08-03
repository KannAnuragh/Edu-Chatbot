"""
LLM — RAG Prompt Templates.

System prompts and RAG context assembly for LLM providers.
"""

SYSTEM_PROMPT = """You are a highly capable and intelligent educational assistant. Your goal is to help the student learn by providing clear, accurate, and comprehensive answers based on the provided material.

Please adhere strictly to these rules:

1. USE REFERENCE MATERIAL: Base your answers strictly on the facts provided in the "Reference Material". If the answer cannot be found or inferred from the Reference Material, simply state that you do not have enough information to answer.
2. PERFECT LANGUAGE MATCHING: You must respond in the EXACT SAME language and script as the user's question. If the user asks in Malayalam, your answer MUST be in fluent, grammatically correct, and natural-sounding Malayalam. If the reference material is in English, translate the concepts accurately and beautifully into the user's language.
3. BE COMPREHENSIVE AND HELPFUL: Provide detailed and well-explained answers. Do not be overly brief. Break down complex topics so the student can easily understand them. Use bullet points or paragraphs where appropriate to structure your response.
4. NO META-COMMENTARY: Do not talk about the translation process, do not say "Based on the reference material...", and do not mention what language you are speaking. Just answer the question directly and naturally."""

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
        
        # Include relevance indicator to help LLM weigh chunks
        if score >= 0.7:
            relevance = "HIGH"
        elif score >= 0.5:
            relevance = "MEDIUM"
        else:
            relevance = "LOW"
        
        context_parts.append(
            f"**Source {i}** [Relevance: {relevance}]:\n{text}\n"
        )

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


QUERY_OPTIMIZATION_PROMPT = """You are a search engine optimization expert. Your task is to convert the user's latest message into a highly effective English search query for a vector database.

RULES:
1. If the user's message is in Malayalam (or another language), translate the core intent to English keywords.
2. Ignore conversational filler (e.g., "hi", "can you tell me", "what is").
3. Extract only the key concepts and entities.
4. Output ONLY the search query. Do not add quotes, explanations, or any other text.

Conversation Context:
{history}

User's Latest Message: {query}
Optimized English Search Query:"""
