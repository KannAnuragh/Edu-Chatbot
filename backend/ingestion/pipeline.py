"""
Document Ingestion Pipeline.

Orchestrates extraction, chunking, embedding, and vector storage.
"""

import re
import time
from typing import Tuple
from langdetect import detect, DetectorFactory

from ingestion.extractor import extract_text_from_file
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


def clean_malayalam_text(text: str) -> str:
    """
    Removes soft hyphens and line-break hyphens common in Malayalam PDF extractions.
    """
    # Remove hyphens that split Malayalam characters (Unicode range: \u0D00-\u0D7F)
    cleaned_text = re.sub(r'([\u0D00-\u0D7F])-\s*([\u0D00-\u0D7F])', r'\1\2', text)
    
    # Optional: Clean up multiple spaces caused by line breaks
    cleaned_text = re.sub(r'\s+', ' ', cleaned_text).strip()
    
    return cleaned_text


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
    print(f"⏱️ [Pipeline] Starting ingestion for {filename}")
    
    # 1. Extract Text
    t0 = time.time()
    pages_text, page_count = extract_text_from_file(file_path)
    t1 = time.time()
    print(f"⏱️ [Pipeline] Extraction took {t1 - t0:.2f} seconds for {page_count} pages.")
    
    if not pages_text:
        raise ValueError("No text could be extracted from the PDF")
        
    # Clean text to remove line-break hyphens and artifacts
    pages_text = [(page_num, clean_malayalam_text(text)) for page_num, text in pages_text]
        
    # 2. Detect Language
    full_text_sample = "\n".join([t for _, t in pages_text[:5]])
    language = detect_language(full_text_sample)
    
    # 3. Chunk Text
    t2 = time.time()
    chunks = chunk_text(pages_text, filename)
    t3 = time.time()
    print(f"⏱️ [Pipeline] Chunking {len(pages_text)} pages took {t3 - t2:.2f} seconds, created {len(chunks)} chunks.")
    
    if not chunks:
        raise ValueError("Chunking resulted in 0 chunks")
        
    # 4. Generate Embeddings
    t4 = time.time()
    texts_to_embed = [c["text"] for c in chunks]
    embeddings = embedding_model.encode(texts_to_embed)
    t5 = time.time()
    print(f"⏱️ [Pipeline] Embedding {len(chunks)} chunks took {t5 - t4:.2f} seconds.")
    
    # 5. Store in Vector DB
    t6 = time.time()
    vector_db = get_vector_db_client()
    vector_db.upsert_chunks(
        user_id=user_id,
        course_id=course_id,
        document_id=document_id,
        filename=filename,
        chunks=chunks,
        embeddings=embeddings
    )
    t7 = time.time()
    print(f"⏱️ [Pipeline] Vector DB upsert took {t7 - t6:.2f} seconds.")
    
    print(f"⏱️ [Pipeline] Total ingestion time: {t7 - t0:.2f} seconds.")
    return page_count, language
