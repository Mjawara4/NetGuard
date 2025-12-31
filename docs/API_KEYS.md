# NetGuard API Key Integration Guide

This document describes how to use API Keys to integrate NetGuard with external services like **Hotfly.net**.

## 1. Authentication

All requests to the NetGuard API using an API Key must include the key in the `X-API-Key` HTTP header.

**Format:** `X-API-Key: ng_sk_your_key_here`

---

## 2. Base API URL

The production API base URL is:
**`https://app.netguard.fun/api/v1`**

*Note: All endpoints listed below are relative to this base URL.*

---

## 3. Scope & Permissions

- **Organization Scoping**: API Keys are linked to the organization of the user who created them. A key can only see and manage devices and users within that specific organization.
- **Enabled Functions**: API Keys have full programmatic access to:
    - **Inventory**: Devices and Sites (Create, Read, Update, Delete).
    - **Hotspot**: User management, Batch generation, and Profiles.
    - **Monitoring**: Real-time metrics and historical data.

---

## 4. Key Endpoints

### 📦 Inventory Management
- **List Devices**: `GET /inventory/devices`
- **Get Specific Device**: `GET /inventory/devices/{device_id}`
- **List Sites**: `GET /inventory/sites`
- **Provision VPN**: `POST /inventory/devices/{device_id}/provision-wireguard` (Returns Mikrotik script)

### 🎫 Hotspot Integration (Hotfly)
- **Batch Generate Vouchers**: `POST /hotspot/{device_id}/users/batch`
- **List Active Users**: `GET /hotspot/{device_id}/active`
- **Get Profiles**: `GET /hotspot/{device_id}/profiles`

**Example JSON for Batch Vouchers:**
```json
{
  "qty": 5,
  "prefix": "auto",
  "random_mode": true,
  "format": "numeric",
  "data_limit": "500M",
  "time_limit": "24h"
}
```

### 📈 Monitoring & Health
- **Latest Metrics**: `GET /monitoring/metrics/latest?device_id={device_id}`
- **Historical Data**: `GET /monitoring/metrics/history?device_id={device_id}&start_time=2025-12-25T00:00:00Z`
- **Active Alerts**: `GET /monitoring/alerts`

### 🤖 Agent Control
- **Trigger Agent**: `POST /agents/trigger`
  - Body: `{ "agent_name": "monitor" | "diagnoser" | "fix" }`
  - Desc: Manually triggers an agent run via Redis.

---

## 5. Examples

### Fetching Device IDs (cURL)
```bash
curl -X GET "https://app.netguard.fun/api/v1/inventory/devices" \
     -H "X-API-Key: ng_sk_..."
```

### What does a Device ID look like?
Device IDs are standard **UUIDs**.
Example: `b917349a-eb31-41ea-8f79-5e80d0195201`

---

## 6. Security Best Practices

1. **Protect your keys**: These keys grant full management access to your routers.
2. **Revocation**: If a key is leaked, delete it from the **Settings** page immediately.
3. **Environment Variables**: Store keys as SECRETS in your integration environment, never hardcoded.
