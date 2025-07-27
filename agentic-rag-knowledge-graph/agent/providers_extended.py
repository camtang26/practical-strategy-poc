"""
Extended providers module with unified embedding generation using optimized connection pooling.
"""
import os
import sys
from typing import List, Optional
import asyncio
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from ingestion.embedder_jina_v2_prod import OptimizedJinaEmbeddingGenerator
from dotenv import load_dotenv

load_dotenv()

# Singleton instance of the optimized embedder
_embedder_instance: Optional[OptimizedJinaEmbeddingGenerator] = None
_embedder_lock = asyncio.Lock()


async def get_embedder() -> OptimizedJinaEmbeddingGenerator:
    """Get or create the singleton embedder instance."""
    global _embedder_instance
    
    if _embedder_instance is None:
        async with _embedder_lock:
            if _embedder_instance is None:
                _embedder_instance = OptimizedJinaEmbeddingGenerator(
                    model=os.getenv('EMBEDDING_MODEL', 'jina-embeddings-v4'),
                    base_batch_size=100,
                    max_concurrent_requests=3,
                    max_retries=3,
                    retry_delay=1.0,
                    rate_limit_per_minute=60
                )
    return _embedder_instance


async def generate_embedding_unified(text: str) -> List[float]:
    """
    Generate embedding using the optimized connection pooling provider.
    
    Args:
        text: Text to embed
        
    Returns:
        Embedding vector
    """
    provider = os.getenv('EMBEDDING_PROVIDER', 'openai')
    
    if provider == 'jina':
        # Use optimized Jina embedder with connection pooling
        embedder = await get_embedder()
        embeddings = await embedder.generate_embeddings([text])
        return embeddings[0]
    
    else:
        # Fallback to OpenAI (kept for compatibility)
        import httpx
        
        api_key = os.getenv('OPENAI_API_KEY')
        model = os.getenv('EMBEDDING_MODEL', 'text-embedding-ada-002')
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                'https://api.openai.com/v1/embeddings',
                headers={
                    'Authorization': f'Bearer {api_key}',
                    'Content-Type': 'application/json'
                },
                json={
                    'input': text,
                    'model': model
                },
                timeout=30.0
            )
            
            if response.status_code != 200:
                raise Exception(f"Embedding API error: {response.text}")
            
            data = response.json()
            return data['data'][0]['embedding']


# Cleanup function for graceful shutdown
async def cleanup_embedder():
    """Clean up the embedder resources."""
    global _embedder_instance
    if _embedder_instance:
        await _embedder_instance.close()
        _embedder_instance = None
