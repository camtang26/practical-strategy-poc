async def generate_embedding(text: str) -> List[float]:
    """
    Generate embedding for text using configured provider with caching.
    
    Args:
        text: Text to embed
    
    Returns:
        Embedding vector
    """
    try:
        # Use cached version
        return await get_cached_embedding(text, generate_embedding_unified)
    except Exception as e:
        logger.error(f"Failed to generate embedding: {e}")
        raise
