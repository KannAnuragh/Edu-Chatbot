"""
Document Ingestion Pipeline.

Orchestrates extraction, chunking, embedding, and vector storage.
"""

import re
import time
import unicodedata
from typing import Tuple

from ingestion.extractor import extract_text_from_file
from ingestion.chunker import chunk_text
from providers.factory import embedding_model, get_vector_db_client


def fix_malayalam_pdf_font_artifacts(text: str) -> str:
    """
    Fixes pseudo-Unicode font artifacts from legacy PDF extractions (ML-TT / FML CMap glitches).
    Converts broken character combinations into standard, pristine Malayalam Unicode.
    """
    if not text:
        return text

    # 1. Ra-vattu reordering (്ര before consonant -> consonant + ്ര)
    text = re.sub(r'്ര([ക-ഹ])', r'\1്ര', text)
    text = re.sub(r'സ്്ര', 'സ്ത്ര', text)

    # 2. Fix specific legacy font mapping glitches (Case study & common words)
    text = re.sub(r'കസ്േ\s*ല്ലാന്റഡയ്യഡ്േ|കസ്േ\s*ല്ലഡി|കസ്േ', 'കേസ് സ്റ്റഡി', text)
    text = re.sub(r'കസിേനെ', 'കേസിനെ', text)
    text = re.sub(r'എഗ്ല്', 'എന്ത്', text)
    text = re.sub(r'എഗ്ലിന്', 'എന്തിന്', text)
    text = re.sub(r'പവയ്യപാേയിെ\s*്|പവയ്യപാേയിെ', 'പേപ്പറായി', text)
    text = re.sub(r'്രപസെേഷനായി', 'പ്രസന്റേഷനായി', text)
    text = re.sub(r'അപൂയ്യവ', 'അപൂർവ്വ', text)
    text = re.sub(r'വറിേന്തതുമായ|വറിേന്തതുമായി', 'വൈവിധ്യമുള്ളതുമായ', text)
    text = re.sub(r'സന്നീയ്യണ', 'സങ്കീർണ്ണ', text)
    text = re.sub(r'മണ്േപ്പറഞ്ഞ', 'മേൽപ്പറഞ്ഞ', text)
    text = re.sub(r'സി≤ിണ്ണ', 'സിദ്ധിച്ച', text)
    text = re.sub(r'⁄രെ', 'ജ്ഞരെ', text)
    text = re.sub(r'നΩുടെ', 'നമ്മുടെ', text)
    text = re.sub(r'സμയ്യശിണ്ണ്', 'സന്ദർശിച്ച്', text)
    text = re.sub(r'്രപവയ്യസ്ഥന', 'പ്രവർത്തന', text)
    text = re.sub(r'ബാന്ന്', 'ബാങ്ക്', text)
    text = re.sub(r'മായ്യത്ഥറ്റ്', 'മാർക്കറ്റ്', text)
    text = re.sub(r'രഖേപ്പെടു', 'രേഖപ്പെടു', text)
    text = re.sub(r'വായ്യസ്ഥാവിനിമയം', 'വാർത്താവിനിമയം', text)
    text = re.sub(r'ദനൈംദിന', 'ദൈനംദിന', text)
    text = re.sub(r'വളയ്യന്നിരി', 'വളർന്നിരി', text)
    text = re.sub(r'ഒന്തെറേ', 'ഒട്ടേറെ', text)
    text = re.sub(r'സാബ്ബസ്ഥിക', 'സാമ്പത്തിക', text)

    # 3. Structural font artifact replacements
    text = re.sub(r'ത്മ([ളൾൽനമതകറ])', r'ങ്ങ\1', text)
    text = re.sub(r'്രപയാേഗ', 'പ്രയോഗ', text)
    text = re.sub(r'്രപതിഭാസ', 'പ്രതിഭാസ', text)
    text = re.sub(r'്രപശ്ന', 'പ്രശ്ന', text)
    text = re.sub(r'്രപ്രകിയ', 'പ്രക്രിയ', text)
    text = re.sub(r'്രപായാേഗിക', 'പ്രായോഗിക', text)
    text = re.sub(r'്രപദേശ', 'പ്രദേശ', text)

    # 4. Suffix and Case marker corrections
    text = re.sub(r'ത്ഥുറിണ്ണും|ത്ഥുറിണ്ണ്', 'ക്കുറിച്ചും', text)
    text = re.sub(r'ത്ഥാനാണ്', 'ക്കാനാണ്', text)
    text = re.sub(r'ത്ഥുക', 'ക്കുക', text)
    text = re.sub(r'ത്ഥും', 'ക്കും', text)
    text = re.sub(r'ത്ഥുന്ന', 'ക്കുന്ന', text)
    text = re.sub(r'ത്ഥാറുണ്ട്', 'ക്കാറുണ്ട്', text)
    text = re.sub(r'ത്ഥാെണ്ടി', 'ക്കൊണ്ടി', text)
    text = re.sub(r'ത്ഥിണ്ണ്', 'ച്ചിട്ട്', text)

    # 5. Noun ending & inflection corrections
    text = re.sub(r'സ്ഥിെെ', 'ത്തിന്റെ', text)
    text = re.sub(r'സ്ഥിന്', 'ത്തിന്', text)
    text = re.sub(r'സ്ഥിലൂടെ', 'ത്തിലൂടെ', text)
    text = re.sub(r'സ്ഥെ', 'ത്തെ', text)
    text = re.sub(r'സ്ഥിണ്', 'ത്തിൽ', text)
    text = re.sub(r'സ്ഥരം', 'ത്തരം', text)

    # 6. Pre-base & post-base vowel matras re-ordering
    text = re.sub(r'ാേ', 'ോ', text)

    # Clean stray hyphenations
    text = re.sub(r'-\s*യുഃ', 'യുള്ള', text)
    text = re.sub(r'-\s*⁄രെ', 'ജ്ഞരെ', text)
    text = re.sub(r'˛', ' - ', text)

    return text


def clean_indic_text(text: str) -> str:
    """
    Cleaner for Indic regional languages and PDF artifact glyphs.
    Covers: Malayalam, Devanagari, Tamil, Telugu, Kannada, etc.
    """
    # 0. Normalize Unicode to NFC format
    text = unicodedata.normalize("NFC", text)

    INDIC_RANGE = r'[\u0900-\u0DFF\u0600-\u08FF]'

    # 2. Remove line-break hyphens splitting Indic words (including soft hyphens and dashes)
    text = re.sub(f'({INDIC_RANGE})[-–—\xad]\\s*({INDIC_RANGE})', r'\1\2', text)
    # Clean mid-word hyphens (e.g. ദേശീയ-തയും -> ദേശീയതയും)
    text = re.sub(f'({INDIC_RANGE})[-–—]({INDIC_RANGE})', r'\1\2', text)

    # 3. Strip invisible formatting artifacts and control characters
    text = re.sub(r'[\u200B\uFEFF\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', text)

    # 4. Post-process lingering FML legacy font artifacts if present
    if re.search(r'[≥‰ƒ∏™‚√≠‡∑›]', text):
        try:
            from ingestion.smc_fml_converter import convert_fml_to_unicode
            text = convert_fml_to_unicode(text)
        except Exception:
            pass

    # 5. Fix pseudo-Unicode font artifacts from legacy PDF extractions
    text = fix_malayalam_pdf_font_artifacts(text)

    # 6. Collapse multiple whitespaces/newlines into single spaces
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
    return top_script[:10] if count > 5 else 'english'


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
    
    # Calculate estimated token cost based on total embedded characters
    total_chars_embedded = sum(len(c["text"]) for c in valid_chunks) if valid_chunks else 0
    estimated_tokens = total_chars_embedded // 4
    print(f"💰 [Pipeline] Estimated token cost for '{filename}': ~{estimated_tokens} tokens", flush=True)
    
    print(f"⏱️ [Pipeline] Total ingestion time: {t7 - t0:.2f} seconds.")
    return page_count, language
