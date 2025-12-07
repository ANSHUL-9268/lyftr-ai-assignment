"""
Unit and integration tests for the WhatsApp Webhook Service.
"""
import hmac
import hashlib
import json
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.config import Settings, get_settings
from app.core.database import Base, get_engine, get_db, get_session_factory
from app.core.security import compute_signature
from app.models.message import Message


# Test configuration
TEST_SECRET = "test-secret-key-12345"


def get_test_settings() -> Settings:
    """Override settings for testing."""
    return Settings(
        webhook_secret=TEST_SECRET,
        database_url="sqlite:///./test_messages.db",
        log_level="DEBUG",
        log_format="text",
    )


@pytest.fixture(scope="function")
def test_db():
    """Create a fresh test database for each test."""
    # Override settings
    settings = get_test_settings()
    
    # Create engine with test database
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    
    engine = create_engine(
        settings.database_url,
        connect_args={"check_same_thread": False}
    )
    
    # Create tables
    Base.metadata.create_all(bind=engine)
    
    TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    def override_get_db():
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()
    
    def override_get_settings():
        return settings
    
    # Override dependencies
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_settings] = override_get_settings
    
    yield engine
    
    # Cleanup
    Base.metadata.drop_all(bind=engine)
    app.dependency_overrides.clear()
    
    # Remove test database file
    import os
    if os.path.exists("./test_messages.db"):
        os.remove("./test_messages.db")


@pytest.fixture
def client(test_db):
    """Create a test client."""
    return TestClient(app)


def sign_payload(payload: dict, secret: str = TEST_SECRET) -> str:
    """Generate HMAC-SHA256 signature for a payload."""
    body = json.dumps(payload).encode("utf-8")
    return compute_signature(secret, body)


class TestHealthEndpoints:
    """Tests for health check endpoints."""
    
    def test_liveness_always_returns_ok(self, client):
        """GET /health/live should always return 200."""
        response = client.get("/health/live")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
    
    def test_readiness_returns_ok_when_configured(self, client):
        """GET /health/ready should return 200 when properly configured."""
        response = client.get("/health/ready")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["checks"]["database"] == "ok"
        assert data["checks"]["webhook_secret"] == "ok"


class TestWebhookEndpoint:
    """Tests for POST /webhook."""
    
    def test_webhook_requires_signature(self, client):
        """POST /webhook without signature returns 401."""
        payload = {
            "message_id": "m1",
            "from": "+919876543210",
            "to": "+14155550100",
            "ts": "2025-01-15T10:00:00Z",
            "text": "Hello"
        }
        response = client.post("/webhook", json=payload)
        assert response.status_code == 401
        assert response.json()["detail"] == "invalid signature"
    
    def test_webhook_rejects_invalid_signature(self, client):
        """POST /webhook with wrong signature returns 401."""
        payload = {
            "message_id": "m1",
            "from": "+919876543210",
            "to": "+14155550100",
            "ts": "2025-01-15T10:00:00Z",
            "text": "Hello"
        }
        response = client.post(
            "/webhook",
            json=payload,
            headers={"X-Signature": "invalid-signature"}
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "invalid signature"
    
    def test_webhook_accepts_valid_signature(self, client):
        """POST /webhook with valid signature returns 200."""
        payload = {
            "message_id": "m1",
            "from": "+919876543210",
            "to": "+14155550100",
            "ts": "2025-01-15T10:00:00Z",
            "text": "Hello"
        }
        signature = sign_payload(payload)
        
        response = client.post(
            "/webhook",
            content=json.dumps(payload),
            headers={
                "Content-Type": "application/json",
                "X-Signature": signature
            }
        )
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
    
    def test_webhook_idempotency(self, client):
        """Duplicate messages should return ok without error."""
        payload = {
            "message_id": "duplicate-test",
            "from": "+919876543210",
            "to": "+14155550100",
            "ts": "2025-01-15T10:00:00Z",
            "text": "Hello"
        }
        signature = sign_payload(payload)
        headers = {
            "Content-Type": "application/json",
            "X-Signature": signature
        }
        body = json.dumps(payload)
        
        # First request
        response1 = client.post("/webhook", content=body, headers=headers)
        assert response1.status_code == 200
        
        # Second request (duplicate)
        response2 = client.post("/webhook", content=body, headers=headers)
        assert response2.status_code == 200
        assert response2.json()["status"] == "ok"
    
    def test_webhook_validates_e164_format(self, client):
        """POST /webhook validates E.164 phone numbers."""
        payload = {
            "message_id": "m2",
            "from": "invalid-phone",
            "to": "+14155550100",
            "ts": "2025-01-15T10:00:00Z"
        }
        signature = sign_payload(payload)
        
        response = client.post(
            "/webhook",
            content=json.dumps(payload),
            headers={
                "Content-Type": "application/json",
                "X-Signature": signature
            }
        )
        assert response.status_code == 422
    
    def test_webhook_requires_utc_timestamp(self, client):
        """POST /webhook requires timestamp ending with Z."""
        payload = {
            "message_id": "m3",
            "from": "+919876543210",
            "to": "+14155550100",
            "ts": "2025-01-15T10:00:00+05:30"  # Not UTC
        }
        signature = sign_payload(payload)
        
        response = client.post(
            "/webhook",
            content=json.dumps(payload),
            headers={
                "Content-Type": "application/json",
                "X-Signature": signature
            }
        )
        assert response.status_code == 422
    
    def test_webhook_text_max_length(self, client):
        """POST /webhook validates text max length."""
        payload = {
            "message_id": "m4",
            "from": "+919876543210",
            "to": "+14155550100",
            "ts": "2025-01-15T10:00:00Z",
            "text": "x" * 5000  # Exceeds 4096
        }
        signature = sign_payload(payload)
        
        response = client.post(
            "/webhook",
            content=json.dumps(payload),
            headers={
                "Content-Type": "application/json",
                "X-Signature": signature
            }
        )
        assert response.status_code == 422


class TestMessagesEndpoint:
    """Tests for GET /messages."""
    
    def _create_messages(self, client, count: int = 5):
        """Helper to create test messages."""
        for i in range(count):
            payload = {
                "message_id": f"msg-{i}",
                "from": f"+9198765432{i % 3}0",
                "to": "+14155550100",
                "ts": f"2025-01-15T10:0{i}:00Z",
                "text": f"Message {i}"
            }
            signature = sign_payload(payload)
            client.post(
                "/webhook",
                content=json.dumps(payload),
                headers={
                    "Content-Type": "application/json",
                    "X-Signature": signature
                }
            )
    
    def test_messages_empty_list(self, client):
        """GET /messages returns empty list when no messages."""
        response = client.get("/messages")
        assert response.status_code == 200
        data = response.json()
        assert data["data"] == []
        assert data["total"] == 0
        assert data["limit"] == 50
        assert data["offset"] == 0
    
    def test_messages_pagination(self, client):
        """GET /messages supports pagination."""
        self._create_messages(client, 10)
        
        # First page
        response = client.get("/messages?limit=3&offset=0")
        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) == 3
        assert data["total"] == 10
        assert data["limit"] == 3
        assert data["offset"] == 0
        
        # Second page
        response = client.get("/messages?limit=3&offset=3")
        data = response.json()
        assert len(data["data"]) == 3
        assert data["offset"] == 3
    
    def test_messages_filter_by_sender(self, client):
        """GET /messages filters by sender."""
        self._create_messages(client, 9)
        
        response = client.get("/messages?from=%2B919876543210")  # URL encoded +
        assert response.status_code == 200
        data = response.json()
        # Messages 0, 3, 6 have this sender
        assert data["total"] == 3
        for msg in data["data"]:
            assert msg["from"] == "+919876543210"
    
    def test_messages_filter_by_since(self, client):
        """GET /messages filters by since timestamp."""
        self._create_messages(client, 5)
        
        response = client.get("/messages?since=2025-01-15T10:03:00Z")
        assert response.status_code == 200
        data = response.json()
        # Messages 3 and 4
        assert data["total"] == 2
    
    def test_messages_text_search(self, client):
        """GET /messages supports case-insensitive text search."""
        self._create_messages(client, 5)
        
        response = client.get("/messages?q=message%202")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert "Message 2" in data["data"][0]["text"]
    
    def test_messages_ordering(self, client):
        """GET /messages orders by ts ASC, message_id ASC."""
        self._create_messages(client, 5)
        
        response = client.get("/messages")
        data = response.json()
        
        # Verify ordering
        timestamps = [msg["ts"] for msg in data["data"]]
        assert timestamps == sorted(timestamps)


class TestStatsEndpoint:
    """Tests for GET /stats."""
    
    def _create_messages(self, client, count: int = 5):
        """Helper to create test messages."""
        for i in range(count):
            payload = {
                "message_id": f"stats-msg-{i}",
                "from": f"+9198765432{i % 3}0",
                "to": "+14155550100",
                "ts": f"2025-01-15T10:0{i}:00Z",
                "text": f"Stats message {i}"
            }
            signature = sign_payload(payload)
            client.post(
                "/webhook",
                content=json.dumps(payload),
                headers={
                    "Content-Type": "application/json",
                    "X-Signature": signature
                }
            )
    
    def test_stats_empty(self, client):
        """GET /stats returns zeros when no messages."""
        response = client.get("/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["total_messages"] == 0
        assert data["senders_count"] == 0
        assert data["messages_per_sender"] == []
        assert data["first_message_ts"] is None
        assert data["last_message_ts"] is None
    
    def test_stats_with_messages(self, client):
        """GET /stats returns correct statistics."""
        self._create_messages(client, 9)
        
        response = client.get("/stats")
        assert response.status_code == 200
        data = response.json()
        
        assert data["total_messages"] == 9
        assert data["senders_count"] == 3
        assert len(data["messages_per_sender"]) == 3
        assert data["first_message_ts"] is not None
        assert data["last_message_ts"] is not None
        
        # Verify messages_per_sender is sorted by count desc
        counts = [s["count"] for s in data["messages_per_sender"]]
        assert counts == sorted(counts, reverse=True)


class TestMetricsEndpoint:
    """Tests for GET /metrics."""
    
    def test_metrics_returns_prometheus_format(self, client):
        """GET /metrics returns Prometheus format."""
        response = client.get("/metrics")
        assert response.status_code == 200
        assert "text/plain" in response.headers["content-type"]
        
        content = response.text
        assert "http_requests_total" in content or "app_info" in content


class TestSignatureComputation:
    """Tests for HMAC-SHA256 signature computation."""
    
    def test_compute_signature(self):
        """Test signature computation."""
        secret = "test-secret"
        body = b'{"message_id": "m1"}'
        
        signature = compute_signature(secret, body)
        
        # Verify it's a valid hex string
        assert len(signature) == 64
        assert all(c in "0123456789abcdef" for c in signature)
    
    def test_signature_is_deterministic(self):
        """Same input produces same signature."""
        secret = "test-secret"
        body = b'{"message_id": "m1"}'
        
        sig1 = compute_signature(secret, body)
        sig2 = compute_signature(secret, body)
        
        assert sig1 == sig2
    
    def test_different_secrets_produce_different_signatures(self):
        """Different secrets produce different signatures."""
        body = b'{"message_id": "m1"}'
        
        sig1 = compute_signature("secret1", body)
        sig2 = compute_signature("secret2", body)
        
        assert sig1 != sig2
