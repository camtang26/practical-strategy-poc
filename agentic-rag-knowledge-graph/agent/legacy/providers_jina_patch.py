"""
Jina-compatible providers patch.
"""

import os
from typing import Optional, Union
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.models.gemini import GeminiModel
import openai
import google.generativeai as genai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Override embedding client for Jina
def get_embedding_client() -> openai.AsyncOpenAI:
    """Get Jina-compatible embedding client."""
    base_url = os.getenv('EMBEDDING_BASE_URL', 'https://api.jina.ai/v1')
    api_key = os.getenv('EMBEDDING_API_KEY', 'ollama')
    
    return openai.AsyncOpenAI(
        base_url=base_url,
        api_key=api_key
    )

def get_embedding_model() -> str:
    """Get embedding model name from environment."""
    return os.getenv('EMBEDDING_MODEL', 'jina-embeddings-v4')

def patch_providers():
    """Apply patches to use Jina embeddings."""
    # Import the providers module and override functions
    import agent.providers as providers
    providers.get_embedding_client = get_embedding_client
    providers.get_embedding_model = get_embedding_model
    print("Applied Jina embedding patches")
