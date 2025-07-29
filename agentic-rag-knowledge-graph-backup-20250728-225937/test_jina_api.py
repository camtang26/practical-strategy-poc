import asyncio
import httpx
import json
import os

JINA_API_KEY = os.getenv("EMBEDDING_API_KEY")

async def test_jina_api():
    # Test 1: Minimal request (what should work)
    minimal_request = {
        "model": "jina-embeddings-v4",
        "input": ["Hello world"]
    }
    
    # Test 2: With encoding_format (might be the issue)
    with_encoding = {
        "model": "jina-embeddings-v4",
        "input": ["Hello world"],
        "encoding_format": "float"
    }
    
    headers = {
        "Authorization": f"Bearer {JINA_API_KEY}",
        "Content-Type": "application/json"
    }
    
    async with httpx.AsyncClient() as client:
        print("Test 1: Minimal request")
        try:
            response = await client.post(
                "https://api.jina.ai/v1/embeddings",
                headers=headers,
                json=minimal_request
            )
            print(f"Status: {response.status_code}")
            if response.status_code == 200:
                print("Success!")
            else:
                print(f"Error: {response.text}")
        except Exception as e:
            print(f"Exception: {e}")
        
        print("\nTest 2: With encoding_format")
        try:
            response = await client.post(
                "https://api.jina.ai/v1/embeddings",
                headers=headers,
                json=with_encoding
            )
            print(f"Status: {response.status_code}")
            if response.status_code == 200:
                print("Success!")
            else:
                print(f"Error: {response.text}")
        except Exception as e:
            print(f"Exception: {e}")

if __name__ == "__main__":
    asyncio.run(test_jina_api())
