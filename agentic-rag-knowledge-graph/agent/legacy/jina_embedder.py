"""
Jina embedder for Graphiti integration.
"""

import os
from typing import List, Dict, Any, Union, Iterable
import httpx
from dataclasses import dataclass

from graphiti_core.embedder import EmbedderClient


@dataclass
class JinaEmbedderConfig:
    """Configuration for Jina embedder."""
    api_key: str
    model: str = "jina-embeddings-v4"
    embedding_dim: int = 2048
    base_url: str = "https://api.jina.ai/v1"


class JinaEmbedder(EmbedderClient):
    """Jina embedder implementation for Graphiti."""
    
    def __init__(self, config: JinaEmbedderConfig):
        """Initialize Jina embedder with configuration."""
        self.config = config
        self.client = httpx.AsyncClient(
            headers={
                "Authorization": f"Bearer {config.api_key}",
                "Content-Type": "application/json"
            },
            timeout=30.0
        )
    
    async def create(self, input_data: Union[str, List[str], Iterable[int], Iterable[Iterable[int]]]) -> List[float]:
        """
        Create embedding for a single input.
        
        Args:
            input_data: Text to embed (string or list with single string)
            
        Returns:
            Embedding vector
        """
        # Handle single text input or list with single item
        if isinstance(input_data, str):
            text = input_data
        elif isinstance(input_data, list) and len(input_data) == 1 and isinstance(input_data[0], str):
            text = input_data[0]
        else:
            raise ValueError(f"Jina embedder expects string input or list with single string, got {type(input_data)}")
        
        response = await self.client.post(
            f"{self.config.base_url}/embeddings",
            json={
                "input": [text],
                "model": self.config.model
            }
        )
        
        if response.status_code != 200:
            raise Exception(f"Jina API error: {response.status_code} - {response.text}")
        
        data = response.json()
        return data["data"][0]["embedding"]
    
    async def create_batch(self, input_data_list: List[str]) -> List[List[float]]:
        """
        Create embeddings for multiple inputs.
        
        Args:
            input_data_list: List of texts to embed
            
        Returns:
            List of embedding vectors
        """
        response = await self.client.post(
            f"{self.config.base_url}/embeddings",
            json={
                "input": input_data_list,
                "model": self.config.model
            }
        )
        
        if response.status_code != 200:
            raise Exception(f"Jina API error: {response.status_code} - {response.text}")
        
        data = response.json()
        return [item["embedding"] for item in data["data"]]
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.client.aclose()
    
    def __del__(self):
        """Clean up client."""
        # Note: In async context, proper cleanup should use __aexit__
        pass
