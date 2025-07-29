import asyncio
from agent.tools import graph_search_tool, GraphSearchInput
import logging

logging.basicConfig(level=logging.INFO)

async def test_graph():
    # Test 1: Direct graph search
    print("=== Testing graph_search tool directly ===")
    search_input = GraphSearchInput(query="strategic management")
    results = await graph_search_tool(search_input)
    print(f"Graph search results: {len(results)} items")
    for i, result in enumerate(results[:3]):
        print(f"Result {i}: {result}")
    
    # Test 2: Check Neo4j connection
    print("\n=== Testing Neo4j directly ===")
    try:
        from neo4j import GraphDatabase
        import os
        from dotenv import load_dotenv
        load_dotenv()
        
        neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7688")
        neo4j_user = os.getenv("NEO4J_USER", "neo4j")
        neo4j_pass = os.getenv("NEO4J_PASSWORD", "your-password-here")
        
        driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_pass))
        with driver.session() as session:
            # Count nodes
            result = session.run("MATCH (n) RETURN count(n) as count")
            node_count = result.single()["count"]
            print(f"Total nodes in graph: {node_count}")
            
            # Count facts
            result = session.run("MATCH ()-[r:RELATES_TO]->() RETURN count(r) as count")
            fact_count = result.single()["count"]
            print(f"Total facts (RELATES_TO edges): {fact_count}")
            
            # Sample facts about strategy
            result = session.run("""
                MATCH ()-[r:RELATES_TO]->() 
                WHERE r.fact CONTAINS 'strateg' 
                RETURN r.fact as fact 
                LIMIT 5
            """)
            print("\nFacts containing 'strateg':")
            facts = list(result)
            if not facts:
                print("No facts found containing 'strateg'")
            else:
                for record in facts:
                    print(f"- {record['fact']}")
                
        driver.close()
    except Exception as e:
        print(f"Neo4j error: {e}")

asyncio.run(test_graph())
