"""
Extended provider functions for embedding generation.
"""

import os
import asyncio
from typing import List
import httpx
from dotenv import load_dotenv

load_dotenv()


async def generate_embedding_unified(text: str) -> List[float]:
    """
    Generate embedding using the configured provider.
    
    Args:
        text: Text to embed
        
    Returns:
        Embedding vector
    """
    provider = os.getenv('EMBEDDING_PROVIDER', 'openai')
    
    if provider == 'jina':
        # Use Jina API
        api_key = os.getenv('EMBEDDING_API_KEY')
        model = os.getenv('EMBEDDING_MODEL', 'jina-embeddings-v4')
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                'https://api.jina.ai/v1/embeddings',
                headers={
                    'Authorization': f'Bearer {api_key}',
                    'Content-Type': 'application/json'
                },
                json={
                    'input': [text],
                    'model': model
                },
                timeout=30.0
            )
            
            if response.status_code != 200:
                raise Exception(f"Jina API error: {response.status_code} - {response.text}")
            
            data = response.json()
            return data["data"][0]["embedding"]
    
    else:
        # Use OpenAI API (existing code)
        from .providers import get_embedding_client, get_embedding_model
        client = get_embedding_client()
        model = get_embedding_model()
        
        response = await client.embeddings.create(
            model=model,
            input=text
        )
        return response.data[0].embedding
