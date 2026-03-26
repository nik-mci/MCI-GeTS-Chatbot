import asyncio
from main import chat_endpoint, ChatRequest
import logging

logging.basicConfig(level=logging.DEBUG)

async def test():
    request = ChatRequest(query="cheap bali trip")
    try:
        res = await chat_endpoint(request)
        print("Success:", res)
    except Exception as e:
        print("Failed:", type(e).__name__, str(e))

if __name__ == "__main__":
    asyncio.run(test())
