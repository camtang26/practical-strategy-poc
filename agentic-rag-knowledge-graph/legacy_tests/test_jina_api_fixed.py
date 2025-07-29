import asyncio
import httpx
import json
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

JINA_API_KEY = os.getenv('EMBEDDING_API_KEY')
print(f"API Key loaded: {JINA_API_KEY[:10]}..." if JINA_API_KEY else "No API key found")

async def test_jina_api():
    # Test 1: Minimal request (what should work)
    minimal_request = {
        "model": "jina-embeddings-v4",
        "input": ["Hello world"]
    }
    
    headers = {
        "Authorization": f"Bearer {JINA_API_KEY}",
        "Content-Type": "application/json"
    }
    
    async with httpx.AsyncClient() as client:
        print("\nTest 1: Minimal request")
        try:
            response = await client.post(
                "https://api.jina.ai/v1/embeddings",
                headers=headers,
                json=minimal_request
            )
            print(f"Status: {response.status_code}")
            if response.status_code == 200:
                print("Success! Response keys:", list(response.json().keys()))
            else:
                print(f"Error: {response.text}")
        except Exception as e:
            print(f"Exception: {e}")

if __name__ == "__main__":
    asyncio.run(test_jina_api())
