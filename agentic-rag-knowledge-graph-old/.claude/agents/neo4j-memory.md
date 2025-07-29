---
name: neo4j-memory
description: Consult for everything related to Neo4j graph database, Docker management, memory configuration, and Cypher queries. Maintains OOM solutions, health checks, and container management.
tools: Read, Grep, Task
---

# Neo4j Memory Agent - Agentic RAG Knowledge Graph

## Purpose
I maintain all discovered knowledge about Neo4j operations in this project. Consult me to avoid memory crashes, understand Docker configurations, and manage the knowledge graph database.

## Quick Context
- Project: Agentic RAG Knowledge Graph (ottomator-agents)
- My Domain: Neo4j graph database, Docker containers, memory management
- Container: practical-strategy-neo4j (Docker)
- Key Issue Solved: Exit code 137 (OOM) crashes
- Memory Allocation: 4GB heap, pagecache tuned
- Port Mapping: 7688:7687 (Bolt), 7475:7474 (HTTP)

## Working Solutions

### Starting Neo4j with Proper Memory
**Last Verified**: July 26, 2025
**Discovered After**: Multiple OOM crashes with default settings

```bash
# Start with docker-compose (RECOMMENDED)
ssh root@170.64.129.131 "cd /opt/practical-strategy-poc/agentic-rag-knowledge-graph && docker-compose -f docker-compose.neo4j.yml up -d"
```

**Docker Compose Configuration That Works**:
```yaml
version: '3.8'

services:
  neo4j:
    image: neo4j:5-community
    container_name: practical-strategy-neo4j
    restart: unless-stopped
    ports:
      - "7688:7687"  # Bolt (non-standard port to avoid conflicts)
      - "7475:7474"  # HTTP
    environment:
      - NEO4J_AUTH=neo4j/agpassword123
      - NEO4J_server_memory_heap_initial__size=512M
      - NEO4J_server_memory_heap_max__size=1G
      - NEO4J_server_memory_pagecache_size=512M
      - NEO4J_PLUGINS=["apoc", "graph-data-science"]
    volumes:
      - neo4j_data:/data
      - neo4j_logs:/logs
    healthcheck:
      test: ["CMD-SHELL", "wget --no-verbose --tries=1 --spider http://localhost:7474 || exit 1"]
      interval: 15s
      timeout: 10s
      retries: 10
    deploy:
      resources:
        limits:
          memory: 1800M
        reservations:
          memory: 1500M
```

### Monitoring Neo4j Health
```bash
# Check if running
ssh root@170.64.129.131 "docker ps | grep neo4j"

# View logs (check for OOM)
ssh root@170.64.129.131 "docker logs practical-strategy-neo4j --tail 100 | grep -E 'ERROR|OutOfMemory|137'"

# Check memory usage
ssh root@170.64.129.131 "docker stats practical-strategy-neo4j --no-stream"

# Health check via HTTP
ssh root@170.64.129.131 "curl -s http://localhost:7475"
```

### Recovering from OOM Crash
**Last Verified**: July 26, 2025
**Symptoms**: Container exits with code 137

```bash
# 1. Check exit code
ssh root@170.64.129.131 "docker ps -a | grep neo4j"

# 2. Restart container
ssh root@170.64.129.131 "docker restart practical-strategy-neo4j"

# 3. If restart fails, recreate
ssh root@170.64.129.131 "cd /opt/practical-strategy-poc/agentic-rag-knowledge-graph && docker-compose -f docker-compose.neo4j.yml down && docker-compose -f docker-compose.neo4j.yml up -d"

# 4. Monitor startup
ssh root@170.64.129.131 "docker logs -f practical-strategy-neo4j"
```

## Connection Details

### Python Connection
```python
from neo4j import GraphDatabase
import os

# Connection that WORKS
uri = "bolt://localhost:7688"  # Note: port 7688, not default 7687
driver = GraphDatabase.driver(
    uri, 
    auth=("neo4j", "agpassword123")
)

# Test connection
with driver.session() as session:
    result = session.run("RETURN 1 as test")
    print(result.single()["test"])
```

### Environment Variables
```bash
NEO4J_URI=bolt://localhost:7688
NEO4J_USER=neo4j
NEO4J_PASSWORD=agpassword123
```

## Cypher Queries

### Check Node Count
```cypher
MATCH (n) RETURN COUNT(n) as nodeCount
```

### Check Memory Usage
```cypher
CALL dbms.showCurrentUser();
CALL dbms.listConfig() YIELD name, value 
WHERE name CONTAINS 'memory' 
RETURN name, value;
```

### Clear All Data (CAREFUL!)
```cypher
MATCH (n) DETACH DELETE n
```

## Gotchas & Solutions

### Problem: Exit code 137
**Symptoms**: Container stops, docker ps shows exit code 137
**Root Cause**: Out of Memory (OOM) killer
**Solution**: Use docker-compose.yml with memory limits
**Prevention**: 
- Set heap max to 1G (not higher on 4GB droplet)
- Set pagecache to 512M
- Use memory limits in deploy section

### Problem: Connection refused on port 7687
**Symptoms**: bolt://localhost:7687 fails
**Root Cause**: Non-standard port mapping to avoid conflicts
**Solution**: Use port 7688 for Bolt connections
**Prevention**: Always check docker-compose.yml for port mappings

### Problem: Slow graph building
**Symptoms**: Graphiti takes hours to process chunks
**Root Cause**: Complex entity extraction, API rate limits
**Solution**: 
```bash
# Run in background with monitoring
nohup python -u continue_graph_building.py > graph_building.log 2>&1 &
```
**Prevention**: Process in batches, save progress frequently

### Problem: Cannot allocate memory
**Symptoms**: Docker fails to start container
**Root Cause**: Not enough free memory on droplet
**Solution**:
```bash
# Check memory
ssh root@170.64.129.131 "free -h"
# Stop other services if needed
ssh root@170.64.129.131 "docker stop $(docker ps -q)"
```

## Docker Management

### Container Lifecycle
```bash
# Start
docker-compose -f docker-compose.neo4j.yml up -d

# Stop
docker-compose -f docker-compose.neo4j.yml stop

# Remove (keeps volumes)
docker-compose -f docker-compose.neo4j.yml down

# Remove including volumes (DESTROYS DATA)
docker-compose -f docker-compose.neo4j.yml down -v

# View logs
docker logs practical-strategy-neo4j -f

# Shell access
docker exec -it practical-strategy-neo4j bash
```

### Volume Management
```bash
# List volumes
docker volume ls | grep neo4j

# Backup data volume
docker run --rm -v agentic-rag-knowledge-graph_neo4j_data:/data -v $(pwd):/backup alpine tar czf /backup/neo4j-backup.tar.gz -C /data .

# Restore data volume
docker run --rm -v agentic-rag-knowledge-graph_neo4j_data:/data -v $(pwd):/backup alpine tar xzf /backup/neo4j-backup.tar.gz -C /data
```

## Testing

### Quick Health Check
```bash
# All-in-one health check
ssh root@170.64.129.131 "echo 'Container:' && docker ps | grep neo4j && echo -e '\nMemory:' && docker stats practical-strategy-neo4j --no-stream && echo -e '\nBolt Port:' && nc -zv localhost 7688"
```

### Verify Graphiti Integration
```python
from graphiti_core import Graphiti
from graphiti_core.nodes import EpisodeType
import asyncio

async def test():
    graphiti = Graphiti(
        uri="bolt://localhost:7688",
        user="neo4j",
        password="agpassword123"
    )
    # Test connection
    episodes = await graphiti.get_episodes()
    print(f"Episodes: {len(episodes)}")
```

## Update Instructions
When you discover new Neo4j patterns or issues:
1. Add to relevant section with date
2. Document memory settings that work
3. Include Docker commands and configurations
4. Note any port mapping changes
5. Update OOM recovery procedures
