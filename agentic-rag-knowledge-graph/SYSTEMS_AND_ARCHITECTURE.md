# Practical Strategy AI Agent - Systems and Architecture Documentation

## 🚨 CRITICAL DEPLOYMENT INFORMATION

### Production Environment Details
- **Server**: DigitalOcean Droplet
- **IP Address**: `170.64.129.131`
- **API Endpoint**: `http://localhost:8058` (internal)
- **SSH Access**: Via MCP do-ssh tool with configured keys

### LLM Configuration (CRITICAL - Must Use Thinking Model)
```bash
LLM_PROVIDER=qwen
LLM_BASE_URL=https://dashscope-intl.aliyuncs.com/compatible-mode/v1
LLM_API_KEY=sk-076224cd46e141c6a9153af9acc6c12c
LLM_CHOICE=qwen3-235b-a22b-thinking-2507  # ⚠️ MUST USE THINKING MODEL, NOT INSTRUCT!
```

**WARNING**: The instruct model (`qwen3-235b-a22b-instruct-2507`) causes excessive tool calling. Always verify the thinking model is configured.

### Embedding Configuration
```bash
EMBEDDING_PROVIDER=jina
EMBEDDING_MODEL=jina-embeddings-v4
EMBEDDING_BASE_URL=https://api.jina.ai/v1
EMBEDDING_API_KEY=jina_7c2cc29c993b49ad858c1cf12b93e8d8j7NFNzGqR6fWxaUtOZ0YMBbFgRYE
VECTOR_DIMENSION=2048
EMBEDDING_CHUNK_SIZE=8191
```

### Database Connections
```bash
# PostgreSQL (Neon Cloud)
DATABASE_URL=postgresql://neondb_owner:Wk7kxtEfWwjX@ep-fancy-meadow-a7kkygxb-pooler.ap-southeast-2.aws.neon.tech/neondb?sslmode=require
POSTGRES_HOST=ep-fancy-meadow-a7kkygxb-pooler.ap-southeast-2.aws.neon.tech
POSTGRES_PORT=5432
POSTGRES_USER=neondb_owner
POSTGRES_DB=neondb

# Neo4j (Local Docker)
NEO4J_URI=bolt://localhost:7688
NEO4J_USER=neo4j
NEO4J_PASSWORD=agpassword123
```

## 📁 Production Directory Structure

```
agentic-rag-knowledge-graph/
├── agent/                      # Core AI agent implementation
│   ├── __init__.py            # Package initialization
│   ├── agent.py               # Main Pydantic AI agent
│   ├── api.py                 # FastAPI server & endpoints
│   ├── cache_manager_prod.py  # Production caching system
│   ├── db_utils.py            # PostgreSQL database utilities
│   ├── error_handler_prod.py  # Production error handling
│   ├── graph_utils.py         # Neo4j graph database utilities
│   ├── models.py              # Pydantic data models
│   ├── prompts.py             # System prompts
│   ├── providers.py           # LLM provider configuration
│   ├── providers_extended.py  # Extended embedding providers
│   ├── tools.py               # Agent tools (search functions)
│   └── legacy/                # Non-production/old files
│       ├── agent_prepare.py
│       ├── jina_embedder.py
│       ├── prompts_updated.py
│       ├── providers_extended_backup.py
│       ├── providers_extended_old.py
│       ├── providers_jina_patch.py
│       └── tools_update.py
│
├── ingestion/                  # Document processing pipeline
│   ├── __init__.py
│   ├── chunker.py             # Text chunking logic
│   ├── embedder_jina_v2_prod.py # Production Jina embedder
│   ├── graph_builder.py       # Knowledge graph construction
│   ├── ingest.py              # Main ingestion orchestrator
│   └── legacy/                # Old embedder implementations
│       ├── embedder.py
│       ├── embedder_jina.py
│       └── embedder_jina_optimized_v3.py
│
├── documents/                  # Source documents
│   └── practical_strategy_book.md  # Main book content
│
├── sql/                        # Database schemas & functions
│   ├── 000_base_schema.sql    # Core tables
│   ├── 001_vector_functions.sql # Vector search functions
│   ├── 002_hybrid_search.sql  # Hybrid search implementation
│   └── 003_performance_indexes.sql # Performance optimizations
│
├── tests/                      # Test suite
│   └── agent/                 # Agent-specific tests
│       ├── test_db_utils.py
│       └── test_models.py
│
├── migrations/                 # Database migrations
├── backups/                   # Code backups
├── test_results/              # Test output storage
├── big_tech_docs/             # Reference documentation
├── legacy_scripts/            # Moved utility scripts
├── legacy_tests/              # Moved test files
│
├── .env                       # Environment configuration
├── requirements.txt           # Python dependencies
├── cli.py                     # Command-line interface
├── start_api.py              # API startup script
├── manage_api.sh             # API management script
├── docker-compose.neo4j.yml  # Neo4j container config
├── pytest.ini                # Pytest configuration
└── README.md                 # Project documentation
```

## 🏗️ System Architecture

### Component Overview
```
┌─────────────────────────────────────────────────────────────────┐
│                        Client Layer                             │
│  ┌─────────────────┐    ┌─────────────────┐                   │
│  │   REST API      │    │  SSE Streaming  │                   │
│  │  (FastAPI)      │    │   (Chat)        │                   │
│  └─────────────────┘    └─────────────────┘                   │
├─────────────────────────────────────────────────────────────────┤
│                    Agentic AI Layer                            │
│  ┌─────────────────┐    ┌─────────────────┐                   │
│  │  Pydantic AI    │    │   Tool Router   │                   │
│  │    Agent        │◄──►│  (Intelligent   │                   │
│  │ (Qwen3 Thinking)│    │   Selection)    │                   │
│  └─────────────────┘    └─────────────────┘                   │
├─────────────────────────────────────────────────────────────────┤
│                   Search & Retrieval Layer                     │
│  ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐  │
│  │  Vector Search  │ │  Graph Search   │ │  Hybrid Search  │  │
│  │ (Jina v4 2048d) │ │  (Neo4j)        │ │  (Combined)     │  │
│  └─────────────────┘ └─────────────────┘ └─────────────────┘  │
├─────────────────────────────────────────────────────────────────┤
│                    Caching & Error Handling                    │
│  ┌─────────────────┐    ┌─────────────────┐                   │
│  │  Cache Manager  │    │ Error Handler  │                   │
│  │  (LRU + TTL)    │    │ (Retry Logic)  │                   │
│  └─────────────────┘    └─────────────────┘                   │
├─────────────────────────────────────────────────────────────────┤
│                      Storage Layer                             │
│  ┌─────────────────┐    ┌─────────────────┐                   │
│  │  PostgreSQL     │    │      Neo4j      │                   │
│  │  + pgvector     │    │  (Knowledge     │                   │
│  │  (Neon Cloud)   │    │   Graph)        │                   │
│  └─────────────────┘    └─────────────────┘                   │
└─────────────────────────────────────────────────────────────────┘
```

## 🔌 API Endpoints

### Health & Status
- `GET /` - Welcome message
- `GET /health` - System health check (DB, Graph, LLM status)

### Search Operations
- `POST /search/vector` - Semantic similarity search
- `POST /search/graph` - Knowledge graph relationship search
- `POST /search/hybrid` - Combined vector + text search

### Document Management
- `GET /documents` - List all documents
- `GET /documents/{document_id}` - Get specific document

### Chat Interface
- `POST /chat` - Single-turn chat interaction
- `POST /chat/stream` - Server-sent events streaming chat

### Session Management
- `POST /sessions` - Create new chat session
- `GET /sessions/{session_id}` - Get session with messages

## 🗄️ Database Schema

### PostgreSQL Tables
```sql
-- Documents table
documents (
    id UUID PRIMARY KEY,
    title TEXT NOT NULL,
    source TEXT NOT NULL,
    content TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP
)

-- Vector embeddings (Jina v4 - 2048 dimensions)
chunks_jina (
    id UUID PRIMARY KEY,
    document_id UUID REFERENCES documents(id),
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    embedding vector(2048),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP
)

-- Chat sessions
sessions (
    id UUID PRIMARY KEY,
    user_id TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP
)

-- Message history
messages (
    id UUID PRIMARY KEY,
    session_id UUID REFERENCES sessions(id),
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP
)
```

### Neo4j Graph Schema
- **Nodes**: Entities extracted from documents
- **Relationships**: Connections between entities
- **Properties**: Metadata and temporal information

## 🚀 Production Deployment

### Starting the System

1. **SSH to Server**:
```bash
# Via Claude with do-ssh MCP
ssh_execute command="cd /opt/practical-strategy-poc/agentic-rag-knowledge-graph"
```

2. **Start API Server**:
```bash
# Background execution (CRITICAL - avoid blocking)
cd /opt/practical-strategy-poc/agentic-rag-knowledge-graph && \
bash -c 'nohup python3 -m agent.api > api.log 2>&1 & echo $!' > api.pid

# Check if running
cat api.pid && ps aux | grep $(cat api.pid) | grep -v grep

# Stop server
kill $(cat api.pid)
```

3. **Monitor Logs**:
```bash
tail -f api.log
```

### Health Verification
```bash
curl http://localhost:8058/health
# Expected: {"status":"healthy","database":true,"graph_database":true,"llm_connection":true}
```

## 🔧 Configuration Management

### Environment Variables Priority
1. `.env` file in project root
2. System environment variables
3. Default values in code

### Critical Settings
- **Always use Qwen3 thinking model** (not instruct)
- **Jina embeddings v4** with 2048 dimensions
- **Connection pooling** properly configured
- **Error retry logic** with exponential backoff

## 📊 Performance Characteristics

### Response Times
- Simple queries: ~20-30 seconds
- Medium complexity: ~30-40 seconds  
- Complex queries: ~40-50 seconds

### Resource Usage
- Memory: ~2-3GB under normal load
- CPU: Moderate usage during inference
- Network: Dependent on LLM API calls

## 🛡️ Security Considerations

### API Keys
- Stored in `.env` file (not in version control)
- Qwen3 API key for Dashscope
- Jina API key for embeddings
- Database credentials

### Network Security
- API runs on localhost only
- External access via reverse proxy (if needed)
- CORS configured for specific origins

## 🔄 Maintenance Procedures

### Database Maintenance
```bash
# Backup PostgreSQL
pg_dump $DATABASE_URL > backup.sql

# Neo4j backup via Docker
docker exec neo4j neo4j-admin backup --to=/backup
```

### Log Rotation
```bash
# Rotate API logs
mv api.log api.log.$(date +%Y%m%d)
touch api.log
```

### System Updates
1. Pull latest code from GitHub
2. Update dependencies: `pip install -r requirements.txt`
3. Run migrations if needed
4. Restart API server

## 📈 Monitoring & Debugging

### Key Metrics
- API response times
- Tool usage patterns
- Error rates
- Database query performance

### Debug Commands
```bash
# Check system resources
htop

# View API logs
tail -f api.log | grep ERROR

# Database connections
psql $DATABASE_URL -c "SELECT count(*) FROM pg_stat_activity;"

# Neo4j status
docker logs neo4j
```

## 🚨 Troubleshooting

### Common Issues

1. **Excessive Tool Calling**
   - Verify thinking model is configured (not instruct)
   - Check LLM_CHOICE in .env

2. **Connection Pool Errors**
   - Restart API to reset connections
   - Check database connection limits

3. **Embedding Failures**
   - Verify Jina API key is valid
   - Check rate limits

4. **Memory Issues**
   - Monitor with `htop`
   - Restart API if needed
   - Consider increasing server resources

---

## 📝 Summary

This system is a production-ready agentic RAG knowledge graph implementation using:
- **Qwen3 thinking model** (critical for proper operation)
- **Pydantic AI** for intelligent agent behavior
- **Jina v4 embeddings** (2048 dimensions)
- **PostgreSQL + pgvector** for vector storage
- **Neo4j** for knowledge graph
- **FastAPI** for REST/streaming API

The system is deployed on DigitalOcean and configured for business strategy consulting based on the Practical Strategy book content.
