import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  
  return {
    plugins: [react()],
    server: {
      host: '0.0.0.0',
      port: 5173,
      // Enhanced hot reload settings
      watch: {
        usePolling: false, // Set to true if hot reload is inconsistent
        interval: 100
      },
      // Proxy API requests to remote backend
      proxy: {
        '/api': {
          target: env.VITE_API_URL || 'http://170.64.129.131:8058',
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/api/, ''),
          configure: (proxy) => {
            proxy.on('error', (err) => {
              console.log('proxy error', err);
            });
          },
        }
      }
    }
  }
})
