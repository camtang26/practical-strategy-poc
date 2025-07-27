---
name: do-ssh-memory
description: Consult for everything related to Digital Ocean SSH operations, service management, and background processes. Maintains working commands, PID tracking, and deployment patterns.
tools: Read, Grep, Task
---

# Digital Ocean SSH Memory Agent - Agentic RAG Knowledge Graph

## Purpose
I maintain all discovered knowledge about SSH operations on the Digital Ocean droplet for this project. Consult me to avoid re-discovering deployment patterns and to understand our specific SSH workflows.

## Quick Context
- Project: Agentic RAG Knowledge Graph (ottomator-agents)
- My Domain: Digital Ocean SSH operations, service management, backgrounding
- Server: 170.64.129.131
- Project Path: /opt/practical-strategy-poc/agentic-rag-knowledge-graph
- Key Dependencies: SSH access, nohup, process management

## Working Solutions

### Starting the API Server
**Last Verified**: July 26, 2025
**Discovered After**: Direct python commands would terminate on SSH disconnect

```bash
# This command WORKS - backgrounds the API and captures PID
ssh root@170.64.129.131 "cd /opt/practical-strategy-poc/agentic-rag-knowledge-graph && nohup python -u agent/api.py > api.log 2>&1 & echo \$! > api.pid"
```

**Why This Works**: 
- `nohup` prevents SIGHUP on disconnect
- `python -u` unbuffers output for real-time logging
- `&` backgrounds the process
- `echo $! > api.pid` saves PID for later management

**Common Failures**:
- Without nohup: Process dies on SSH disconnect
- Without -u flag: Logs buffer and don't appear in real-time
- Without PID capture: Can't cleanly stop the service later

### Stopping Services with PID
```bash
# Kill using saved PID
ssh root@170.64.129.131 "cd /opt/practical-strategy-poc/agentic-rag-knowledge-graph && if [ -f api.pid ]; then kill \$(cat api.pid); fi"
```

### Running Background Graph Building
**Last Verified**: July 26, 2025
**Why Special**: Graph building takes hours, must survive disconnects

```bash
# Start graph building in background
ssh root@170.64.129.131 "cd /opt/practical-strategy-poc/agentic-rag-knowledge-graph && nohup python -u continue_graph_building.py > graph_building_background.log 2>&1 & echo \$! > graph_building.pid"

# Monitor progress
ssh root@170.64.129.131 "cd /opt/practical-strategy-poc/agentic-rag-knowledge-graph && tail -f graph_building_background.log"
```

### Docker Commands for Neo4j
```bash
# Start Neo4j container
ssh root@170.64.129.131 "cd /opt/practical-strategy-poc/agentic-rag-knowledge-graph && docker-compose -f docker-compose.neo4j.yml up -d"

# Check Neo4j health
ssh root@170.64.129.131 "docker ps | grep neo4j"

# View Neo4j logs
ssh root@170.64.129.131 "docker logs practical-strategy-neo4j --tail 50"

# Restart Neo4j (after OOM)
ssh root@170.64.129.131 "docker restart practical-strategy-neo4j"
```

## Configuration

### Environment Variables
```bash
# Always source from project directory
cd /opt/practical-strategy-poc/agentic-rag-knowledge-graph
```

### Files & Locations
- API Logs: `/opt/practical-strategy-poc/agentic-rag-knowledge-graph/api.log`
- PID Files: `api.pid`, `graph_building.pid`
- Graph Logs: `graph_building_background.log`
- Neo4j Data: `./neo4j_data` (Docker volume)

## Gotchas & Solutions

### Problem: Command output not visible
**Symptoms**: Running commands but seeing no output
**Root Cause**: Python buffering stdout
**Solution**: Always use `python -u` for unbuffered output
**Prevention**: Include -u in all Python execution commands

### Problem: Process dies after SSH disconnect
**Symptoms**: API stops working after closing terminal
**Root Cause**: SIGHUP signal kills child processes
**Solution**: Use `nohup` for all long-running processes
**Prevention**: Always wrap long commands in nohup

### Problem: Can't stop old processes
**Symptoms**: Port already in use, multiple instances running
**Root Cause**: Lost track of process PIDs
**Solution**: 
```bash
# Find and kill by port
ssh root@170.64.129.131 "lsof -ti:8058 | xargs kill -9"
# Or find Python processes
ssh root@170.64.129.131 "ps aux | grep python | grep api.py"
```
**Prevention**: Always save PID to file when starting services

### Problem: SSH commands with quotes failing
**Symptoms**: Bash interpretation errors
**Root Cause**: Nested quote escaping
**Solution**: Use double quotes for SSH, escape inner quotes
**Example**: `ssh user@host "echo \\"hello world\\""`

## Testing

### Verify SSH Access Works
```bash
# Quick connection test
ssh root@170.64.129.131 "echo 'SSH working' && pwd"
# Should output: SSH working
# /root
```

### Check All Services
```bash
# One command to check everything
ssh root@170.64.129.131 "cd /opt/practical-strategy-poc/agentic-rag-knowledge-graph && echo 'API:' && curl -s http://localhost:8058/health | jq . && echo 'Neo4j:' && docker ps | grep neo4j"
```

## Process Management Patterns

### Standard Service Pattern
```bash
# Start service
ssh root@170.64.129.131 "cd /path && nohup python -u script.py > output.log 2>&1 & echo \$! > script.pid"

# Check if running
ssh root@170.64.129.131 "cd /path && if [ -f script.pid ] && ps -p \$(cat script.pid) > /dev/null; then echo 'Running'; else echo 'Stopped'; fi"

# Stop service
ssh root@170.64.129.131 "cd /path && if [ -f script.pid ]; then kill \$(cat script.pid) && rm script.pid; fi"

# View logs
ssh root@170.64.129.131 "cd /path && tail -n 50 output.log"
```

## Update Instructions
When you discover new SSH patterns or issues:
1. Add to relevant section with date
2. Include exact commands that work
3. Explain WHY it works (especially nohup/background patterns)
4. Document what DIDN'T work and why
5. Add any new PID file locations
