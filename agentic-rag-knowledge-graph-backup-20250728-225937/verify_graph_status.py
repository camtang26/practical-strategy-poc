#!/usr/bin/env python3
"""
Quick script to verify the knowledge graph status in Neo4j
"""
import os
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()

# Neo4j connection
uri = os.getenv("NEO4J_URI", "bolt://localhost:7688")
user = os.getenv("NEO4J_USER", "neo4j")
password = os.getenv("NEO4J_PASSWORD", "agpassword123")

driver = GraphDatabase.driver(uri, auth=(user, password))

def get_graph_stats():
    with driver.session() as session:
        # Count entities
        entity_count = session.run("MATCH (e:Entity) RETURN count(e) as count").single()["count"]
        
        # Count relationships
        rel_count = session.run("MATCH ()-[r]->() RETURN count(r) as count").single()["count"]
        
        # Count episodes
        episode_count = session.run("MATCH (ep:EpisodeMention) RETURN count(ep) as count").single()["count"]
        
        # Get entity types
        entity_types = session.run("""
            MATCH (e:Entity)
            RETURN e.entity_type as type, count(e) as count
            ORDER BY count DESC
            LIMIT 10
        """).values()
        
        # Get relationship types
        rel_types = session.run("""
            MATCH ()-[r]->()
            RETURN type(r) as type, count(r) as count
            ORDER BY count DESC
            LIMIT 10
        """).values()
        
        # Sample entities
        sample_entities = session.run("""
            MATCH (e:Entity)
            RETURN e.name as name, e.entity_type as type, e.summary as summary
            LIMIT 5
        """).values()
        
        return {
            "entity_count": entity_count,
            "relationship_count": rel_count,
            "episode_count": episode_count,
            "entity_types": entity_types,
            "relationship_types": rel_types,
            "sample_entities": sample_entities
        }

if __name__ == "__main__":
    try:
        stats = get_graph_stats()
        
        print("🎯 Knowledge Graph Status:")
        print(f"📊 Total Entities: {stats['entity_count']}")
        print(f"🔗 Total Relationships: {stats['relationship_count']}")
        print(f"📝 Total Episodes: {stats['episode_count']}")
        
        print("\n📈 Top Entity Types:")
        for entity_type, count in stats['entity_types']:
            print(f"  - {entity_type}: {count}")
        
        print("\n🔀 Top Relationship Types:")
        for rel_type, count in stats['relationship_types']:
            print(f"  - {rel_type}: {count}")
        
        print("\n📌 Sample Entities:")
        for name, entity_type, summary in stats['sample_entities']:
            print(f"  - {name} ({entity_type})")
            if summary:
                print(f"    {summary[:100]}...")
        
        driver.close()
        
    except Exception as e:
        print(f"❌ Error connecting to Neo4j: {e}")
        print("Make sure Neo4j is running and credentials are correct.")
