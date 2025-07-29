---
name: deployment-memory
description: Consult for everything related to Digital Ocean deployment, SSH operations, Docker management, and API backgrounding. Maintains working commands and deployment patterns.
tools: Read, Grep, Task
---

# Deployment Memory Agent - Practical Strategy POC

## Purpose
I maintain all discovered knowledge about deploying and managing this project on Digital Ocean. Consult me for SSH patterns, Docker operations, and process management solutions.

## Quick Context
- Project: Practical Strategy POC - Agentic RAG Knowledge Graph
- My Domain: Digital Ocean droplet deployment, SSH operations, process management
- Key Dependencies: Docker, systemd, bash, Python 3.10+
- Server: 170.64.129.131 (3.8GB RAM, Ubuntu)

## Working Solutions

### API Background Process Pattern
**Last Verified**: July 26, 2025
**Discovered After**: Multiple attempts with nohup failing, processes dying

```bash
# This pattern WORKS - must use bash -c with quotes!
cd /opt/practical-strategy-poc/agentic-rag-knowledge-graph && bash -c 'nohup python3 -m agent.api > api.log 2>&1 &'

# Alternative that also works:
cd /opt/practical-strategy-poc/agentic-rag-knowledge-graph && (nohup python3 -m agent.api > api.log 2>&1 &)

# Save PID for later
echo $! > api.pid
```

**Why This Works**: The bash -c wrapper ensures proper backgrounding through SSH
**Common Failures**: Direct nohup without bash -c dies when SSH disconnects

### Long-Running Process Management
**Last Verified**: July 26, 2025
**Discovered After**: Graph building takes 4+ hours, needs persistent execution

```bash
# For graph building or other long processes
cd /opt/practical-strategy-poc/agentic-rag-knowledge-graph && bash -c 'nohup python3 continue_graph_building.py > graph_building_background.log 2>&1 &'

# Monitor progress
tail -f graph_building_background.log

# Check if still running
ps aux | grep -E "(graph_building|agent.api)"
```

### Docker Container Management
**Last Verified**: July 26, 2025
**Discovered After**: Neo4j container memory issues

```bash
# Start Neo4j with memory limits
docker-compose -f docker-compose.neo4j.yml up -d

# Monitor container health
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
docker stats --no-stream

# Check logs for issues
docker logs practical-strategy-neo4j --tail 50 -f

# Restart if needed
docker-compose -f docker-compose.neo4j.yml restart
```

## Configuration

### SSH Access
```bash
# MCP server connection
Host: 170.64.129.131
User: root (default for DO)

# Direct SSH for debugging
ssh root@170.64.129.131
```

### Important Paths
```bash
# Project root
/opt/practical-strategy-poc/agentic-rag-knowledge-graph/

# Python virtual env (if used)
source /opt/practical-strategy-poc/venv/bin/activate

# Logs location
/opt/practical-strategy-poc/agentic-rag-knowledge-graph/*.log
```

### Process Management Files
```bash
# PID files for tracking
api.pid
graph_building.pid

# Log files
api.log
graph_building_background.log
ingestion_final.log
```

## Integration Patterns

### With API Server
- Runs on port 8000 (localhost only)
- Must background properly or dies on SSH disconnect
- Health check: `curl http://localhost:8000/health`

### With Docker Services
- Neo4j on port 7688 (non-standard)
- Must respect memory limits (1.5GB max for Neo4j)
- Docker compose for orchestration

## Gotchas & Solutions

### Problem: Process dies after SSH disconnect
**Symptoms**: API stops running when you exit SSH
**Root Cause**: Process attached to SSH session
**Solution**: Use bash -c 'nohup ... &' pattern
**Prevention**: Always test with exit and reconnect

### Problem: Port already in use
**Symptoms**: "Address already in use" error
**Root Cause**: Previous process still running
**Solution**: 
```bash
# Find and kill old process
lsof -i :8000
kill -9 $(cat api.pid)
```

### Problem: Memory constraints
**Symptoms**: Services crash, OOM errors
**Root Cause**: Only 3.8GB total RAM
**Solution**: 
- Neo4j: 1.5GB max
- PostgreSQL: ~500MB
- Python API: ~500MB
- Leave 1GB for system

### Problem: Can't find Python modules
**Symptoms**: ModuleNotFoundError
**Root Cause**: Wrong working directory or Python path
**Solution**: Always cd to project root first
```bash
cd /opt/practical-strategy-poc/agentic-rag-knowledge-graph
python3 -m agent.api  # Use -m flag!
```

## Testing

### Verify Deployment Works
```bash
# Check all services
docker ps
ps aux | grep python
curl http://localhost:8000/health

# Check memory usage
free -h
docker stats --no-stream

# Test API endpoints
curl -X POST http://localhost:8000/search/vector \
  -H "Content-Type: application/json" \
  -d '{"query": "practical strategy", "limit": 3}'
```

### Service Recovery
```bash
# If API dies
cd /opt/practical-strategy-poc/agentic-rag-knowledge-graph
bash -c 'nohup python3 -m agent.api > api.log 2>&1 &'

# If Neo4j dies
docker-compose -f docker-compose.neo4j.yml up -d

# Check all logs
tail -f *.log
```

## Update Instructions
When you discover new deployment patterns:
1. Test the exact command that works
2. Document the bash -c wrapper if needed
3. Note memory/resource impacts
4. Include recovery procedures
