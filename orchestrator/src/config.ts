/**
 * Configuration for the orchestrator service.
 */
import dotenv from 'dotenv';

dotenv.config();

export const config = {
  // Server
  port: parseInt(process.env.PORT || '3000', 10),
  environment: process.env.NODE_ENV || 'development',

  // Backend service
  backendUrl: process.env.BACKEND_URL || 'http://localhost:8000',
  backendWsUrl: process.env.BACKEND_WS_URL || 'ws://localhost:8000',

  // Redis
  redisUrl: process.env.REDIS_URL || 'redis://localhost:6379/0',
  redisSessionTtl: parseInt(process.env.REDIS_SESSION_TTL || '1800', 10),

  // WebSocket
  wsHeartbeatInterval: parseInt(process.env.WS_HEARTBEAT_INTERVAL || '30000', 10),
  wsMaxPayload: parseInt(process.env.WS_MAX_PAYLOAD || '1048576', 10),

  // Latency targets
  latencyTargets: {
    stt: parseInt(process.env.TARGET_STT_LATENCY_MS || '150', 10),
    llm: parseInt(process.env.TARGET_LLM_LATENCY_MS || '200', 10),
    tts: parseInt(process.env.TARGET_TTS_LATENCY_MS || '100', 10),
    total: parseInt(process.env.TARGET_TOTAL_LATENCY_MS || '450', 10),
  },

  // Supported languages
  supportedLanguages: ['en', 'hi', 'ta'],
};
