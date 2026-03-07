/**
 * Redis client wrapper.
 */
import Redis from 'ioredis';
import { config } from '../config';
import { logger } from '../utils/logger';

export class RedisClient {
  private static instance: RedisClient;
  private client: Redis | null = null;

  private constructor() {}

  static getInstance(): RedisClient {
    if (!RedisClient.instance) {
      RedisClient.instance = new RedisClient();
    }
    return RedisClient.instance;
  }

  async connect(): Promise<void> {
    this.client = new Redis(config.redisUrl, {
      lazyConnect: true,
      maxRetriesPerRequest: 3,
    });

    this.client.on('error', (err) => {
      logger.error('redis_error', { error: err.message });
    });

    this.client.on('connect', () => {
      logger.debug('redis_connected');
    });

    await this.client.connect();
  }

  async disconnect(): Promise<void> {
    if (this.client) {
      await this.client.quit();
      this.client = null;
    }
  }

  getClient(): Redis {
    if (!this.client) {
      throw new Error('Redis not connected');
    }
    return this.client;
  }

  // Session operations
  async getSession(sessionId: string): Promise<Record<string, string> | null> {
    const client = this.getClient();
    const data = await client.hgetall(`session:${sessionId}`);
    return Object.keys(data).length > 0 ? data : null;
  }

  async setSessionField(
    sessionId: string,
    field: string,
    value: string
  ): Promise<void> {
    const client = this.getClient();
    await client.hset(`session:${sessionId}`, field, value);
    await client.expire(`session:${sessionId}`, config.redisSessionTtl);
  }

  async getConversationHistory(
    sessionId: string,
    lastN: number = 10
  ): Promise<string[]> {
    const client = this.getClient();
    return await client.lrange(`session:${sessionId}:history`, -lastN, -1);
  }

  // Caching
  async cacheGet(key: string): Promise<string | null> {
    const client = this.getClient();
    return await client.get(`cache:${key}`);
  }

  async cacheSet(
    key: string,
    value: string,
    ttlSeconds: number = 300
  ): Promise<void> {
    const client = this.getClient();
    await client.setex(`cache:${key}`, ttlSeconds, value);
  }
}
