"""
Agentic RAG with flexible LLM provider support.
"""

import os
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
import logging

from pydantic_ai import Agent, RunContext
from dotenv import load_dotenv

from .prompts import SYSTEM_PROMPT
from .providers import get_llm_model
from .tools import (
    vector_search_tool,
    graph_search_tool,
    hybrid_search_tool,
    get_document_tool,
    list_documents_tool,
    get_entity_relationships_tool,
    get_entity_timeline_tool,
    VectorSearchInput,
    GraphSearchInput,
    HybridSearchInput,
    DocumentInput,
    DocumentListInput,
    EntityRelationshipInput,
    EntityTimelineInput
)

# Load environment variables
load_dotenv()

# Set up logging
logger = logging.getLogger(__name__)


@dataclass
class AgentDependencies:
    """Dependencies for the agent."""
    session_id: str
    user_id: Optional[str] = None
    search_preferences: Dict[str, Any] = None
    search_type: Optional[str] = None  # Add search_type field
    
    def __post_init__(self):
        if self.search_preferences is None:
            self.search_preferences = {
                "use_vector": True,
                "use_graph": True,
                "default_limit": 10
            }


# Initialize the agent with flexible model configuration
rag_agent = Agent(
    get_llm_model(),
    deps_type=AgentDependencies,
    system_prompt=SYSTEM_PROMPT
)


# Register tools with proper docstrings (no description parameter)
@rag_agent.tool
async def vector_search(
    ctx: RunContext[AgentDependencies],
    query: str,
    limit: int = 10
) -> List[Dict[str, Any]]:
    """
    Search for relevant information using semantic similarity.
    Best for semantic similarity searches.
    
    Args:
        ctx: Agent context
        query: Search query
        limit: Maximum number of results
    
    Returns:
        List of search results
    """
    
    input_data = VectorSearchInput(query=query, limit=limit)
    return await vector_search_tool(input_data)


@rag_agent.tool
async def graph_search(
    ctx: RunContext[AgentDependencies],
    query: str
) -> List[Dict[str, Any]]:
    """
    Search the knowledge graph for facts and relationships.
    Best for exploring relationships and connections.
    
    Args:
        ctx: Agent context
        query: Search query
    
    Returns:
        List of graph search results
    """
        
    input_data = GraphSearchInput(query=query)
    return await graph_search_tool(input_data)


@rag_agent.tool
async def hybrid_search(
    ctx: RunContext[AgentDependencies],
    query: str,
    limit: int = 10,
    text_weight: float = 0.3
) -> List[Dict[str, Any]]:
    """
    Perform hybrid search combining vector and keyword search.
    Best for comprehensive searches combining both approaches
    
    Args:
        ctx: Agent context
        query: Search query
        limit: Maximum number of results
        text_weight: Weight for text search (0-1)
    
    Returns:
        List of search results
    """
        
    input_data = HybridSearchInput(
        query=query,
        limit=limit,
        text_weight=text_weight
    )
    return await hybrid_search_tool(input_data)


@rag_agent.tool
async def get_document(
    ctx: RunContext[AgentDependencies],
    document_id: str
) -> Optional[Dict[str, Any]]:
    """
    Get a specific document by ID.
    
    Args:
        ctx: Agent context
        document_id: Document ID
    
    Returns:
        Document details or None
    """
    input_data = DocumentInput(document_id=document_id)
    return await get_document_tool(input_data)


@rag_agent.tool
async def list_documents(
    ctx: RunContext[AgentDependencies]
) -> List[Dict[str, Any]]:
    """
    List all available documents.
    
    Args:
        ctx: Agent context
    
    Returns:
        List of documents
    """
    input_data = DocumentListInput()
    return await list_documents_tool(input_data)


@rag_agent.tool
async def get_entity_relationships(
    ctx: RunContext[AgentDependencies],
    entity: str,
    depth: int = 2
) -> Dict[str, Any]:
    """
    Get relationships for an entity from the knowledge graph.
    
    Args:
        ctx: Agent context
        entity: Entity name
        depth: Relationship depth
    
    Returns:
        Entity relationships
    """
    input_data = EntityRelationshipInput(entity_name=entity, depth=depth)
    return await get_entity_relationships_tool(input_data)


@rag_agent.tool
async def get_entity_timeline(
    ctx: RunContext[AgentDependencies],
    entity: str
) -> List[Dict[str, Any]]:
    """
    Get timeline of facts for an entity.
    
    Args:
        ctx: Agent context
        entity: Entity name
    
    Returns:
        Timeline of facts
    """
    input_data = EntityTimelineInput(entity_name=entity)
    return await get_entity_timeline_tool(input_data)
