# Deployment Guide

## Prerequisites

- Docker 24.0+
- Docker Compose 2.20+
- OpenAI API key
- Minimum 8GB RAM, 4 CPU cores

## Local Development

### 1. Clone Repository

```bash
git clone <repository-url>
cd voice-ai-agent
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your configuration
```

Required variables:
```
OPENAI_API_KEY=sk-your-api-key
```

### 3. Start Infrastructure

```bash
cd docker
docker-compose up -d postgres redis
```

### 4. Initialize Database

The schema is automatically applied on first PostgreSQL start from the mounted SQL file.

### 5. Run Backend

```bash
# Option A: Docker
docker-compose up -d backend

# Option B: Local Python
cd backend
pip install -r requirements.txt
uvicorn main:app --reload
```

### 6. Run Orchestrator

```bash
# Option A: Docker
docker-compose up -d orchestrator

# Option B: Local Node.js
cd orchestrator
npm install
npm run dev
```

## Production Deployment

### With Docker Compose

```bash
cd docker

# Build images
docker-compose build

# Start all services
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f backend
```

### Kubernetes (Helm)

Create `values.yaml`:

```yaml
replicaCount:
  backend: 3
  orchestrator: 2
  worker: 2

image:
  backend:
    repository: your-registry/voice-ai-backend
    tag: latest
  orchestrator:
    repository: your-registry/voice-ai-orchestrator
    tag: latest

env:
  OPENAI_API_KEY:
    secretKeyRef:
      name: voice-ai-secrets
      key: openai-api-key
  DATABASE_URL:
    secretKeyRef:
      name: voice-ai-secrets
      key: database-url
  REDIS_URL:
    secretKeyRef:
      name: voice-ai-secrets
      key: redis-url

resources:
  backend:
    requests:
      memory: "2Gi"
      cpu: "1000m"
    limits:
      memory: "4Gi"
      cpu: "2000m"
```

### AWS Deployment

#### ECS with Fargate

```bash
# Create ECR repositories
aws ecr create-repository --repository-name voice-ai-backend
aws ecr create-repository --repository-name voice-ai-orchestrator

# Build and push
docker build -t voice-ai-backend -f docker/Dockerfile.backend .
docker tag voice-ai-backend:latest <account>.dkr.ecr.<region>.amazonaws.com/voice-ai-backend:latest
docker push <account>.dkr.ecr.<region>.amazonaws.com/voice-ai-backend:latest
```

Task definition example:
```json
{
  "family": "voice-ai-backend",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "2048",
  "memory": "4096",
  "containerDefinitions": [
    {
      "name": "backend",
      "image": "<account>.dkr.ecr.<region>.amazonaws.com/voice-ai-backend:latest",
      "portMappings": [
        {
          "containerPort": 8000,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {"name": "APP_ENV", "value": "production"}
      ],
      "secrets": [
        {
          "name": "OPENAI_API_KEY",
          "valueFrom": "arn:aws:secretsmanager:..."
        }
      ]
    }
  ]
}
```

### Infrastructure Components

#### PostgreSQL (RDS)

```bash
aws rds create-db-instance \
  --db-instance-identifier voice-ai-db \
  --db-instance-class db.r6g.large \
  --engine postgres \
  --engine-version 16 \
  --master-username voiceai \
  --master-user-password <password> \
  --allocated-storage 100 \
  --storage-type gp3 \
  --multi-az
```

#### Redis (ElastiCache)

```bash
aws elasticache create-cache-cluster \
  --cache-cluster-id voice-ai-redis \
  --engine redis \
  --cache-node-type cache.r6g.large \
  --num-cache-nodes 1
```

## SSL/TLS Configuration

### Nginx Reverse Proxy

```nginx
upstream backend {
    server backend:8000;
}

upstream orchestrator {
    server orchestrator:3000;
}

server {
    listen 443 ssl http2;
    server_name api.voiceai.example.com;

    ssl_certificate /etc/ssl/certs/voiceai.crt;
    ssl_certificate_key /etc/ssl/private/voiceai.key;

    # REST API
    location /api/ {
        proxy_pass http://orchestrator;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # WebSocket
    location /ws/ {
        proxy_pass http://orchestrator;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 86400;
    }
}
```

## Monitoring Setup

### Prometheus Metrics

Add to `docker-compose.yml`:

```yaml
prometheus:
  image: prom/prometheus:latest
  volumes:
    - ./prometheus.yml:/etc/prometheus/prometheus.yml
  ports:
    - "9090:9090"

grafana:
  image: grafana/grafana:latest
  ports:
    - "3001:3000"
  depends_on:
    - prometheus
```

### prometheus.yml

```yaml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'voice-ai-backend'
    static_configs:
      - targets: ['backend:8000']
    metrics_path: '/api/metrics'

  - job_name: 'voice-ai-orchestrator'
    static_configs:
      - targets: ['orchestrator:3000']
    metrics_path: '/api/metrics'
```

## Health Checks

### Backend Health

```bash
curl http://localhost:8000/api/health
curl http://localhost:8000/api/health/ready
```

### Orchestrator Health

```bash
curl http://localhost:3000/health
curl http://localhost:3000/api/health/backend
```

## Troubleshooting

### Common Issues

1. **WebSocket Connection Failed**
   - Check CORS settings
   - Verify firewall rules for WebSocket ports
   - Ensure sticky sessions for load balancer

2. **Database Connection Error**
   - Verify DATABASE_URL format
   - Check network connectivity
   - Ensure PostgreSQL is accepting connections

3. **High Latency**
   - Monitor `/api/metrics` endpoint
   - Check STT model size (use smaller for lower latency)
   - Scale backend instances

4. **Redis Connection Error**
   - Verify REDIS_URL
   - Check Redis maxclients setting
   - Ensure sufficient memory

### Logs

```bash
# Backend logs
docker-compose logs -f backend

# All services
docker-compose logs -f

# Filter by time
docker-compose logs --since 1h backend
```

## Backup & Recovery

### Database Backup

```bash
# Create backup
pg_dump -h localhost -U voiceai voiceai_db > backup.sql

# Restore
psql -h localhost -U voiceai voiceai_db < backup.sql
```

### Redis Backup

```bash
# Trigger RDB snapshot
redis-cli BGSAVE

# Copy dump.rdb from container
docker cp voice-ai-redis:/data/dump.rdb ./backup/
```
