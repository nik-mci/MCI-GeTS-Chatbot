import os
from dotenv import load_dotenv

env_path = os.path.join('rag_api', '.env')
load_dotenv(env_path)

key = os.getenv("GROQ_API_KEY", "")

print("-" * 30)
if key:
    print(f"Key Found!")
    print(f"Key Length: {len(key)}")
    print(f"Starts With: {key[:10]}...")
    print(f"Loaded Path: {os.path.abspath(env_path)}")
else:
    print("No GROQ_API_KEY found.")

os.environ.pop("GROQ_API_KEY", None)
load_dotenv(env_path, override=True)
new_key = os.getenv("GROQ_API_KEY", "")
if new_key and new_key != key:
    print("WARNING: Your system environment variable was overriding your .env file!")
print("-" * 30)
