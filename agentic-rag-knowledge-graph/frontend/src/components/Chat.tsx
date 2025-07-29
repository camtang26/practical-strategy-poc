import { useState, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { tomorrow } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { api } from '../services/api';
import type { ChatMessage, HealthResponse, ToolCall } from '../services/api';
import './Chat.css';

export function Chat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [sessionId] = useState(() => crypto.randomUUID());
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const messageIdRef = useRef<number>(0);

  // Check API health on mount
  useEffect(() => {
    checkHealth();
  }, []);

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const checkHealth = async () => {
    try {
      const healthStatus = await api.checkHealth();
      setHealth(healthStatus);
      setError(null);
    } catch (err) {
      setError('Failed to connect to backend API. Please ensure the API is running on port 8058.');
      console.error('Health check failed:', err);
    }
  };

  const sendMessage = async () => {
    if (!input.trim() || isLoading) return;

    const userMessage: ChatMessage = {
      role: 'user',
      content: input,
      timestamp: new Date().toISOString(),
    };

    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setIsLoading(true);
    setError(null);

    // Generate unique message ID for this response
    ++messageIdRef.current;
    const responseContentRef = { current: '' };
    const toolsRef = { current: [] as ToolCall[] };

    const assistantMessage: ChatMessage = {
      role: 'assistant',
      content: '',
      timestamp: new Date().toISOString(),
      tools: [],
    };

    setMessages(prev => [...prev, assistantMessage]);

    try {
      await api.sendStreamingMessage(
        {
          message: userMessage.content,
          session_id: sessionId,
        },
        (chunk) => {
          // Accumulate content in ref (not affected by React re-renders)
          responseContentRef.current += chunk;
          
          // Update state with complete content
          setMessages(prev => {
            const newMessages = [...prev];
            const lastMessage = newMessages[newMessages.length - 1];
            if (lastMessage && lastMessage.role === 'assistant') {
              lastMessage.content = responseContentRef.current;
              lastMessage.tools = toolsRef.current;
            }
            return newMessages;
          });
        },
        (tools) => {
          // Update tools
          toolsRef.current = tools;
          
          // Update message with tools
          setMessages(prev => {
            const newMessages = [...prev];
            const lastMessage = newMessages[newMessages.length - 1];
            if (lastMessage && lastMessage.role === 'assistant') {
              lastMessage.tools = tools;
            }
            return newMessages;
          });
        },
        (error) => {
          setError(`Streaming error: ${error.message}`);
        }
      );
    } catch (err: any) {
      setError(`Failed to send message: ${err.message}`);
      setMessages(prev => {
        const newMessages = [...prev];
        const lastMessage = newMessages[newMessages.length - 1];
        if (lastMessage && lastMessage.role === 'assistant') {
          lastMessage.content = 'Error: Failed to get response from the server.';
        }
        return newMessages;
      });
    } finally {
      setIsLoading(false);
    }
  };

  const getHealthStatusClass = () => {
    if (!health) return 'status-unknown';
    if (health.database && health.graph_database && health.llm_connection) {
      return 'status-healthy';
    }
    return 'status-unhealthy';
  };

  const renderToolUsage = (tools: ToolCall[] | undefined) => {
    if (!tools || tools.length === 0) return null;

    return (
      <div className="tools-used">
        <div className="tools-header">🛠 Tools Used:</div>
        {tools.map((tool, index) => (
          <div key={index} className="tool-item">
            <span className="tool-name">{index + 1}. {tool.tool_name}</span>
            {tool.args && (
              <span className="tool-args">
                {tool.args.query && (
                  <span className="tool-arg">
                    query="{tool.args.query.length > 50 
                      ? tool.args.query.substring(0, 50) + '...' 
                      : tool.args.query}"
                  </span>
                )}
                {tool.args.limit && (
                  <span className="tool-arg">limit={tool.args.limit}</span>
                )}
              </span>
            )}
          </div>
        ))}
      </div>
    );
  };

  const markdownComponents = {
    code({ node, inline, className, children, ...props }: any) {
      const match = /language-(\w+)/.exec(className || '');
      return !inline && match ? (
        <SyntaxHighlighter
          style={tomorrow}
          language={match[1]}
          PreTag="div"
          {...props}
        >
          {String(children).replace(/\n$/, '')}
        </SyntaxHighlighter>
      ) : (
        <code className={className} {...props}>
          {children}
        </code>
      );
    },
  };

  return (
    <div className="chat-container">
      <div className="chat-header">
        <h1>Practical Strategy AI Agent</h1>
        <div className={`health-status ${getHealthStatusClass()}`}>
          <span className="status-dot"></span>
          <span>
            {health ? (
              health.status === 'healthy' ? 'Connected' : 'Partial Connection'
            ) : (
              'Checking...'
            )}
          </span>
          {error && (
            <button className="retry-btn" onClick={checkHealth}>
              Retry
            </button>
          )}
        </div>
      </div>

      {error && (
        <div className="error-banner">
          {error}
        </div>
      )}

      <div className="messages-container">
        {messages.length === 0 ? (
          <div className="welcome-message">
            <h2>Welcome to Practical Strategy AI</h2>
            <p>Ask me anything about business strategy, strategic planning, or the Practical Strategy methodology.</p>
            <div className="example-questions">
              <p>Try asking:</p>
              <ul>
                <li>"What are the key principles of strategic thinking?"</li>
                <li>"How do I develop a strategic plan for my organization?"</li>
                <li>"What is the difference between strategy and tactics?"</li>
              </ul>
            </div>
          </div>
        ) : (
          messages.map((message, index) => (
            <div key={index} className={`message ${message.role}`}>
              <div className="message-role">{message.role === 'user' ? 'You' : 'AI Agent'}</div>
              <div className="message-content">
                {message.role === 'assistant' ? (
                  <ReactMarkdown 
                    remarkPlugins={[remarkGfm]}
                    components={markdownComponents}
                  >
                    {message.content}
                  </ReactMarkdown>
                ) : (
                  message.content
                )}
              </div>
              {message.role === 'assistant' && renderToolUsage(message.tools)}
            </div>
          ))
        )}
        {isLoading && (
          <div className="message assistant">
            <div className="message-role">AI Agent</div>
            <div className="message-content loading">
              <span className="loading-dot"></span>
              <span className="loading-dot"></span>
              <span className="loading-dot"></span>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <div className="input-container">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyPress={(e) => e.key === 'Enter' && sendMessage()}
          placeholder="Ask about business strategy..."
          disabled={isLoading || !!error}
          className="chat-input"
        />
        <button
          onClick={sendMessage}
          disabled={isLoading || !input.trim() || !!error}
          className="send-button"
        >
          {isLoading ? 'Sending...' : 'Send'}
        </button>
      </div>

      {health && (
        <div className="debug-info">
          <details>
            <summary>Connection Details</summary>
            <pre>{JSON.stringify(health, null, 2)}</pre>
            <p>Session ID: {sessionId}</p>
            <p>API Endpoint: {import.meta.env.VITE_API_URL || 'http://170.64.129.131:8058'}</p>
          </details>
        </div>
      )}
    </div>
  );
}