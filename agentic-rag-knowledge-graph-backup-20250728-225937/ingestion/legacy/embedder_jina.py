"""
Custom embedder for Jina API that works around OpenAI client limitations.
"""

import httpx
import asyncio
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
import os
from dotenv import load_dotenv

from .chunker import DocumentChunk

load_dotenv()

logger = logging.getLogger(__name__)


class JinaEmbeddingGenerator:
    """Custom embedding generator for Jina API."""
    
    def __init__(
        self,
        model: str = "jina-embeddings-v4",
        batch_size: int = 100,
        max_retries: int = 3,
        retry_delay: float = 1.0
    ):
        """Initialize Jina embedding generator."""
        self.model = model
        self.batch_size = batch_size
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.api_key = os.getenv('EMBEDDING_API_KEY')
        self.base_url = "https://api.jina.ai/v1"
        
        # Jina v4 has 2048 dimensions
        self.dimensions = 2048
        self.max_tokens = 8191
        
        if not self.api_key:
            raise ValueError("EMBEDDING_API_KEY not found in environment")
    
    async def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for a single text."""
        embeddings = await self.generate_embeddings_batch([text])
        return embeddings[0] if embeddings else []
    
    async def generate_embeddings_batch(
        self,
        texts: List[str]
    ) -> List[List[float]]:
        """Generate embeddings for a batch of texts using Jina API directly."""
        if not texts:
            return []
        
        # Process texts
        processed_texts = []
        for text in texts:
            if not text or not text.strip():
                processed_texts.append("")
                continue
            
            # Truncate if too long
            if len(text) > self.max_tokens * 4:
                text = text[:self.max_tokens * 4]
            
            processed_texts.append(text)
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        request_data = {
            "model": self.model,
            "input": processed_texts
        }
        
        for attempt in range(self.max_retries):
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        f"{self.base_url}/embeddings",
                        headers=headers,
                        json=request_data,
                        timeout=30.0
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        return [item["embedding"] for item in data["data"]]
                    else:
                        error_msg = f"Jina API error: {response.status_code} - {response.text}"
                        logger.error(error_msg)
                        if attempt == self.max_retries - 1:
                            raise Exception(error_msg)
                        
            except Exception as e:
                if attempt == self.max_retries - 1:
                    logger.error(f"Failed to embed texts after {self.max_retries} attempts: {e}")
                    raise
                
                logger.warning(f"Attempt {attempt + 1} failed: {e}")
                await asyncio.sleep(self.retry_delay * (2 ** attempt))
        
        return []
    
    async def embed_chunks(
        self,
        chunks: List[DocumentChunk],
        progress_callback: Optional[callable] = None
    ) -> List[DocumentChunk]:
        """Embed a list of document chunks."""
        if not chunks:
            return []
        
        embedded_chunks = []
        total_batches = (len(chunks) + self.batch_size - 1) // self.batch_size
        
        for i in range(0, len(chunks), self.batch_size):
            batch_chunks = chunks[i:i + self.batch_size]
            batch_texts = [chunk.content for chunk in batch_chunks]
            
            try:
                embeddings = await self.generate_embeddings_batch(batch_texts)
                
                # Add embeddings to chunks
                for chunk, embedding in zip(batch_chunks, embeddings):
                    # Create a new chunk with embedding
                    embedded_chunk = DocumentChunk(
                        content=chunk.content,
                        index=chunk.index,
                        start_char=chunk.start_char,
                        end_char=chunk.end_char,
                        metadata={
                            **chunk.metadata,
                            "embedding_model": self.model,
                            "embedding_generated_at": datetime.now().isoformat(),
                            "embedding_dimensions": self.dimensions
                        },
                        token_count=chunk.token_count
                    )
                    
                    # Add embedding as a separate attribute
                    embedded_chunk.embedding = embedding
                    embedded_chunks.append(embedded_chunk)
                
                # Progress update
                current_batch = (i // self.batch_size) + 1
                if progress_callback:
                    progress_callback(current_batch, total_batches)
                
                logger.info(f"Processed batch {current_batch}/{total_batches}")
                
            except Exception as e:
                logger.error(f"Failed to process batch {i//self.batch_size + 1}: {e}")
                # Continue with other batches
        
        return embedded_chunks


def create_embedder(**kwargs) -> JinaEmbeddingGenerator:
    """Create an embedding generator instance."""
    model = os.getenv('EMBEDDING_MODEL', 'jina-embeddings-v4')
    
    # If using Jina, use custom generator
    if 'jina' in model.lower():
        return JinaEmbeddingGenerator(model=model, **kwargs)
    else:
        # Fall back to original embedder for other models
        from .embedder import EmbeddingGenerator
        return EmbeddingGenerator(model=model, **kwargs)
