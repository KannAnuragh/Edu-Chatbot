import os
from dotenv import load_dotenv

load_dotenv("backend/.env")

api_key = os.environ.get("GEMINI_API_KEY", "")
print(f"Loaded GEMINI_API_KEY: {api_key[:10]}... (len: {len(api_key)})")

try:
    from google import genai
    client = genai.Client(api_key=api_key)
    print("genai.Client initialized successfully!")
    
    # Try calling
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents="Hi"
    )
    print("Response text:", response.text)
except Exception as e:
    import traceback
    print("ERROR:")
    traceback.print_exc()
