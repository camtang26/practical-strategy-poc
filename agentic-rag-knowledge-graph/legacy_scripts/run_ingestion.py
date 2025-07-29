#!/usr/bin/env python3
"""Run document ingestion with Jina embeddings."""
import asyncio
import logging
from pathlib import Path

# Apply Jina patches
from agent.providers_jina_patch import patch_providers
patch_providers()

from ingestion.ingest import DocumentIngestionPipeline, IngestionConfig
from agent.db_utils import init_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    """Run the ingestion."""
    logger.info("Starting ingestion with Jina embeddings...")
    
    # Initialize database
    await init_db()
    
    # Create pipeline with config
    config = IngestionConfig(
        chunk_size=800,
        chunk_overlap=150,
        use_semantic_chunking=True,
        extract_entities=True,
        skip_graph_building=False
    )
    
    pipeline = DocumentIngestionPipeline(config)
    
    # Ingest documents
    docs_path = Path("documents")
    files = list(docs_path.glob("*.md"))
    logger.info(f"Found {len(files)} documents to ingest")
    
    for file in files:
        logger.info(f"Ingesting {file.name}...")
    
    await pipeline.run(str(docs_path))
    logger.info("Ingestion complete!")

if __name__ == "__main__":
    asyncio.run(main())
