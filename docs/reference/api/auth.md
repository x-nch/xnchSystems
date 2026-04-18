# API Authentication

API authentication and authorization.

## Authentication Methods

### API Key

**Header**: `X-API-Key: your-api-key`

```bash
curl -H "X-API-Key: sk_xnch_abc123" \
  http://localhost:8000/api/v1/health
```

### Bearer Token

**Header**: `Authorization: Bearer your-token`

```bash
curl -H "Authorization: Bearer eyJhbGciOiJIUzI1NiI..." \
  http://localhost:8000/api/v1/health
```

## Configuration

```yaml
api:
  auth:
    enabled: true
    
    # API Keys
    keys:
      - key: "sk_xnch_abc123"
        name: "admin"
        permissions: ["*"]
      - key: "sk_xnch_def456"
        name: "readonly"
        permissions: ["read"]
        
    # JWT Configuration
    jwt:
      secret: "${JWT_SECRET}"
      algorithm: HS256
      expiry: 3600  # seconds
```

## Permissions

| Permission | Endpoints |
|------------|-----------|
| `read` | GET /health, GET /metrics, GET /memory/*, GET /audit/* |
| `execute` | POST /execute |
| `write` | POST /*, PUT /*, DELETE /* |
| `admin` | All + config management |

## Rate Limiting

```yaml
api:
  rate_limit:
    enabled: true
    requests_per_minute: 60
    
    # Per-endpoint limits
    endpoints:
      /execute: 10
      /intent/parse: 100
```

## Security Headers

```yaml
api:
  cors:
    allowed_origins:
      - "https://yourdomain.com"
    allowed_methods:
      - GET
      - POST
    allowed_headers:
      - Content-Type
      - Authorization
```

## Production Security

1. **Use HTTPS** in production
2. **Rotate keys** regularly
3. **Enable rate limiting**
4. **Configure CORS** properly