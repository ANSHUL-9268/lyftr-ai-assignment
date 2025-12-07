# WhatsApp Webhook Service

A production-style FastAPI service for ingesting WhatsApp-like messages with HMAC-SHA256 signature validation, SQLite storage, and comprehensive observability features.

Setup Used : VSCode, Copilot, Claude, AI Studio, Excalidraw

## Features

- **Webhook Ingestion**: Receive and store WhatsApp messages with exactly-once semantics
- **HMAC-SHA256 Validation**: Secure webhook endpoint with signature verification
- **Pagination & Filtering**: Query messages with pagination, filtering by sender, timestamp, and text search
- **Analytics**: Lightweight statistics endpoint for message analytics
- **Health Checks**: Kubernetes-compatible liveness and readiness probes
- **Prometheus Metrics**: Built-in metrics endpoint for observability
- **Structured Logging**: JSON-formatted logs for production environments
- **12-Factor Config**: Environment-based configuration

## Quick Start

### Using Docker Compose (Recommended)

1. **Clone and configure**:
   ```bash
   cp .env.example .env
   # Edit .env and set WEBHOOK_SECRET to a secure value
   ```

2. **Start the service**:
   ```bash
   docker-compose up -d
   ```

3. **Check health**:
   ```bash
   curl http://localhost:8000/health/ready
   ```

### Local Development

1. **Create virtual environment**:
   ```bash
   python -m venv venv
   # Windows
   .\venv\Scripts\activate
   # Linux/Mac
   source venv/bin/activate
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment**:
   ```bash
   cp .env.example .env
   # Edit .env with your settings
   ```

4. **Run the server**:
   ```bash
   uvicorn app.main:app --reload
   ```

5. **Access the API docs**:
   - Swagger UI: http://localhost:8000/docs
   - ReDoc: http://localhost:8000/redoc

## API Endpoints

### POST /webhook

Ingest an inbound WhatsApp message.

**Headers**:
- `Content-Type: application/json`
- `X-Signature: <HMAC-SHA256 hex signature>`

**Request Body**:
```json
{
  "message_id": "m1",
  "from": "+919876543210",
  "to": "+14155550100",
  "ts": "2025-01-15T10:00:00Z",
  "text": "Hello"
}
```

**Signature Computation**:
```python
import hmac
import hashlib
import json

body = json.dumps(payload).encode('utf-8')
signature = hmac.new(
    secret.encode('utf-8'),
    body,
    hashlib.sha256
).hexdigest()
```

**Example with curl**:
```bash
SECRET="your-webhook-secret"
BODY='{"message_id":"m1","from":"+919876543210","to":"+14155550100","ts":"2025-01-15T10:00:00Z","text":"Hello"}'
SIGNATURE=$(echo -n "$BODY" | openssl dgst -sha256 -hmac "$SECRET" | sed 's/^.* //')

curl -X POST http://localhost:8000/webhook \
  -H "Content-Type: application/json" \
  -H "X-Signature: $SIGNATURE" \
  -d "$BODY"
```

### GET /messages

Query stored messages with pagination and filtering.

**Query Parameters**:
- `limit` (int, 1-100, default: 50): Number of messages per page
- `offset` (int, default: 0): Number of messages to skip
- `from` (string): Filter by sender phone number
- `since` (ISO-8601): Filter messages since timestamp
- `q` (string): Case-insensitive text search

**Example**:
```bash
curl "http://localhost:8000/messages?limit=10&from=%2B919876543210&since=2025-01-01T00:00:00Z"
```

### GET /stats

Get message statistics.

**Response**:
```json
{
  "total_messages": 1000,
  "senders_count": 50,
  "messages_per_sender": [
    {"from": "+919876543210", "count": 100}
  ],
  "first_message_ts": "2025-01-01T00:00:00Z",
  "last_message_ts": "2025-01-15T10:00:00Z"
}
```

### GET /health/live

Liveness probe - always returns 200.

### GET /health/ready

Readiness probe - returns 200 if database is connected and WEBHOOK_SECRET is configured.

### GET /metrics

Prometheus-style metrics endpoint.

## Configuration

All configuration is done via environment variables:

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `WEBHOOK_SECRET` | Yes | - | HMAC-SHA256 secret for signature validation |
| `DATABASE_URL` | No | `sqlite:///./data/messages.db` | SQLAlchemy database URL |
| `APP_NAME` | No | `WhatsApp Webhook Service` | Application name |
| `APP_VERSION` | No | `1.0.0` | Application version |
| `DEBUG` | No | `false` | Enable debug mode |
| `HOST` | No | `0.0.0.0` | Server host |
| `PORT` | No | `8000` | Server port |
| `LOG_LEVEL` | No | `INFO` | Logging level |
| `LOG_FORMAT` | No | `json` | Log format (`json` or `text`) |

## Running Tests

```bash
# Install test dependencies
pip install -r requirements.txt

# Run tests
pytest tests/ -v

# Run with coverage
pytest tests/ -v --cov=app --cov-report=html
```

## Project Structure

```
whatsapp-webhook-service/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI application factory
│   ├── api/
│   │   ├── __init__.py
│   │   ├── health.py        # Health check endpoints
│   │   ├── messages.py      # Messages query endpoint
│   │   ├── metrics.py       # Prometheus metrics
│   │   ├── stats.py         # Analytics endpoint
│   │   └── webhook.py       # Webhook ingestion
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py        # Configuration settings
│   │   ├── database.py      # Database connection
│   │   ├── logging.py       # Structured logging
│   │   └── security.py      # HMAC signature validation
│   ├── models/
│   │   ├── __init__.py
│   │   └── message.py       # SQLAlchemy models
│   └── schemas/
│       ├── __init__.py
│       └── message.py       # Pydantic schemas
├── tests/
│   ├── __init__.py
│   └── test_api.py          # API tests
├── .env.example             # Example environment config
├── docker-compose.yml       # Docker Compose config
├── Dockerfile               # Docker build file
├── README.md                # This file
└── requirements.txt         # Python dependencies
```

## Security Considerations

1. **WEBHOOK_SECRET**: Use a strong, randomly generated secret (at least 32 bytes)
   ```bash
   python -c "import secrets; print(secrets.token_hex(32))"
   ```

2. **Signature Validation**: All webhook requests must include a valid HMAC-SHA256 signature

3. **Input Validation**: All inputs are validated using Pydantic with strict rules

4. **Database**: SQLite with parameterized queries prevents SQL injection

## License

MIT
