# Deploy to Render - Step by Step

## Prerequisites
1. Neo4j Aura account (free tier available at https://neo4j.com/cloud/aura/)
2. Your existing Neon PostgreSQL credentials
3. Qwen3 API key (Dashscope)
4. Jina API key

## Step 1: Set up Neo4j Aura (5 minutes)
1. Go to https://neo4j.com/cloud/aura/
2. Create a free instance
3. Save the connection URI and password
4. Update your Neo4j environment variables with the cloud instance

## Step 2: Push Changes to GitHub
```bash
git add Dockerfile render.yaml RENDER_ENV_VARS.md RENDER_DEPLOYMENT.md agent/api.py
git commit -m "Add Render deployment configuration"
git push origin main
```

## Step 3: Deploy on Render
1. Go to https://dashboard.render.com/
2. Click "New +" → "Web Service"
3. Connect your GitHub repository: `camtang26/practical-strategy-poc`
4. Render will auto-detect the `render.yaml` file
5. Review the configuration and click "Create Web Service"

## Step 4: Add Environment Variables
1. In Render dashboard, go to your service
2. Click "Environment" tab
3. Add all variables from `RENDER_ENV_VARS.md`
4. Click "Save Changes" - this will trigger a redeploy

## Step 5: Update Frontend
Once deployed, Render will give you an HTTPS URL like:
`https://practical-strategy-api.onrender.com`

Update your frontend:
1. Go to Vercel dashboard
2. Settings → Environment Variables
3. Add: `VITE_API_URL=https://practical-strategy-api.onrender.com`
4. Redeploy

## Notes
- First deploy may take 10-15 minutes
- Free tier spins down after 15 min of inactivity (first request will be slow)
- Logs available in Render dashboard
- Health check: `https://your-service.onrender.com/health`

## Troubleshooting
- If health check fails, check logs in Render dashboard
- Ensure all environment variables are set correctly
- Neo4j Aura connection requires the `neo4j+s://` protocol
- Database URLs must include `?sslmode=require` for PostgreSQL