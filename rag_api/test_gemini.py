import asyncio
import google.generativeai as genai
import os
from dotenv import load_dotenv

load_dotenv()

async def test_gemini_native():
    api_key = os.getenv("GEMINI_API_KEY")
    print(f"Key loaded: {'YES' if api_key else 'NO'}")
    
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-1.5-flash")
    
    try:
        response = await model.generate_content_async("hello")
        print("Response Success:", response.text)
    except Exception as e:
        print(f"Response Failed: {type(e).__name__} - {str(e)}")

if __name__ == "__main__":
    asyncio.run(test_gemini_native())
