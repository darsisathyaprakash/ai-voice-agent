/**
 * WebSocket proxy for voice streaming.
 * Handles client connections and proxies to Python backend.
 */
import WebSocket, { Server as WebSocketServer } from 'ws';
import { v4 as uuidv4 } from 'uuid';
import { config } from '../config';
import { logger } from '../utils/logger';
import { LatencyTracker } from '../utils/latency';
import { RedisClient } from '../services/redis';

interface ClientConnection {
  ws: WebSocket;
  sessionId: string;
  backendWs: WebSocket | null;
  latencyTracker: LatencyTracker;
  language: string;
}

export class VoiceWebSocketProxy {
  private connections: Map<string, ClientConnection> = new Map();

  constructor(wss: WebSocketServer) {
    wss.on('connection', (ws, req) => {
      this.handleConnection(ws);
    });

    // Heartbeat to keep connections alive
    setInterval(() => {
      this.heartbeat();
    }, config.wsHeartbeatInterval);
  }

  private handleConnection(ws: WebSocket): void {
    const connectionId = uuidv4();
    
    logger.info('client_connected', { connectionId });

    const connection: ClientConnection = {
      ws,
      sessionId: '',
      backendWs: null,
      latencyTracker: new LatencyTracker(connectionId),
      language: 'en',
    };

    this.connections.set(connectionId, connection);

    ws.on('message', async (data) => {
      await this.handleMessage(connectionId, data);
    });

    ws.on('close', () => {
      this.handleDisconnect(connectionId);
    });

    ws.on('error', (error) => {
      logger.error('client_ws_error', { connectionId, error: error.message });
    });
  }

  private async handleMessage(
    connectionId: string,
    data: WebSocket.RawData
  ): Promise<void> {
    const connection = this.connections.get(connectionId);
    if (!connection) return;

    try {
      // Check if it's text (JSON) or binary (audio)
      if (typeof data === 'string' || Buffer.isBuffer(data)) {
        // Try to parse as JSON
        try {
          const message = JSON.parse(data.toString());
          await this.handleJsonMessage(connectionId, message);
        } catch {
          // Binary audio data - forward to backend
          await this.forwardAudioToBackend(connectionId, data);
        }
      }
    } catch (error) {
      logger.error('message_handling_error', {
        connectionId,
        error: String(error),
      });
    }
  }

  private async handleJsonMessage(
    connectionId: string,
    message: any
  ): Promise<void> {
    const connection = this.connections.get(connectionId);
    if (!connection) return;

    switch (message.type) {
      case 'init':
        // Initialize session
        await this.initializeSession(connectionId, message);
        break;

      case 'end_turn':
        // Signal end of user speech
        await this.forwardToBackend(connectionId, message);
        break;

      case 'barge_in':
        // Handle interruption
        await this.forwardToBackend(connectionId, message);
        break;

      case 'text_input':
        // Text input for testing
        await this.forwardToBackend(connectionId, message);
        break;

      case 'end_session':
        // End the session
        await this.forwardToBackend(connectionId, message);
        break;

      default:
        logger.debug('unknown_message_type', { type: message.type });
    }
  }

  private async initializeSession(
    connectionId: string,
    message: any
  ): Promise<void> {
    const connection = this.connections.get(connectionId);
    if (!connection) return;

    const { patient_phone, language = 'en' } = message;
    connection.language = language;

    // Connect to Python backend WebSocket
    try {
      const backendWs = new WebSocket(`${config.backendWsUrl}/ws/voice`);

      backendWs.on('open', () => {
        // Send initialization to backend
        backendWs.send(
          JSON.stringify({
            patient_phone,
            language,
          })
        );
        logger.info('backend_connected', { connectionId });
      });

      backendWs.on('message', (data) => {
        // Forward backend responses to client
        this.forwardToClient(connectionId, data);
      });

      backendWs.on('close', () => {
        logger.info('backend_disconnected', { connectionId });
      });

      backendWs.on('error', (error) => {
        logger.error('backend_ws_error', { connectionId, error: error.message });
      });

      connection.backendWs = backendWs;
    } catch (error) {
      logger.error('backend_connection_failed', {
        connectionId,
        error: String(error),
      });
      this.sendError(connectionId, 'Failed to connect to voice service');
    }
  }

  private async forwardToBackend(
    connectionId: string,
    message: any
  ): Promise<void> {
    const connection = this.connections.get(connectionId);
    if (!connection?.backendWs) return;

    if (connection.backendWs.readyState === WebSocket.OPEN) {
      connection.backendWs.send(JSON.stringify(message));
    }
  }

  private async forwardAudioToBackend(
    connectionId: string,
    data: WebSocket.RawData
  ): Promise<void> {
    const connection = this.connections.get(connectionId);
    if (!connection?.backendWs) return;

    if (connection.backendWs.readyState === WebSocket.OPEN) {
      connection.backendWs.send(data);
    }
  }

  private forwardToClient(
    connectionId: string,
    data: WebSocket.RawData
  ): void {
    const connection = this.connections.get(connectionId);
    if (!connection) return;

    if (connection.ws.readyState === WebSocket.OPEN) {
      connection.ws.send(data);

      // Log latency metrics if present
      try {
        const message = JSON.parse(data.toString());
        if (message.type === 'turn_complete' && message.latency) {
          connection.latencyTracker.startPipeline();
          for (const [stage, duration] of Object.entries(
            message.latency.stages || {}
          )) {
            connection.latencyTracker.startStage(stage);
            // Simulate the end after the recorded duration
          }
          logger.debug('latency_recorded', {
            connectionId,
            latency: message.latency,
          });
        }
      } catch {
        // Binary data, ignore
      }
    }
  }

  private sendError(connectionId: string, message: string): void {
    const connection = this.connections.get(connectionId);
    if (!connection) return;

    if (connection.ws.readyState === WebSocket.OPEN) {
      connection.ws.send(
        JSON.stringify({
          type: 'error',
          message,
        })
      );
    }
  }

  private handleDisconnect(connectionId: string): void {
    const connection = this.connections.get(connectionId);
    if (connection) {
      // Close backend connection
      if (connection.backendWs) {
        connection.backendWs.close();
      }
      this.connections.delete(connectionId);
    }
    logger.info('client_disconnected', { connectionId });
  }

  private heartbeat(): void {
    for (const [connectionId, connection] of this.connections) {
      if (connection.ws.readyState === WebSocket.OPEN) {
        connection.ws.ping();
      } else {
        this.handleDisconnect(connectionId);
      }
    }
  }
}
