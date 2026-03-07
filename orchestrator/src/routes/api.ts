/**
 * API routes for the orchestrator.
 */
import { Router, Request, Response, NextFunction } from 'express';
import { backendClient } from '../services/backend';
import { RedisClient } from '../services/redis';
import { LatencyMonitor } from '../utils/latency';
import { logger } from '../utils/logger';

export const apiRouter = Router();

// Proxy to backend health
apiRouter.get('/health/backend', async (req: Request, res: Response) => {
  const isHealthy = await backendClient.healthCheck();
  res.json({
    backend: isHealthy ? 'healthy' : 'unhealthy',
  });
});

// Metrics endpoint
apiRouter.get('/metrics', (req: Request, res: Response) => {
  const metrics = LatencyMonitor.getInstance().getMetrics();
  res.json(metrics);
});

// Session info
apiRouter.get('/sessions/:sessionId', async (req: Request, res: Response) => {
  try {
    const session = await RedisClient.getInstance().getSession(
      req.params.sessionId
    );
    if (!session) {
      return res.status(404).json({ error: 'Session not found' });
    }
    res.json(session);
  } catch (error) {
    logger.error('session_fetch_error', { error: String(error) });
    res.status(500).json({ error: 'Internal server error' });
  }
});

// Doctor search
apiRouter.get('/doctors/search', async (req: Request, res: Response) => {
  try {
    const { specialty, language } = req.query;
    const doctors = await backendClient.searchDoctors(
      specialty as string,
      language as string
    );
    res.json(doctors);
  } catch (error) {
    logger.error('doctor_search_error', { error: String(error) });
    res.status(500).json({ error: 'Failed to search doctors' });
  }
});

// Doctor availability
apiRouter.get(
  '/doctors/:doctorId/availability/:date',
  async (req: Request, res: Response) => {
    try {
      const { doctorId, date } = req.params;
      const availability = await backendClient.getDoctorAvailability(
        doctorId,
        date
      );
      res.json(availability);
    } catch (error) {
      logger.error('availability_fetch_error', { error: String(error) });
      res.status(500).json({ error: 'Failed to fetch availability' });
    }
  }
);

// Campaign stats
apiRouter.get('/campaigns/:campaignId/stats', async (req: Request, res: Response) => {
  try {
    const stats = await backendClient.getCampaignStats(req.params.campaignId);
    res.json(stats);
  } catch (error) {
    logger.error('campaign_stats_error', { error: String(error) });
    res.status(500).json({ error: 'Failed to fetch campaign stats' });
  }
});

// Error handler
apiRouter.use((error: Error, req: Request, res: Response, next: NextFunction) => {
  logger.error('api_error', {
    path: req.path,
    error: error.message,
  });
  res.status(500).json({ error: 'Internal server error' });
});
