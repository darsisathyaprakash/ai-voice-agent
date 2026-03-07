/**
 * Latency monitoring utilities.
 */
import { config } from '../config';
import { logger } from './logger';

interface LatencyRecord {
  sessionId: string;
  stages: Record<string, number>;
  total: number;
  timestamp: Date;
}

export class LatencyMonitor {
  private static instance: LatencyMonitor;
  private records: LatencyRecord[] = [];
  private intervalId: ReturnType<typeof setInterval> | null = null;

  private constructor() {}

  static getInstance(): LatencyMonitor {
    if (!LatencyMonitor.instance) {
      LatencyMonitor.instance = new LatencyMonitor();
    }
    return LatencyMonitor.instance;
  }

  start(): void {
    // Periodically log aggregated metrics
    this.intervalId = setInterval(() => {
      this.logAggregatedMetrics();
    }, 60000); // Every minute
  }

  stop(): void {
    if (this.intervalId) {
      clearInterval(this.intervalId);
    }
  }

  record(sessionId: string, stages: Record<string, number>, total: number): void {
    this.records.push({
      sessionId,
      stages,
      total,
      timestamp: new Date(),
    });

    // Check for violations
    const targets = config.latencyTargets;
    const violations: string[] = [];

    if (stages.stt && stages.stt > targets.stt) {
      violations.push(`STT: ${stages.stt}ms > ${targets.stt}ms`);
    }
    if (stages.llm && stages.llm > targets.llm) {
      violations.push(`LLM: ${stages.llm}ms > ${targets.llm}ms`);
    }
    if (stages.tts && stages.tts > targets.tts) {
      violations.push(`TTS: ${stages.tts}ms > ${targets.tts}ms`);
    }
    if (total > targets.total) {
      violations.push(`Total: ${total}ms > ${targets.total}ms`);
    }

    if (violations.length > 0) {
      logger.warn('latency_violation', {
        sessionId,
        violations,
        stages,
        total,
      });
    }

    // Keep only last 1000 records
    if (this.records.length > 1000) {
      this.records = this.records.slice(-1000);
    }
  }

  getMetrics(): {
    avgTotal: number;
    avgStages: Record<string, number>;
    p95Total: number;
    violationRate: number;
  } {
    if (this.records.length === 0) {
      return {
        avgTotal: 0,
        avgStages: {},
        p95Total: 0,
        violationRate: 0,
      };
    }

    const totals = this.records.map((r) => r.total);
    const sortedTotals = [...totals].sort((a, b) => a - b);
    
    const avgTotal = totals.reduce((a, b) => a + b, 0) / totals.length;
    const p95Index = Math.floor(sortedTotals.length * 0.95);
    const p95Total = sortedTotals[p95Index] || 0;

    // Calculate average for each stage
    const stageSums: Record<string, number[]> = {};
    for (const record of this.records) {
      for (const [stage, value] of Object.entries(record.stages)) {
        if (!stageSums[stage]) stageSums[stage] = [];
        stageSums[stage].push(value);
      }
    }

    const avgStages: Record<string, number> = {};
    for (const [stage, values] of Object.entries(stageSums)) {
      avgStages[stage] = values.reduce((a, b) => a + b, 0) / values.length;
    }

    // Calculate violation rate
    const violations = totals.filter((t) => t > config.latencyTargets.total);
    const violationRate = (violations.length / totals.length) * 100;

    return {
      avgTotal: Math.round(avgTotal),
      avgStages: Object.fromEntries(
        Object.entries(avgStages).map(([k, v]) => [k, Math.round(v)])
      ),
      p95Total: Math.round(p95Total),
      violationRate: Math.round(violationRate * 100) / 100,
    };
  }

  private logAggregatedMetrics(): void {
    const metrics = this.getMetrics();
    if (this.records.length > 0) {
      logger.info('latency_metrics', {
        recordCount: this.records.length,
        ...metrics,
      });
    }
  }
}

export class LatencyTracker {
  private sessionId: string;
  private stages: Record<string, number> = {};
  private stageStarts: Record<string, number> = {};
  private pipelineStart: number | null = null;

  constructor(sessionId: string) {
    this.sessionId = sessionId;
  }

  startPipeline(): void {
    this.pipelineStart = Date.now();
    this.stages = {};
  }

  startStage(stage: string): void {
    this.stageStarts[stage] = Date.now();
  }

  endStage(stage: string): number {
    if (!this.stageStarts[stage]) return 0;
    const elapsed = Date.now() - this.stageStarts[stage];
    this.stages[stage] = elapsed;
    delete this.stageStarts[stage];
    return elapsed;
  }

  getTotal(): number {
    if (!this.pipelineStart) return 0;
    return Date.now() - this.pipelineStart;
  }

  finalize(): { stages: Record<string, number>; total: number } {
    const total = this.getTotal();
    LatencyMonitor.getInstance().record(this.sessionId, this.stages, total);
    return { stages: this.stages, total };
  }
}
