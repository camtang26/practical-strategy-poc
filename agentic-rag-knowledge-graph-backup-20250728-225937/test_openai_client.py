import asyncio
import openai
from dotenv import load_dotenv
import os
import logging

# Enable debug logging to see what OpenAI client sends
logging.basicConfig(level=logging.DEBUG)
httpx_logger = logging.getLogger("httpx")
httpx_logger.setLevel(logging.DEBUG)

load_dotenv()

async def test_openai_client():
    client = openai.AsyncOpenAI(
        base_url="https://api.jina.ai/v1",
        api_key=os.getenv('EMBEDDING_API_KEY')
    )
    
    try:
        print("Testing OpenAI client with Jina API...")
        response = await client.embeddings.create(
            model="jina-embeddings-v4",
            input=["Hello world"]
        )
        print("Success!")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_openai_client())
