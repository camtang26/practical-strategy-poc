# Practical Strategy AI Agent - Project Documentation

## 🎯 Project Overview

This is an **agentic RAG (Retrieval-Augmented Generation) knowledge graph system** built as a client demo/MVP for a business strategy book author. The system creates an AI agent that can act as if it wrote the author's comprehensive business strategy book, providing expert-level consultative responses with full context and understanding of the "Practical Strategy" methodology.

### Business Purpose
- **Client**: Business strategy book author seeking to demonstrate AI-powered knowledge retrieval
- **Goal**: Create an AI agent that embodies the author's expertise and can provide consultative guidance
- **Use Case**: Standalone application for strategic business consulting based on the book's content
- **Target Audience**: Business professionals seeking strategic guidance and planning assistance

## 🏗️ Architecture Overview

Built on the **ottomator-agents** framework, this system combines multiple AI technologies:

```
┌─────────────────────────────────────────────────────────────────┐
│                     Client Interface                            │
│  ┌─────────────────┐    ┌─────────────────┐                   │
│  │  Web Interface  │    │  API Endpoints  │                   │
│  │   (Chat UI)     │    │   (REST/SSE)    │                   │
│  └─────────────────┘    └─────────────────┘                   │
├─────────────────────────────────────────────────────────────────┤
│                    Agentic AI Layer                            │
│  ┌─────────────────┐    ┌─────────────────┐                   │
│  │  Pydantic AI    │    │  Intelligent    │                   │
│  │    Agent        │◄──►│  Tool Selection │                   │
│  │  (Gemini 2.5)   │    │  & Execution    │                   │
│  └─────────────────┘    └─────────────────┘                   │
├─────────────────────────────────────────────────────────────────┤
│                   Search & Retrieval Layer                     │
│  ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐  │
│  │  Vector Search  │ │  Graph Search   │ │  Hybrid Search  │  │
│  │ (Jina v4 2048d) │ │  (Neo4j+Graph.) │ │  (Combined)     │  │
│  └─────────────────┘ └─────────────────┘ └─────────────────┘  │
├─────────────────────────────────────────────────────────────────┤
│                      Storage Layer                             │
│  ┌─────────────────┐    ┌─────────────────┐                   │
│  │  PostgreSQL     │    │      Neo4j      │                   │
│  │  + pgvector     │    │  (Knowledge     │                   │
│  │  (Neon Cloud)   │    │   Graph)        │                   │
│  └─────────────────┘    └─────────────────┘                   │
└─────────────────────────────────────────────────────────────────┘
```

## 🛠️ Complete Tech Stack

### **Core AI Framework**
- **Pydantic AI** - Main agentic framework for intelligent tool selection
- **Ottomator-Agents** - Enhanced RAG capabilities with knowledge graph integration
- **Gemini 2.5 Pro** - Primary language model for responses
- **Jina Embeddings v4** - State-of-the-art multimodal embeddings (2048 dimensions, 32k context)

### **Database & Storage**
- **PostgreSQL + pgvector** - Vector embeddings storage (Neon Cloud)
- **Neo4j + Graphiti** - Knowledge graph database for entity relationships
- **Document Storage** - Processed markdown documents with metadata

### **Search Capabilities**
- **Vector Search** - Semantic similarity using Jina embeddings
- **Graph Search** - Relationship-based retrieval via Neo4j
- **Hybrid Search** - Combined vector + text search with intelligent weighting
- **Temporal Knowledge** - Time-aware information tracking

### **API & Infrastructure**
- **FastAPI** - Backend API with streaming responses
- **DigitalOcean** - Cloud deployment platform
- **Docker** - Containerization for databases
- **CORS & Security** - Cross-origin support with proper headers

## 🚀 Current Deployment Status

### **Production Environment**
- **Server**: DigitalOcean droplet
- **API Endpoint**: `http://localhost:8058`
- **Status**: ✅ Healthy and operational
- **Database**: Connected to Neon PostgreSQL cloud
- **Knowledge Graph**: Neo4j running locally

### **System Health Check**
```bash
curl http://localhost:8058/health
# Returns: {"status":"healthy","database":true,"graph_database":true,"llm_connection":true}
```

## 📚 Document Knowledge Base

### **Primary Content**
- **Practical Strategy Book** (`practical_strategy_book.md`)
  - **Size**: 265,382 bytes of comprehensive business strategy content
  - **Chunks**: 106 semantically processed chunks
  - **Embeddings**: Jina v4 embeddings with 2048 dimensions
  - **Coverage**: Complete business strategy methodology

### **Content Processing**
- **Semantic Chunking** - Intelligent text segmentation
- **Entity Extraction** - Automated knowledge graph building
- **Metadata Enrichment** - Source citations and context
- **Multimodal Ready** - Support for future image content

## 🔧 Configuration & Setup

### **Environment Variables**
```bash
# Database Configuration
DATABASE_URL=postgresql://user:pass@host/db
POSTGRES_HOST=ep-fancy-meadow-a7kkygxb-pooler.ap-southeast-2.aws.neon.tech
POSTGRES_PORT=5432
POSTGRES_USER=neondb_owner
POSTGRES_DB=neondb

# Knowledge Graph
NEO4J_URI=bolt://localhost:7688
NEO4J_USER=neo4j
NEO4J_PASSWORD=agpassword123

# AI Configuration
LLM_PROVIDER=google
LLM_CHOICE=gemini-2.5-pro
LLM_API_KEY=your_gemini_api_key

# Embeddings
EMBEDDING_PROVIDER=jina
EMBEDDING_MODEL=jina-embeddings-v4
EMBEDDING_BASE_URL=https://api.jina.ai/v1
EMBEDDING_API_KEY=your_jina_api_key
VECTOR_DIMENSION=2048
EMBEDDING_CHUNK_SIZE=8191
```

## 🛡️ Database Schema

### **Core Tables**
```sql
-- Documents storage
CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title TEXT NOT NULL,
    source TEXT NOT NULL,
    content TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Vector embeddings (Jina v4)
CREATE TABLE chunks_jina (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    embedding vector(2048),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Chat sessions
CREATE TABLE sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Message history
CREATE TABLE messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID REFERENCES sessions(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
```

### **Optimized Indexes**
```sql
-- Vector similarity search
CREATE INDEX chunks_jina_content_gin_idx ON chunks_jina USING gin(to_tsvector('english', content));
CREATE INDEX chunks_jina_document_id_idx ON chunks_jina(document_id);

-- Document metadata search
CREATE INDEX idx_documents_metadata ON documents USING GIN (metadata);
```

## 🔌 API Endpoints

### **Health & Status**
- `GET /health` - System health check
- `GET /` - Welcome message with system info

### **Search Operations**
- `POST /search/vector` - Semantic similarity search
- `POST /search/graph` - Knowledge graph relationship search  
- `POST /search/hybrid` - Combined vector + text search

### **Document Management**
- `GET /documents` - List all documents
- `GET /documents/{id}` - Get specific document

### **Chat Interface**
- `POST /chat` - Single-turn conversation
- `POST /chat/stream` - Streaming chat responses
- `GET /sessions/{session_id}` - Get chat history

### **Example API Usage**
```bash
# Vector search for strategic thinking concepts
curl -X POST http://localhost:8058/search/vector \
  -H "Content-Type: application/json" \
  -d '{"query": "What are the key principles of strategic thinking?", "k": 5}'

# Streaming chat about business strategy
curl -X POST http://localhost:8058/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"message": "How do I develop a strategic plan for my organization?", "session_id": "uuid"}'
```

## 🧠 Intelligent Agent Capabilities

### **Tool Selection**
The Pydantic AI agent automatically selects the best search strategy:
- **Vector Search**: For semantic similarity and concept matching
- **Graph Search**: For relationship and entity-based queries
- **Hybrid Search**: For complex queries requiring both approaches
- **Document Retrieval**: For specific source material access

### **Response Generation**
- **Context-Aware**: Maintains conversation history and context
- **Source Citations**: Provides specific references to book content
- **Streaming**: Real-time response generation
- **Multimodal Ready**: Prepared for text and image inputs

## 🔄 Development Workflow

### **Code Organization**
```
agentic-rag-knowledge-graph/
├── agent/               # AI agent core
│   ├── agent.py        # Pydantic AI agent
│   ├── api.py          # FastAPI endpoints
│   ├── tools.py        # Search tools
│   ├── prompts.py      # System prompts
│   └── providers.py    # LLM providers
├── ingestion/          # Document processing
│   ├── ingest.py       # Main ingestion
│   ├── chunker.py      # Text chunking
│   └── embedder.py     # Embedding generation
├── sql/                # Database schemas
├── documents/          # Source documents
└── tests/              # Test suite
```

### **Development Guidelines**
- **Modularity**: Keep files under 500 lines, split into logical modules
- **Testing**: Comprehensive pytest suite with unit tests
- **Documentation**: Google-style docstrings for all functions
- **Type Hints**: Full type annotations using Pydantic models
- **Error Handling**: Graceful failure with proper logging

## 🚨 Troubleshooting & Maintenance

### **Common Issues**
1. **Neo4j Connection**: Ensure Docker container is running
2. **Embedding API**: Check Jina API key and rate limits
3. **Database Performance**: Monitor pgvector index efficiency
4. **Memory Usage**: Watch for large document processing

### **Monitoring**
```bash
# Check API health
curl http://localhost:8058/health

# Monitor logs
tail -f api.log

# Database connections
docker ps | grep postgres
docker ps | grep neo4j
```

### **Performance Optimization**
- **Vector Indexes**: Use HNSW for large datasets (current: ivfflat)
- **Chunking Strategy**: Optimize chunk size for specific domains
- **Caching**: Implement Redis for frequent queries
- **Connection Pooling**: Monitor database connection usage

## 📈 Future Enhancements

### **Planned Features**
- **Multimodal Support**: Image embeddings with Jina v4
- **Advanced Analytics**: Query pattern analysis
- **User Management**: Authentication and user sessions
- **API Rate Limiting**: Request throttling and quotas
- **Webhook Integration**: Real-time notifications

### **Scalability Considerations**
- **Horizontal Scaling**: Multiple API instances
- **Database Sharding**: Distribute vector storage
- **CDN Integration**: Cache static responses
- **Load Balancing**: Multi-region deployment

## 🎯 Success Metrics

### **Performance Targets**
- **Response Time**: < 2 seconds for search queries
- **Accuracy**: High relevance scores (>0.7 similarity)
- **Availability**: 99.9% uptime
- **Scalability**: Support for 1000+ concurrent users

### **Business Value**
- **Expert Knowledge Access**: 24/7 strategic consulting
- **Consistent Responses**: Standardized methodology application
- **Scalable Expertise**: Serve multiple clients simultaneously
- **Cost Efficiency**: Reduce human consultant dependencies

---

## 📞 Support & Contact

For technical issues, deployment questions, or enhancement requests related to this Practical Strategy AI Agent system, refer to the project documentation and logs for debugging information.

**Remember**: This system represents the cutting edge of agentic RAG technology, combining semantic search, knowledge graphs, and intelligent agent capabilities to deliver expert-level business strategy consulting at scale.

---

## 🧠 Project Memory Agents

This project uses specialized memory agents to preserve context and prevent re-discovery of solutions. Located in `.claude/agents/`:

### Available Memory Agents

**database-memory**
- Purpose: PostgreSQL and Neo4j operations, memory management, migration patterns
- Consult when: Working with databases, fixing memory issues, creating indexes
- Key knowledge: Neo4j memory limits (1.5GB), pgvector dimension constraints, migration scripts

**deployment-memory**
- Purpose: Digital Ocean SSH patterns, Docker management, API backgrounding
- Consult when: Deploying services, backgrounding processes, managing containers
- Key knowledge: bash -c wrapper for nohup, memory constraints (3.8GB total), process management

**embeddings-memory**
- Purpose: Jina API quirks, dimension handling, multi-provider support
- Consult when: Working with embeddings, fixing API errors, switching providers
- Key knowledge: Jina rejects encoding_format parameter, custom HTTP client required, 2048 dimensions

**llm-memory**
- Purpose: LLM provider configurations, tool calling issues, Gemini to Qwen3 transition
- Consult when: Configuring LLMs, debugging tool selection, switching providers
- Key knowledge: Gemini ignores search_type constraints, Qwen3 superior for tool calling

**search-memory**
- Purpose: Vector/graph/hybrid search implementations, SQL functions, performance
- Consult when: Optimizing search, writing SQL functions, debugging empty results
- Key knowledge: Provider filtering required, RRF scoring, ~2.6s hybrid search time

**graphiti-memory**
- Purpose: Knowledge graph building, entity extraction, batch processing
- Consult when: Building graphs, extracting entities, managing long processes
- Key knowledge: ~50s per chunk processing, 4-hour total time, Gemini configuration

### Usage Protocol

1. **BEFORE** working on any domain below, consult its agent:
   ```
   Task("Consult database-memory agent for Neo4j configuration")
   ```

2. **AFTER** discovering new solutions, update the agent:
   ```
   Task("Update embeddings-memory with new Jina API discovery")
   ```

3. **When stuck**, check if a memory agent has the solution:
   ```
   Task("Check all memory agents for similar issues")
   ```

### Why This Matters

These agents prevent:
- Re-solving the same problems (e.g., Jina API quirks)
- Forgetting working configurations (e.g., Neo4j memory settings)
- Breaking integrations you forgot about (e.g., dimension mismatches)
- Wasting time on known issues (e.g., Gemini tool calling)

### Critical Known Issues

1. **Server Memory**: Only 3.8GB total RAM - carefully manage service memory
2. **Jina API**: MUST use custom HTTP client, not OpenAI client
3. **Gemini Tool Calling**: Doesn't respect constraints - switching to Qwen3
4. **Neo4j Container**: Limited to 1.5GB memory or crashes
5. **Background Processes**: Must use `bash -c 'nohup ... &'` pattern

### Quick Command Reference

```bash
# Start API (use this exact pattern!)
cd /opt/practical-strategy-poc/agentic-rag-knowledge-graph && bash -c 'nohup python3 -m agent.api > api.log 2>&1 &'

# Check services
docker ps
ps aux | grep python
curl http://localhost:8000/health

# Monitor memory
free -h
docker stats --no-stream
```

Remember: These memory agents are PROJECT-SPECIFIC - they know THIS codebase and its unique challenges!
