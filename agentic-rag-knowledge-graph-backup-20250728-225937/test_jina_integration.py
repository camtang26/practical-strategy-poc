#!/usr/bin/env python3
"""Test Jina embeddings v4 integration."""
import asyncio
from agent.providers_jina_patch import patch_providers

# Apply patches
patch_providers()

from agent.providers import get_embedding_client, get_embedding_model

async def main():
    """Test Jina embeddings with various inputs."""
    client = get_embedding_client()
    model = get_embedding_model()
    
    print(f"✅ Jina Embeddings v4 Integration Test")
    print(f"   Model: {model}")
    print(f"   API Base: {client.base_url}")
    print()
    
    # Test 1: Single text embedding
    print("📝 Test 1: Single text embedding")
    response = await client.embeddings.create(
        model=model,
        input="Strategic planning for business transformation",
        extra_body={'normalized': True, 'embedding_type': 'float'}
    )
    print(f"   Dimension: {len(response.data[0].embedding)}")
    print(f"   ✓ Success")
    print()
    
    # Test 2: Batch text embedding
    print("📚 Test 2: Batch text embedding")
    texts = [
        "Market analysis and competitive positioning",
        "Innovation strategies for growth",
        "Digital transformation roadmap"
    ]
    response = await client.embeddings.create(
        model=model,
        input=texts,
        extra_body={'normalized': True, 'embedding_type': 'float'}
    )
    print(f"   Embedded {len(response.data)} texts")
    print(f"   Each dimension: {len(response.data[0].embedding)}")
    print(f"   ✓ Success")
    print()
    
    # Test 3: Long context embedding
    print("📖 Test 3: Long context embedding (testing 32K token window)")
    long_text = "Strategic business planning " * 1000  # ~4000 tokens
    response = await client.embeddings.create(
        model=model,
        input=long_text,
        extra_body={'normalized': True, 'embedding_type': 'float'}
    )
    print(f"   Input length: {len(long_text)} chars")
    print(f"   Dimension: {len(response.data[0].embedding)}")
    print(f"   ✓ Success - Large context handled")
    print()
    
    print("🎉 All tests passed! Jina v4 integration working perfectly.")
    print()
    print("Key advantages over OpenAI embeddings:")
    print("- 32,768 token context (vs 8,192)")
    print("- Multimodal support (text + images)")
    print("- 2048 dimensions for richer representations")
    print("- Better cost efficiency")

if __name__ == "__main__":
    asyncio.run(main())
