"""
Jina AI embedding provider implementation.
"""

import openai
from typing import List, Union, Dict, Any, Optional
import logging
import base64
import httpx
import json

from .base import EmbeddingProvider, EmbeddingResult, EmbeddingType


logger = logging.getLogger(__name__)


class JinaEmbeddingProvider(EmbeddingProvider):
    """Jina AI embedding provider using their OpenAI-compatible API."""
    
    # Model configurations
    MODEL_CONFIGS = {
        "jina-embeddings-v4": {
            "dimensions": 1024,  # Default, supports truncation
            "max_tokens": 32768,  # 32k tokens!
            "supports_images": True,
            "tile_size": 28,  # pixels per tile
            "tokens_per_tile": 10
        },
        "jina-embeddings-v3": {
            "dimensions": 1024,
            "max_tokens": 8192,
            "supports_images": False
        },
        "jina-clip-v2": {
            "dimensions": 768,
            "max_tokens": 8192,
            "supports_images": True,
            "tile_size": 512,
            "tokens_per_tile": 4000
        },
        "jina-clip-v1": {
            "dimensions": 768,
            "max_tokens": 8192,
            "supports_images": True,
            "tile_size": 224,
            "tokens_per_tile": 1000
        },
        "jina-colbert-v2": {
            "dimensions": 128,  # Per-token embeddings
            "max_tokens": 8192,
            "supports_images": False,
            "is_colbert": True  # Late interaction model
        }
    }
    
    def __init__(
        self,
        api_key: str,
        model: str = "jina-embeddings-v4",
        base_url: Optional[str] = None,
        normalized: bool = True,
        embedding_type: str = "float",
        **kwargs
    ):
        """
        Initialize Jina embedding provider.
        
        Args:
            api_key: Jina API key
            model: Model name (default: jina-embeddings-v4)
            base_url: API base URL (default: Jina's API)
            normalized: Whether to L2 normalize embeddings
            embedding_type: Output type (float, binary, base64)
        """
        super().__init__(api_key, model, base_url, **kwargs)
        
        # Initialize OpenAI-compatible client pointing to Jina
        self.client = openai.AsyncOpenAI(
            api_key=api_key,
            base_url=base_url or "https://api.jina.ai/v1"
        )
        
        self.normalized = normalized
        self.embedding_type = embedding_type
        
        # Get model config
        if model not in self.MODEL_CONFIGS:
            logger.warning(f"Unknown model {model}, using v4 config")
            self.model_config = self.MODEL_CONFIGS["jina-embeddings-v4"]
        else:
            self.model_config = self.MODEL_CONFIGS[model]
    
    async def embed_texts(
        self,
        texts: List[str],
        **kwargs
    ) -> EmbeddingResult:
        """Generate embeddings for texts using Jina API."""
        self.validate_inputs(texts)
        
        # Process texts
        processed_texts = []
        for text in texts:
            if not text or not text.strip():
                processed_texts.append("")
                continue
                
            # Jina supports much longer contexts!
            max_chars = self.model_config["max_tokens"] * 4
            if len(text) > max_chars:
                logger.warning(f"Truncating text from {len(text)} to {max_chars} chars")
                text = text[:max_chars]
                
            processed_texts.append(text)
        
        try:
            # Use direct HTTP request to avoid OpenAI client adding encoding_format
            async with httpx.AsyncClient() as http_client:
                # Ensure proper URL formatting
                base_url = str(self.client.base_url).rstrip('/')
                response = await http_client.post(
                    f"{base_url}/embeddings",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": self.model,
                        "input": processed_texts
                    }
                )
                response.raise_for_status()
                data = response.json()
            
            embeddings = [item["embedding"] for item in data["data"]]
            
            # Calculate token usage for Jina
            total_tokens = sum(len(text.split()) * 1.3 for text in processed_texts)  # Rough estimate
            
            return EmbeddingResult(
                embeddings=embeddings,
                metadata={
                    "provider": "jina",
                    "normalized": self.normalized,
                    "embedding_type": self.embedding_type,
                    "is_colbert": self.model_config.get("is_colbert", False)
                },
                model=self.model,
                dimensions=self.model_config["dimensions"],
                token_usage=int(total_tokens)
            )
            
        except Exception as e:
            logger.error(f"Jina embedding error: {e}")
            raise
    
    async def embed_images(
        self,
        images: List[Union[str, bytes]],
        **kwargs
    ) -> EmbeddingResult:
        """Generate embeddings for images using Jina API."""
        if not self.model_config["supports_images"]:
            raise NotImplementedError(f"Model {self.model} does not support image embeddings")
        
        self.validate_inputs(images)
        
        # Convert images to proper format
        processed_inputs = []
        total_tokens = 0
        
        for img in images:
            if isinstance(img, str):
                if img.startswith(('http://', 'https://')):
                    # URL format
                    processed_inputs.append({"url": img})
                else:
                    # Assume it's a file path, read and encode
                    try:
                        with open(img, 'rb') as f:
                            img_bytes = f.read()
                        encoded = base64.b64encode(img_bytes).decode('utf-8')
                        processed_inputs.append({"bytes": encoded})
                    except Exception as e:
                        logger.error(f"Failed to read image file {img}: {e}")
                        raise
            else:
                # Already bytes, encode to base64
                encoded = base64.b64encode(img).decode('utf-8')
                processed_inputs.append({"bytes": encoded})
        
        try:
            # Use direct HTTP request to avoid OpenAI client adding encoding_format
            async with httpx.AsyncClient() as http_client:
                # Ensure proper URL formatting
                base_url = str(self.client.base_url).rstrip('/')
                response = await http_client.post(
                    f"{base_url}/embeddings",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": self.model,
                        "input": processed_inputs
                    }
                )
                response.raise_for_status()
                data = response.json()
            
            embeddings = [item["embedding"] for item in data["data"]]
            
            return EmbeddingResult(
                embeddings=embeddings,
                metadata={
                    "provider": "jina",
                    "input_type": "image",
                    "normalized": self.normalized,
                    "embedding_type": self.embedding_type
                },
                model=self.model,
                dimensions=self.model_config["dimensions"],
                token_usage=None  # Jina doesn't return usage info in response
            )
            
        except Exception as e:
            logger.error(f"Jina image embedding error: {e}")
            raise
    
    async def embed_mixed(
        self,
        inputs: List[Dict[str, Union[str, bytes]]],
        **kwargs
    ) -> EmbeddingResult:
        """Generate embeddings for mixed text and image inputs."""
        if not self.model_config["supports_images"]:
            # Fall back to text-only
            return await super().embed_mixed(inputs, **kwargs)
        
        self.validate_inputs(inputs)
        
        # Process mixed inputs
        processed_inputs = []
        
        for inp in inputs:
            input_type = inp.get("type", "text")
            content = inp.get("content", "")
            
            if input_type == "text":
                processed_inputs.append(content)
            elif input_type == "image":
                if isinstance(content, str) and content.startswith(('http://', 'https://')):
                    processed_inputs.append({"url": content})
                else:
                    # Convert to base64
                    if isinstance(content, str):
                        # File path
                        with open(content, 'rb') as f:
                            content = f.read()
                    encoded = base64.b64encode(content).decode('utf-8')
                    processed_inputs.append({"bytes": encoded})
            else:
                logger.warning(f"Unknown input type: {input_type}")
        
        try:
            # Use direct HTTP request to avoid OpenAI client adding encoding_format
            async with httpx.AsyncClient() as http_client:
                # Ensure proper URL formatting
                base_url = str(self.client.base_url).rstrip('/')
                response = await http_client.post(
                    f"{base_url}/embeddings",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": self.model,
                        "input": processed_inputs
                    }
                )
                response.raise_for_status()
                data = response.json()
            
            embeddings = [item["embedding"] for item in data["data"]]
            
            return EmbeddingResult(
                embeddings=embeddings,
                metadata={
                    "provider": "jina",
                    "input_types": "mixed",
                    "normalized": self.normalized,
                    "embedding_type": self.embedding_type
                },
                model=self.model,
                dimensions=self.model_config["dimensions"],
                token_usage=None  # Jina doesn't return usage info in response
            )
            
        except Exception as e:
            logger.error(f"Jina mixed embedding error: {e}")
            raise
    
    def get_dimensions(self) -> int:
        """Get embedding dimensions."""
        return self.model_config["dimensions"]
    
    def supports_images(self) -> bool:
        """Check if provider supports images."""
        return self.model_config["supports_images"]
    
    def get_max_tokens(self) -> int:
        """Get max token limit."""
        return self.model_config["max_tokens"]
    
    def calculate_image_tokens(self, width: int, height: int) -> int:
        """
        Calculate token cost for an image.
        
        Args:
            width: Image width in pixels
            height: Image height in pixels
            
        Returns:
            Number of tokens
        """
        if "tile_size" not in self.model_config:
            return 0
            
        tile_size = self.model_config["tile_size"]
        tokens_per_tile = self.model_config["tokens_per_tile"]
        
        # Calculate tiles needed
        tiles_x = (width + tile_size - 1) // tile_size
        tiles_y = (height + tile_size - 1) // tile_size
        total_tiles = tiles_x * tiles_y
        
        return total_tiles * tokens_per_tile
