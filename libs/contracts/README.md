# Aetherlink Contracts

API and event specifications for the Aetherlink platform.

## 📋 Overview

- **HTTP Errors**: RFC7807 problem+json format
- **Required Headers**: 
  - `x-tenant-id` - Tenant identifier for multi-tenancy
  - `x-request-id` - Request tracing identifier
- **JWT Claims**:
  - `sub` - Subject (user ID)
  - `email` - User email
  - `realm_access.roles` - User roles
  - `tenant_id` - Associated tenant

## 📦 Specifications

### OpenAPI (REST APIs)
- **Gateway v1**: `./openapi/gateway-v1.yaml`
  - Health checks
  - Identity verification
  - JWT-protected endpoints

### AsyncAPI (Event Streams)
- **Event Envelope v1**: `./asyncapi/envelope-v1.yaml`
  - CloudEvents-style envelope
  - Multi-tenant event routing
  - Actor tracking

## 🔐 Security

All APIs use JWT Bearer authentication:
```
Authorization: Bearer <jwt_token>
```

## 📊 Event Format

All events follow the envelope pattern:
```json
{
  "id": "uuid",
  "ts": "ISO8601 timestamp",
  "type": "event.type",
  "source": "service-name",
  "tenant_id": "tenant-slug",
  "actor": "user-id",
  "data": { ... }
}
```

## 🚀 Usage

Generate client SDKs:
```bash
# OpenAPI
openapi-generator generate -i openapi/gateway-v1.yaml -g python

# AsyncAPI
asyncapi generate fromTemplate asyncapi/envelope-v1.yaml @asyncapi/python-paho-template
```
