"""
Tests for health check API endpoints.
"""
import pytest
from unittest.mock import patch, AsyncMock


class TestHealthEndpoints:
    """Test suite for health check endpoints."""

    @pytest.mark.asyncio
    async def test_health_check(self, client):
        """Test basic health check returns 200."""
        response = await client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "service" in data

    @pytest.mark.asyncio
    async def test_liveness_check(self, client):
        """Test liveness probe returns 200."""
        response = await client.get("/api/health/live")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "alive"

    @pytest.mark.asyncio
    async def test_readiness_check_returns_status(self, client):
        """Test readiness check returns checks structure."""
        response = await client.get("/api/health/ready")
        # May return 200 or 503 depending on service status
        assert response.status_code in [200, 503]
        data = response.json()
        assert "status" in data
        assert "checks" in data
        assert "database" in data["checks"]
        assert "redis" in data["checks"]

    @pytest.mark.asyncio
    async def test_metrics_endpoint(self, client):
        """Test metrics endpoint returns latency targets."""
        response = await client.get("/api/metrics")
        assert response.status_code == 200
        data = response.json()
        assert "latency_targets" in data
        targets = data["latency_targets"]
        assert "stt_ms" in targets
        assert "llm_ms" in targets
        assert "tts_ms" in targets
        assert "total_ms" in targets
