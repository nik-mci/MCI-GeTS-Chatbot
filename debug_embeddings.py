import google.generativeai as genai
import os
from dotenv import load_dotenv

# Load API key
load_dotenv('rag_api/.env')
api_key = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=api_key)

def test_embeddings():
    model = "models/gemini-embedding-2-preview"
    texts = ["Hello world", "Traveling to India"]
    
    print(f"Testing embeddings with model: {model}")
    try:
        result = genai.embed_content(
            model=model,
            content=texts,
            task_type="retrieval_document"
        )
        print("Success! Keys in response:", result.keys())
        if 'embeddings' in result:
             print(f"Embeddings count: {len(result['embeddings'])}")
             print(f"Embedding size: {len(result['embeddings'][0])}")
        else:
             print("Full result:", result)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_embeddings()
