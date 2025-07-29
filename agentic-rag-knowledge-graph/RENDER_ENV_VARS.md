# Render Environment Variables

Add these environment variables in your Render dashboard:

## Database Configuration
```
DATABASE_URL=postgresql://neondb_owner:YOUR_PASSWORD@ep-fancy-meadow-a7kkygxb-pooler.ap-southeast-2.aws.neon.tech/neondb?sslmode=require
POSTGRES_HOST=ep-fancy-meadow-a7kkygxb-pooler.ap-southeast-2.aws.neon.tech
POSTGRES_PORT=5432
POSTGRES_USER=neondb_owner
POSTGRES_PASSWORD=YOUR_NEON_PASSWORD
POSTGRES_DB=neondb
```

## Knowledge Graph (Neo4j)
```
NEO4J_URI=neo4j+s://YOUR_NEO4J_INSTANCE.databases.neo4j.io
NEO4J_USER=neo4j
NEO4J_PASSWORD=YOUR_NEO4J_PASSWORD
```
**Note**: You'll need to use a cloud Neo4j instance (Neo4j Aura) since Render doesn't support local Neo4j.

## AI Configuration
```
LLM_PROVIDER=qwen
LLM_CHOICE=qwen3-235b-a22b-thinking-2507
LLM_API_KEY=YOUR_DASHSCOPE_API_KEY
ENABLE_THINKING=true
```

## Embeddings
```
EMBEDDING_PROVIDER=jina
EMBEDDING_MODEL=jina-embeddings-v4
EMBEDDING_BASE_URL=https://api.jina.ai/v1
EMBEDDING_API_KEY=YOUR_JINA_API_KEY
VECTOR_DIMENSION=2048
EMBEDDING_CHUNK_SIZE=8191
```

## Server Configuration
```
PORT=8058
PYTHON_ENV=production
```

## CORS (if needed)
```
CORS_ORIGINS=https://practical-strategy-poc.vercel.app,https://your-custom-domain.com
```