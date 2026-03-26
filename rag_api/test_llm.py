import asyncio
from openai import AsyncOpenAI
import os
from dotenv import load_dotenv

load_dotenv()

async def test_llm():
    api_key = os.getenv("DEEPSEEK_API_KEY")
    print(f"Key loaded: {'YES' if api_key else 'NO'}")
    client = AsyncOpenAI(
        api_key=api_key,
        base_url="https://api.deepseek.com"
    )
    try:
        response = await client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": "hello"}],
            max_tokens=10
        )
        print("Response Success:", response.choices[0].message.content)
    except Exception as e:
        import json
        print(f"Response Failed: {type(e).__name__}")
        if hasattr(e, 'response'):
            try:
                print("Error Details:", e.response.json())
            except:
                print("Raw Error:", str(e))
        else:
            print("Error Message:", str(e))

if __name__ == "__main__":
    asyncio.run(test_llm())
