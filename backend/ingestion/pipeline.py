"""
Document Ingestion Pipeline.

Orchestrates extraction, chunking, embedding, and vector storage.
"""

import re
import time
from typing import Tuple

from ingestion.extractor import extract_text_from_file
from ingestion.chunker import chunk_text
from providers.factory import embedding_model, get_vector_db_client


def clean_indic_text(text: str) -> str:
    """
    Zero-memory regex cleaner for all Indian regional languages.
    Covers: Devanagari, Bengali/Assamese, Gurmukhi, Gujarati, Odia,
            Tamil, Telugu, Kannada, Malayalam, Urdu/Perso-Arabic.
    """
    # Range 1: \u0900-\u0DFF (All major Indic scripts)
    # Range 2: \u0600-\u08FF (Urdu, Kashmiri, Sindhi Perso-Arabic scripts)
    INDIC_RANGE = r'[\u0900-\u0DFF\u0600-\u08FF]'

    # 1. Remove line-break hyphens splitting Indic words (including soft hyphens and en/em dashes)
    text = re.sub(f'({INDIC_RANGE})[-–—\xad]\\s*({INDIC_RANGE})', r'\1\2', text)

    # 2. Strip invisible formatting artifacts (zero-width spaces) and control characters
    # NOTE: We MUST NOT strip \u200C (ZWNJ) and \u200D (ZWJ) because Malayalam and other Indic languages rely on them for conjuncts and chillu characters.
    text = re.sub(r'[\u200B\uFEFF\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', text)

    # 3. Collapse multiple whitespaces/newlines into single spaces
    text = re.sub(r'\s+', ' ', text).strip()

    return text


def detect_indic_script(text: str) -> str:
    """
    Detects script type based on character frequency without ML models.
    Zero-dependency, runs in microseconds.
    """
    script_counts = {
        'devanagari': len(re.findall(r'[\u0900-\u097F]', text)),  # Hindi, Marathi, Sanskrit
        'bengali': len(re.findall(r'[\u0980-\u09FF]', text)),     # Bengali, Assamese
        'gurmukhi': len(re.findall(r'[\u0A00-\u0A7F]', text)),    # Punjabi
        'gujarati': len(re.findall(r'[\u0A80-\u0AFF]', text)),    # Gujarati
        'odia': len(re.findall(r'[\u0B00-\u0B7F]', text)),        # Odia
        'tamil': len(re.findall(r'[\u0B80-\u0BFF]', text)),       # Tamil
        'telugu': len(re.findall(r'[\u0C00-\u0C7F]', text)),      # Telugu
        'kannada': len(re.findall(r'[\u0C80-\u0CFF]', text)),     # Kannada
        'malayalam': len(re.findall(r'[\u0D00-\u0D7F]', text)),   # Malayalam
        'urdu': len(re.findall(r'[\u0600-\u06FF]', text)),        # Urdu
    }

    top_script, count = max(script_counts.items(), key=lambda x: x[1])
    return top_script if count > 5 else 'english_or_other'


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
        
    # Clean text to remove line-break hyphens and OCR artifacts for all Indic scripts
    pages_text = [(page_num, clean_indic_text(text)) for page_num, text in pages_text]
        
    # 2. Detect Language (zero-dependency, character-range based)
    full_text_sample = " ".join([t for _, t in pages_text[:5]])
    language = detect_indic_script(full_text_sample)
    
    # 3. Chunk Text
    t2 = time.time()
    chunks = chunk_text(pages_text, filename)
    t3 = time.time()
    print(f"⏱️ [Pipeline] Chunking {len(pages_text)} pages took {t3 - t2:.2f} seconds, created {len(chunks)} chunks.")
    
    if not chunks:
        raise ValueError("Chunking resulted in 0 chunks")
        
    # [NEW] 3.5 Translate Malayalam chunks offline to prevent LLM language bleed
    if language == 'malayalam':
        from ingestion.translator import translate_chunks
        texts = [c["text"] for c in chunks]
        translated_texts = translate_chunks(texts)
        for c, t_text in zip(chunks, translated_texts):
            c["original_malayalam"] = c["text"]  # Save original in metadata
            c["text"] = t_text                   # Overwrite with English for embeddings/LLM

        
    # 4. Generate Embeddings
    t4 = time.time()
    texts_to_embed = [c["text"] for c in chunks]
    embeddings = embedding_model.encode(texts_to_embed)
    t5 = time.time()
    print(f"⏱️ [Pipeline] Embedding {len(chunks)} chunks took {t5 - t4:.2f} seconds.")
    
    # Filter out chunks that failed to embed (where embedding is None)
    valid_chunks = []
    valid_embeddings = []
    for c, emb in zip(chunks, embeddings):
        if emb is not None:
            valid_chunks.append(c)
            valid_embeddings.append(emb)
        else:
            print(f"⚠️ [Pipeline] Dropping chunk {c.get('page_number')} due to failed embedding on Cloudflare.", flush=True)
            
    # 5. Store in Vector DB
    t6 = time.time()
    if valid_chunks:
        vector_db = get_vector_db_client()
        vector_db.upsert_chunks(
            user_id=user_id,
            course_id=course_id,
            document_id=document_id,
            filename=filename,
            chunks=valid_chunks,
            embeddings=valid_embeddings
        )
    else:
        print(f"⚠️ [Pipeline] No valid chunks remaining to upsert for {filename}.", flush=True)
        
    t7 = time.time()
    print(f"⏱️ [Pipeline] Vector DB upsert took {t7 - t6:.2f} seconds.")
    
    print(f"⏱️ [Pipeline] Total ingestion time: {t7 - t0:.2f} seconds.")
    return page_count, language
