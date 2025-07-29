# Practical Strategy AI Agent - Frontend

This is the local development frontend for the Practical Strategy AI Agent. It provides a chat interface for interacting with the AI agent backend.

## Features

- 🚀 **Fast Hot Reloading**: Vite-powered development with instant updates
- 💬 **Real-time Chat**: Streaming responses from the AI agent
- 🔗 **Remote Backend Connection**: Configured to connect to Digital Ocean API
- 🎯 **Type-Safe**: Built with TypeScript for better development experience
- ⚡ **Optimized Proxy**: API requests are proxied through Vite for CORS handling

## Setup

1. **Install Dependencies**
   ```bash
   npm install
   ```

2. **Configure Environment** (optional)
   The `.env` file is already configured to point to the remote backend:
   ```
   VITE_API_URL=http://170.64.129.131:8058
   ```

3. **Start Development Server**
   ```bash
   npm run dev
   ```

   The app will be available at `http://localhost:5173`

## Hot Reload Configuration

The Vite configuration is optimized for consistent hot reloading:

- **File Watching**: Uses native file system events (set `usePolling: true` if experiencing issues)
- **Host Binding**: Configured to bind to `0.0.0.0` for network access
- **API Proxy**: All `/api/*` requests are proxied to the remote backend

If hot reload is inconsistent, try:
1. Setting `usePolling: true` in `vite.config.ts`
2. Increasing the `interval` value
3. Ensuring no antivirus software is interfering

## API Integration

The frontend uses a proxy configuration to handle API requests:
- Frontend requests to `/api/*` are forwarded to the backend
- CORS is handled automatically by the proxy
- Request/response logging is enabled for debugging

### Available Endpoints

- `/api/health` - Check backend health status
- `/api/chat` - Send chat messages
- `/api/chat/stream` - Streaming chat responses (SSE)
- `/api/search/vector` - Vector similarity search
- `/api/search/graph` - Knowledge graph search
- `/api/search/hybrid` - Combined search

## Project Structure

```
frontend/
├── src/
│   ├── components/
│   │   ├── Chat.tsx        # Main chat interface
│   │   └── Chat.css        # Chat styling
│   ├── services/
│   │   └── api.ts          # API client service
│   ├── App.tsx             # Root component
│   ├── App.css             # App styling
│   └── main.tsx           # Entry point
├── .env                    # Environment configuration
├── vite.config.ts          # Vite configuration
└── package.json            # Dependencies
```

## Troubleshooting

### Connection Issues
- Ensure the backend API is running on port 8058
- Check that the Digital Ocean droplet is accessible
- Verify the API health at http://170.64.129.131:8058/health

### Hot Reload Not Working
1. Check console for file watching errors
2. Try restarting the dev server
3. Enable polling in vite.config.ts
4. Clear browser cache

### Build for Production
```bash
npm run build
```

The production build will be in the `dist/` directory.

## Development Tips

- The chat interface shows connection status in real-time
- Debug information is available in the expandable section at the bottom
- All API requests are logged to the browser console
- Session IDs are generated automatically for conversation tracking