"""
Document Ingestion Pipeline.

Orchestrates extraction, chunking, embedding, and vector storage.
"""

from typing import Tuple
from langdetect import detect, DetectorFactory

from ingestion.extractor import extract_text_from_pdf
from ingestion.chunker import chunk_text
from providers.factory import embedding_model, get_vector_db_client

# Ensure consistent language detection
DetectorFactory.seed = 0

def detect_language(text: str) -> str:
    """Detect language of text. Fallback to 'en'."""
    try:
        # Use first 1000 characters for detection
        return detect(text[:1000])
    except:
        return "en"


def run_ingestion_pipeline(
    file_path: str, 
    filename: str, 
    user_id: str, 
    course_id: str, 
    document_id: str
) -> Tuple[int, str]:
    """
    Run the full ingestion pipeline.
    
    Returns:
        (page_count, detected_language)
    """
    # 1. Extract Text
    pages_text, page_count = extract_text_from_pdf(file_path)
    
    if not pages_text:
        raise ValueError("No text could be extracted from the PDF")
        
    # 2. Detect Language
    full_text_sample = "\n".join([t for _, t in pages_text[:5]])
    language = detect_language(full_text_sample)
    
    # 3. Chunk Text
    chunks = chunk_text(pages_text, filename)
    
    if not chunks:
        raise ValueError("Chunking resulted in 0 chunks")
        
    # 4. Generate Embeddings
    texts_to_embed = [c["text"] for c in chunks]
    embeddings = embedding_model.encode(texts_to_embed)
    
    # 5. Store in Qdrant
    vector_db = get_vector_db_client()
    vector_db.upsert_chunks(
        user_id=user_id,
        course_id=course_id,
        document_id=document_id,
        filename=filename,
        chunks=chunks,
        embeddings=embeddings
    )
    
    return page_count, language
