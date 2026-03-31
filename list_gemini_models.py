import google.generativeai as genai
import os
from dotenv import load_dotenv

# Load API key from rag_api/.env
load_dotenv('rag_api/.env')
api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    print("Error: GEMINI_API_KEY not found in .env")
    exit(1)

genai.configure(api_key=api_key)

print("Fetching available models...")
try:
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            print(f"- {m.name}")
except Exception as e:
    print(f"Failed to list models: {e}")
