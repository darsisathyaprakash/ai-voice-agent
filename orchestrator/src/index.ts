/**
 * Voice AI Orchestrator - Entry Point
 * API gateway and WebSocket proxy for the voice AI system.
 */
import express from 'express';
import cors from 'cors';
import helmet from 'helmet';
import { Server as WebSocketServer } from 'ws';
import { createServer } from 'http';
import { config } from './config';
import { logger } from './utils/logger';
import { apiRouter } from './routes/api';
import { VoiceWebSocketProxy } from './websocket/proxy';
import { RedisClient } from './services/redis';
import { LatencyMonitor } from './utils/latency';

const app = express();
const server = createServer(app);

// Middleware
app.use(helmet());
app.use(cors());
app.use(express.json());

// Request logging
app.use((req, res, next) => {
  const start = Date.now();
  res.on('finish', () => {
    const duration = Date.now() - start;
    logger.info('http_request', {
      method: req.method,
      path: req.path,
      status: res.statusCode,
      duration_ms: duration,
    });
  });
  next();
});

// Root route
app.get('/', (req, res) => {
  res.json({ 
    service: 'voice-ai-orchestrator',
    message: 'Orchestrator running',
    version: '1.0.0',
  });
});

// Health check
app.get('/health', (req, res) => {
  res.json({ status: 'healthy', service: 'voice-ai-orchestrator' });
});

// API routes
app.use('/api', apiRouter);

// Initialize WebSocket server
const wss = new WebSocketServer({ server, path: '/ws/voice' });
const voiceProxy = new VoiceWebSocketProxy(wss);

// Initialize services
async function initialize() {
  try {
    // Connect to Redis
    await RedisClient.getInstance().connect();
    logger.info('redis_connected');

    // Start latency monitoring
    LatencyMonitor.getInstance().start();

    // Start server
    server.listen(config.port, () => {
      logger.info('server_started', {
        port: config.port,
        environment: config.environment,
      });
    });
  } catch (error) {
    logger.error('initialization_failed', { error: String(error) });
    process.exit(1);
  }
}

// Graceful shutdown
process.on('SIGTERM', async () => {
  logger.info('shutdown_initiated');
  
  server.close();
  await RedisClient.getInstance().disconnect();
  
  logger.info('shutdown_complete');
  process.exit(0);
});

process.on('SIGINT', async () => {
  logger.info('interrupt_received');
  process.emit('SIGTERM');
});

// Start
initialize();
