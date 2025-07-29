// API Client for Practical Strategy Agent

// In production, use the full backend URL. In dev, use the proxy.
const API_BASE = import.meta.env.PROD 
  ? import.meta.env.VITE_API_URL || 'https://practicalstrat.duckdns.org'
  : '/api';

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  timestamp?: string;
  tools?: ToolCall[];
  model_used?: string;
}

export interface ToolCall {
  tool_name: string;
  args: Record<string, any>;
  tool_call_id?: string;
}

export interface ChatRequest {
  message: string;
  session_id?: string;
  model_choice?: string;
}

export interface SearchRequest {
  query: string;
  k?: number;
  search_type?: 'vector' | 'graph' | 'hybrid';
}

export interface HealthResponse {
  status: string;
  database: boolean;
  graph_database: boolean;
  llm_connection: boolean;
}

class ApiClient {
  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${API_BASE}${endpoint}`;
    
    try {
      const response = await fetch(url, {
        ...options,
        headers: {
          'Content-Type': 'application/json',
          ...options.headers,
        },
      });

      if (!response.ok) {
        throw new Error(`API Error: ${response.status} ${response.statusText}`);
      }

      return await response.json();
    } catch (error) {
      console.error(`API request failed for ${endpoint}:`, error);
      throw error;
    }
  }

  // Health check
  async checkHealth(): Promise<HealthResponse> {
    return this.request<HealthResponse>('/health');
  }

  // Chat endpoints
  async sendMessage(request: ChatRequest): Promise<any> {
    return this.request('/chat', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  // Streaming chat
  async sendStreamingMessage(
    request: ChatRequest,
    onChunk: (chunk: string) => void,
    onTools?: (tools: ToolCall[]) => void,
    onError?: (error: Error) => void,
    onModel?: (model: string) => void
  ): Promise<void> {
    try {
      const response = await fetch(`${API_BASE}/chat/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(request),
      });

      if (!response.ok) {
        throw new Error(`API Error: ${response.status} ${response.statusText}`);
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();

      if (!reader) {
        throw new Error('No response body');
      }

      let buffer = '';
      
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        buffer += chunk;
        
        // Process complete lines
        const lines = buffer.split('\n');
        buffer = lines.pop() || ''; // Keep incomplete line in buffer
        
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6).trim();
            if (data === '[DONE]') {
              return;
            }
            try {
              const parsed = JSON.parse(data);
              
              if (parsed.type === 'text' && parsed.content) {
                onChunk(parsed.content);
              } else if (parsed.type === 'tools' && parsed.tools) {
                onTools?.(parsed.tools);
              } else if (parsed.type === 'model' && parsed.model_used) {
                onModel?.(parsed.model_used);
              }
            } catch (e) {
              console.warn('Failed to parse SSE chunk:', e);
            }
          }
        }
      }
      
      // Process any remaining data in buffer
      if (buffer.trim()) {
        console.warn('Incomplete SSE message in buffer:', buffer);
      }
    } catch (error) {
      console.error('Streaming error:', error);
      onError?.(error as Error);
      throw error;
    }
  }

  // Search endpoints
  async vectorSearch(request: SearchRequest): Promise<any> {
    return this.request('/search/vector', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  async graphSearch(request: SearchRequest): Promise<any> {
    return this.request('/search/graph', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  async hybridSearch(request: SearchRequest): Promise<any> {
    return this.request('/search/hybrid', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  // Documents
  async getDocuments(): Promise<any[]> {
    return this.request('/documents');
  }

  async getDocument(id: string): Promise<any> {
    return this.request(`/documents/${id}`);
  }

  // Sessions
  async getSession(sessionId: string): Promise<any> {
    return this.request(`/sessions/${sessionId}`);
  }
}

const apiClient = new ApiClient();

export { apiClient as api };