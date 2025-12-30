# Functionality Fixes - NetGuard AI

## 🔧 Issues Fixed

### 1. **Encryption/Decryption for Async SQLAlchemy**
**Problem**: SQLAlchemy's `load` event doesn't work with async sessions, so encrypted device secrets (`ssh_password`, `wg_private_key`) were not being decrypted when loaded from the database.

**Solution**: 
- Created `decrypt_device_secrets()` helper function in `backend/app/models/core.py`
- Updated all endpoints that access device credentials to manually call this function after loading devices

**Files Modified**:
- `backend/app/models/core.py` - Added `decrypt_device_secrets()` function
- `backend/app/routers/hotspot.py` - All 8 endpoints now decrypt device secrets
- `backend/app/routers/devices.py` - WireGuard provisioning endpoint now decrypts device secrets

---

## ✅ Fixed Endpoints

### Hotspot Management (All Fixed)
1. ✅ `GET /api/v1/hotspot/{device_id}/users` - Get hotspot users
2. ✅ `POST /api/v1/hotspot/{device_id}/users` - Create hotspot user
3. ✅ `GET /api/v1/hotspot/{device_id}/profiles` - Get hotspot profiles
4. ✅ `POST /api/v1/hotspot/{device_id}/profiles` - Create hotspot profile
5. ✅ `DELETE /api/v1/hotspot/{device_id}/profiles/{profile_name}` - Delete profile
6. ✅ `GET /api/v1/hotspot/{device_id}/active` - Get active users
7. ✅ `DELETE /api/v1/hotspot/{device_id}/active/{active_id}` - Kick active user
8. ✅ `POST /api/v1/hotspot/{device_id}/users/batch` - Batch generate users

### WireGuard Provisioning (Fixed)
1. ✅ `POST /api/v1/devices/{device_id}/provision-wireguard` - Generate WireGuard script

---

## 🧪 Testing Checklist

### Hotspot Endpoints
- [ ] **Get Hotspot Users**: Should connect to router and retrieve users
- [ ] **Create Hotspot User**: Should create new user on router
- [ ] **Get Profiles**: Should retrieve hotspot profiles from router
- [ ] **Create Profile**: Should create new profile on router
- [ ] **Delete Profile**: Should remove profile from router
- [ ] **Get Active Users**: Should show currently connected users
- [ ] **Kick User**: Should disconnect an active user
- [ ] **Batch Generate**: Should create multiple users at once

### WireGuard Provisioning
- [ ] **Provision Script**: Should generate complete MikroTik script with all values populated
- [ ] **Script is Pasteable**: Script should be ready to paste directly into MikroTik terminal
- [ ] **No Placeholders**: All variables should be replaced with actual values

### Other Endpoints (Verify Still Working)
- [ ] **Device Management**: Create, read, update, delete devices
- [ ] **Site Management**: Create, read, update, delete sites
- [ ] **Authentication**: Login, signup, password change
- [ ] **Monitoring**: Get metrics, alerts, incidents
- [ ] **API Keys**: Create, list, revoke API keys

---

## 🔍 How to Test

### 1. Test Hotspot Manager
```bash
# Get a device ID first, then:
curl -X GET "https://app.netguard.fun/api/v1/hotspot/{device_id}/users" \
  -H "Authorization: Bearer YOUR_TOKEN"

# Should return list of hotspot users (not 500 error)
```

### 2. Test WireGuard Provisioning
```bash
curl -X POST "https://app.netguard.fun/api/v1/devices/{device_id}/provision-wireguard" \
  -H "Authorization: Bearer YOUR_TOKEN"

# Should return complete script with all values populated
# Check that mikrotik_script field has no placeholders
```

### 3. Check Backend Logs
```bash
ssh root@74.208.167.166 'cd /opt/netguard && docker compose logs backend --tail=50'
# Should see no encryption/decryption errors
```

---

## 📝 Technical Details

### Before Fix
```python
# Device loaded from DB
device = result.scalars().first()
# device.ssh_password was still encrypted (load event didn't fire)
connection = get_api_pool(device.ip_address, device.ssh_username, device.ssh_password, port)
# Connection failed because password was encrypted string
```

### After Fix
```python
# Device loaded from DB
device = result.scalars().first()
# Manually decrypt secrets
decrypt_device_secrets(device)
# device.ssh_password is now decrypted
connection = get_api_pool(device.ip_address, device.ssh_username, device.ssh_password, port)
# Connection succeeds with decrypted password
```

---

## ✅ Deployment Status

- **Deployed**: December 30, 2025
- **Status**: ✅ All fixes deployed and backend is healthy
- **Health Check**: `{"status":"healthy","database":"connected"}`

---

## 🚀 Next Steps

1. **Test in Browser**: Access https://app.netguard.fun and test:
   - Hotspot manager functionality
   - WireGuard provisioning script generation
   - All other features

2. **Monitor Logs**: Watch for any errors:
   ```bash
   ssh root@74.208.167.166 'cd /opt/netguard && docker compose logs -f backend'
   ```

3. **Verify Data**: Ensure existing devices still work with decrypted passwords

---

## 📊 Summary

**Total Endpoints Fixed**: 9
- 8 Hotspot endpoints
- 1 WireGuard provisioning endpoint

**Status**: ✅ **All fixes deployed and ready for testing**
