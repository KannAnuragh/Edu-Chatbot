import sys
import os
import fitz  # PyMuPDF

try:
    from libindic.payyans import Payyans
except ImportError:
    print("libindic-payyans is not installed.")
    print("Please install it by running:")
    print("pip install git+https://github.com/libindic/payyans.git#egg=libindic-payyans")
    sys.exit(1)

def convert_pdf_to_unicode(pdf_path: str, output_txt_path: str):
    print(f"Opening PDF: {pdf_path}")
    
    # Initialize the converter
    converter = Payyans()
    
    # We will assume ML-TTKarthika as the source font. 
    # Other common fonts: ML-TTRevathi, ML-TTAmbili.
    source_font = "ML-TTKarthika"
    
    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        print(f"Error opening PDF: {e}")
        sys.exit(1)
        
    total_pages = len(doc)
    converted_text = ""
    
    for i, page in enumerate(doc, 1):
        print(f"Converting page {i}/{total_pages}...")
        text = page.get_text("text").strip()
        
        if not text:
            continue
            
        # Basic cleanup of null bytes
        text = text.replace('\x00', '')
        
        # Convert legacy ASCII to Unicode
        try:
            # Note: Payyans requires the exact font name mapping
            unicode_text = converter.ASCII2Unicode(text, source_font)
            converted_text += f"\n--- Page {i} ---\n{unicode_text}\n"
        except Exception as e:
            print(f"Warning: Failed to convert text on page {i}: {e}")
            converted_text += f"\n--- Page {i} ---\n{text}\n"
            
    doc.close()
    
    # Save the output
    print(f"\nSaving converted text to: {output_txt_path}")
    with open(output_txt_path, "w", encoding="utf-8") as f:
        f.write(converted_text)
        
    print("✅ Conversion complete!")
    print(f"You can now upload '{os.path.basename(output_txt_path)}' to the admin dashboard instead of the PDF.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python convert_font.py <path_to_pdf>")
        print("Example: python convert_font.py textbook.pdf")
        sys.exit(1)
        
    pdf_path = sys.argv[1]
    
    if not os.path.exists(pdf_path):
        print(f"File not found: {pdf_path}")
        sys.exit(1)
        
    base_name = os.path.splitext(pdf_path)[0]
    output_txt_path = f"{base_name}_unicode.txt"
    
    convert_pdf_to_unicode(pdf_path, output_txt_path)
