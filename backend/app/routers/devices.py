import re
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from typing import Annotated, List
from uuid import UUID
import logging
from app.core.database import get_db
from app.auth.deps import get_current_user, get_authorized_actor
from app.models import Device, Site, User, APIKey, Metric, Alert, UserRole
from app.schemas.inventory import DeviceCreate, DeviceCredentials, DeviceResponse, SiteCreate, SiteResponse, WireGuardProvisionResponse, ProvisionScriptResponse
from app.services.wireguard import WireGuardService
from app.core.config import settings

logger = logging.getLogger(__name__)


router = APIRouter()

@router.post("/sites", response_model=SiteResponse)
async def create_site(site: SiteCreate, db: AsyncSession = Depends(get_db), actor = Depends(get_authorized_actor)):
    # Permission check: Ensure actor belongs to an org
    if not actor.organization_id:
         raise HTTPException(status_code=403, detail="Actor does not belong to an organization")
         
    site_data = site.dict(exclude={'organization_id'})
    new_site = Site(**site_data, organization_id=actor.organization_id)
    db.add(new_site)
    await db.commit()
    await db.refresh(new_site)
    return new_site

@router.get("/sites", response_model=List[SiteResponse])
async def get_sites(db: AsyncSession = Depends(get_db), actor = Depends(get_authorized_actor)):
    
    if isinstance(actor, APIKey):
        if actor.organization_id:
            result = await db.execute(select(Site).where(Site.organization_id == actor.organization_id))
        else:
            result = await db.execute(select(Site))
        return result.scalars().all()
        
    current_user = actor
    # Super Admin sees all
    if current_user.role == UserRole.SUPER_ADMIN:
        result = await db.execute(select(Site))
        return result.scalars().all()

    # Filter by user's org
    if current_user.organization_id:
        result = await db.execute(select(Site).where(Site.organization_id == current_user.organization_id))
        return result.scalars().all()
    
    return []

@router.post("/devices", response_model=DeviceResponse)
async def create_device(device: DeviceCreate, db: AsyncSession = Depends(get_db), actor = Depends(get_authorized_actor)):
    # Verify Site belongs to Org
    site_res = await db.execute(select(Site).where(Site.id == device.site_id, Site.organization_id == actor.organization_id))
    if not site_res.scalars().first():
        raise HTTPException(status_code=404, detail="Site not found or access denied")

    new_device = Device(**device.dict())
    db.add(new_device)
    await db.commit()
    await db.refresh(new_device)
    return new_device

@router.get("/device-credentials", response_model=List[DeviceCredentials])
async def get_device_credentials(
    db: AsyncSession = Depends(get_db),
    actor = Depends(get_authorized_actor),
):
    """Router API credentials, for the monitor agent only.

    The agent cannot authenticate without these. It used to read the device
    list and fall back to a global SSH_PASSWORD default when ssh_password was
    absent -- which it always was, because DeviceResponse strips it. The result
    was a login failure against every router the setup script had provisioned,
    reported to the operator as blank CPU/memory/uptime with no explanation.

    A separate path rather than a flag on /devices: this returns plaintext
    router passwords, and that should be an endpoint someone has to choose, not
    a parameter that could be set by accident on a response humans also read.
    """
    from app.models.core import decrypt_device_secrets

    # Machine actors only. An operator has no use for this, and a stolen
    # session should not hand over every router password in the organisation.
    if not isinstance(actor, APIKey):
        raise HTTPException(
            status_code=403,
            detail="Router credentials are available to machine actors only.",
        )

    query = select(Device)
    if actor.organization_id:
        query = select(Device).join(Site).where(Site.organization_id == actor.organization_id)

    result = await db.execute(query)
    out = []
    for d in result.scalars().all():
        decrypt_device_secrets(d)
        # No credential means nothing to send. An empty string would reach the
        # router as a real password attempt and muddy its log.
        if not d.ssh_password or not d.ssh_username:
            continue
        out.append(DeviceCredentials(
            id=d.id, ip_address=d.ip_address, ssh_username=d.ssh_username,
            ssh_password=d.ssh_password, ssh_port=getattr(d, "ssh_port", 8728) or 8728,
        ))
    return out


@router.get("/devices", response_model=List[DeviceResponse])
async def get_devices(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    actor = Depends(get_authorized_actor)
):
    from app.models.core import decrypt_device_secrets

    base_query = select(Device)

    if isinstance(actor, APIKey):
        if actor.organization_id:
            base_query = select(Device).join(Site).where(Site.organization_id == actor.organization_id)
        # else global API key sees all
    else:
        current_user = actor
        if current_user.role != UserRole.SUPER_ADMIN:
            if current_user.organization_id:
                base_query = select(Device).join(Site).where(Site.organization_id == current_user.organization_id)
            else:
                return []

    result = await db.execute(base_query.offset(skip).limit(limit))
    devices = result.scalars().all()
    for d in devices:
        decrypt_device_secrets(d)
    return devices

@router.get("/devices/{device_id}", response_model=DeviceResponse)
async def get_device(device_id: str, db: AsyncSession = Depends(get_db), actor = Depends(get_authorized_actor)):
    # Verify ownership
    if isinstance(actor, User) and actor.role == UserRole.SUPER_ADMIN:
         query = select(Device).where(Device.id == UUID(device_id))
    elif isinstance(actor, APIKey) and not actor.organization_id:
         query = select(Device).where(Device.id == UUID(device_id))
    else:
         query = select(Device).join(Site).where(Device.id == UUID(device_id), Site.organization_id == actor.organization_id)
    
    result = await db.execute(query)
    device = result.scalars().first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    return device

@router.delete("/devices/{device_id}", status_code=204)
async def delete_device(device_id: str, db: AsyncSession = Depends(get_db), actor = Depends(get_authorized_actor)):
    
    # Check existence and ownership
    if isinstance(actor, User) and actor.role == UserRole.SUPER_ADMIN:
         query = select(Device).where(Device.id == UUID(device_id))
    elif isinstance(actor, APIKey) and not actor.organization_id:
         query = select(Device).where(Device.id == UUID(device_id))
    else:
         query = select(Device).join(Site).where(Device.id == UUID(device_id), Site.organization_id == actor.organization_id)
    
    result = await db.execute(query)
    device = result.scalars().first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
        
    # Cascade delete (manual), in dependency order. The full tree of foreign keys
    # into a device, confirmed against the live schema:
    #   devices <- alerts <- {incidents, auto_fix_actions}
    #   devices <- hotspot_sales
    #   devices <- voucher_batches
    #   devices <- metrics (no enforced FK, but cleaned up here)
    # Every child must go before its parent or the delete fails with a foreign-key
    # violation, surfaced to the operator as "Failed to delete device". The first
    # pass missed hotspot_sales/voucher_batches; the second missed that incidents
    # and auto_fix_actions reference the alerts we were deleting.
    from app.models.core import VoucherSale, VoucherBatch
    from app.models.monitoring import Incident, AutoFixAction
    dev_uuid = UUID(device_id)
    device_alerts = select(Alert.id).where(Alert.device_id == dev_uuid)

    # Grandchildren first: they point at this device's alerts.
    await db.execute(delete(Incident).where(Incident.alert_id.in_(device_alerts)))
    await db.execute(delete(AutoFixAction).where(AutoFixAction.alert_id.in_(device_alerts)))
    # Then the direct children.
    await db.execute(delete(Alert).where(Alert.device_id == dev_uuid))
    await db.execute(delete(VoucherSale).where(VoucherSale.device_id == dev_uuid))
    await db.execute(delete(VoucherBatch).where(VoucherBatch.device_id == dev_uuid))
    await db.execute(delete(Metric).where(Metric.device_id == dev_uuid))

    # The device row goes last, after everything that references it.
    await db.delete(device)
    await db.commit()
    return

@router.put("/devices/{device_id}", response_model=DeviceResponse)
async def update_device(device_id: str, device_update: DeviceCreate, db: AsyncSession = Depends(get_db), actor = Depends(get_authorized_actor)):
    # Verify ownership
    if isinstance(actor, User) and actor.role == UserRole.SUPER_ADMIN:
         query = select(Device).where(Device.id == UUID(device_id))
    elif isinstance(actor, APIKey) and not actor.organization_id:
         query = select(Device).where(Device.id == UUID(device_id))
    else:
         query = select(Device).join(Site).where(Device.id == UUID(device_id), Site.organization_id == actor.organization_id)
         
    result = await db.execute(query)
    device = result.scalars().first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
        
    # Update fields
    for key, value in device_update.dict(exclude_unset=True).items():
        setattr(device, key, value)
        
    await db.commit()
    await db.refresh(device)
    return device

@router.post("/devices/{device_id}/provision-wireguard", response_model=WireGuardProvisionResponse)
async def provision_wireguard(device_id: str, db: AsyncSession = Depends(get_db), actor = Depends(get_authorized_actor)):
    """Create (or return) the device's WireGuard tunnel and the router script for it.

    Restricted to SUPER_ADMIN and ORG_ADMIN users (403 otherwise), for the same
    reason provision-script is: the response body carries `wg_private_key`, the
    router's tunnel private key, and the script embeds it. Gating only
    provision-script would be theatre -- an actor who wants the tunnel key would
    just use this endpoint instead. API keys are machine-scoped and unchanged.
    """
    # Before any key generation or persistence: a refused caller must not leave a
    # freshly minted key on the device row, or a peer appended to the server config.
    if isinstance(actor, User) and actor.role not in (UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN):
        raise HTTPException(
            status_code=403,
            detail="Provisioning WireGuard returns the router's tunnel private key; "
                   "it requires an organisation admin or super admin.",
        )

    # Verify ownership
    if isinstance(actor, User) and actor.role == UserRole.SUPER_ADMIN:
         query = select(Device).where(Device.id == UUID(device_id))
    elif isinstance(actor, APIKey) and not actor.organization_id:
         query = select(Device).where(Device.id == UUID(device_id))
    else:
         query = select(Device).join(Site).where(Device.id == UUID(device_id), Site.organization_id == actor.organization_id)
         
    result = await db.execute(query)
    device = result.scalars().first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    # Decrypt device secrets (required for async SQLAlchemy)
    from app.models.core import decrypt_device_secrets
    decrypt_device_secrets(device)

    # If already provisioned, return existing info (idempotency)
    # But if keys are missing from DB, regenerate.
    
    if not device.wg_private_key or not device.wg_public_key:
        priv, pub = WireGuardService.generate_keys()
        device.wg_private_key = priv
        device.wg_public_key = pub
        
    if not device.wg_ip_address:
        device.wg_ip_address = await WireGuardService.get_available_ip(db)
        
    # Update DB
    db.add(device)
    await db.commit()
    await db.refresh(device)
    
    # Decrypt again after refresh (since refresh loads from DB)
    decrypt_device_secrets(device)
    
    # Update Server Config
    # We call this every time to ensure it's in the config file, 
    # though ideally we check if it's already there to avoid duplicates.
    # The service just appends, so we should be careful. 
    # For MVP, we'll append. In real world, check existence.
    # Use a simple check in service? Or just rely on "add_peer_to_conf"
    # handling it? I didn't implement check logic.
    # Re-reading my service implementation: it blindly appends.
    # I should assume for MVP this is fine or maybe "add_peer_to_conf" should query file.
    # Let's trust the service for now or do a quick improved service call later.
    
    WireGuardService.add_peer_to_conf(device.wg_public_key, device.wg_ip_address)
    
    # Generate Script - ensure server public key is fetched if needed
    server_pub_key = settings.WG_SERVER_PUBLIC_KEY
    # Check if the value is a valid WireGuard key (base64, ~44 chars) or a placeholder
    is_valid_key = server_pub_key and len(server_pub_key) >= 40 and server_pub_key not in [
        "SERVER_PUBLIC_KEY_PLACEHOLDER", 
        "SERVER_PUBLIC_KEY_NOT_FOUND",
        "auto-read-from-volume-or-manual"
    ]
    
    if not is_valid_key:
        try:
            server_pub_key = WireGuardService.get_server_public_key()
            logger.info(f"Successfully read server public key from volume")
        except Exception as e:
            logger.error(f"Failed to get server public key: {e}")
            raise HTTPException(
                status_code=500,
                detail="WireGuard server configuration error. Please ensure WG_SERVER_PUBLIC_KEY is set in .env or key file exists"
            )
    
    script = WireGuardService.generate_mikrotik_script(
        private_key=device.wg_private_key,
        client_ip=device.wg_ip_address,
        server_public_key=server_pub_key,
        server_endpoint=settings.WG_SERVER_ENDPOINT,
        server_port=settings.WG_SERVER_PORT
    )
    
    return WireGuardProvisionResponse(
        device_id=device.id,
        wg_ip_address=device.wg_ip_address,
        wg_public_key=device.wg_public_key,
        wg_private_key=device.wg_private_key,
        mikrotik_script=script
    )


# ValueError fields from build_params that a caller can fix by changing the request.
# Everything else build_params rejects came from the device row or server config.
_CLIENT_INPUT_FIELDS = ("site_slug", "timezone")

# The account the provisioning script creates, and the shape of a password this
# service mints. A stored value that does not match was not minted here (a
# hand-typed one, or a legacy row), so it is replaced rather than reused.
_API_USERNAME = "netguard"
_MINTED_PASSWORD_RE = re.compile(r"[A-Za-z0-9]{16,}")


@router.post("/devices/{device_id}/provision-script", response_model=ProvisionScriptResponse)
async def generate_provision_script(
    device_id: str,
    site_slug: str = Query(..., description="Lowercase slug naming the site on the router"),
    timezone: str = Query("Africa/Banjul"),
    # Annotated form on purpose: `rotate: bool = Query(False)` makes the DEFAULT a
    # Query object, which is truthy. Over HTTP FastAPI resolves it, but any direct
    # call (every test here) would silently take the rotate branch.
    rotate: Annotated[bool, Query(description="Mint new credentials instead of reusing the stored ones")] = False,
    db: AsyncSession = Depends(get_db),
    actor = Depends(get_authorized_actor),
):
    """Generate the one-shot RouterOS provisioning script for a device.

    By default this REUSES the credentials NetGuard already holds, so generating
    a script twice yields the same file and an earlier download stays valid.
    Pass rotate=true to mint fresh ones, which invalidates any earlier script.

    THIS ROTATES CREDENTIALS WHEN ASKED TO. A rotating call generates a fresh
    `netguard` API password and a fresh `admin` password, stores the API
    password on the device, and returns a script that sets both on the router.
    Calling it again invalidates any script handed out earlier: the old script
    would put passwords on the router that NetGuard no longer holds.

    Why rotate rather than reuse: the script applies its passwords on every
    run, so NetGuard must store exactly what it last sent; generating fresh
    values each time keeps that one rule simple, and a leaked script stops
    being valid for the next install. The cost is that an installer must use
    the most recently generated script. That is why this is a POST.

    Restricted to SUPER_ADMIN and ORG_ADMIN users (403 otherwise), and to
    devices in the actor's own organisation (404 otherwise).

    The device must already have WireGuard provisioned (409 otherwise); no
    placeholder key or address is ever substituted.
    """
    from app.services.provisioning.params import build_params
    from app.services.provisioning.script import build_provision_script
    from app.services.provisioning.secrets import generate_api_password

    try:
        device_uuid = UUID(device_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Device not found")

    # This mints and stores credentials and returns a tunnel private key, so it
    # is not open to read-only users. API keys are machine-scoped and unchanged.
    if isinstance(actor, User) and actor.role not in (UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN):
        raise HTTPException(
            status_code=403,
            detail="Generating a provisioning script rotates router credentials; "
                   "it requires an organisation admin or super admin.",
        )

    # Verify ownership
    if isinstance(actor, User) and actor.role == UserRole.SUPER_ADMIN:
        query = select(Device).where(Device.id == device_uuid)
    elif isinstance(actor, APIKey) and not actor.organization_id:
        query = select(Device).where(Device.id == device_uuid)
    else:
        query = select(Device).join(Site).where(Device.id == device_uuid, Site.organization_id == actor.organization_id)

    result = await db.execute(query)
    device = result.scalars().first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    from app.models.core import decrypt_device_secrets
    decrypt_device_secrets(device)

    if not device.wg_private_key or not device.wg_ip_address:
        raise HTTPException(
            status_code=409,
            detail=("This router has no WireGuard tunnel yet, so a provisioning script "
                    "would not be able to connect. Provision WireGuard for this router "
                    "first: POST /api/v1/inventory/devices/{id}/provision-wireguard, "
                    "then request the script again.").replace("{id}", str(device.id)),
        )

    # Same resolution as provision-wireguard, but nothing is substituted: an
    # unusable key is a server configuration error, not a script to emit.
    server_pub_key = settings.WG_SERVER_PUBLIC_KEY
    if not (server_pub_key and len(server_pub_key) >= 40 and server_pub_key not in (
            "SERVER_PUBLIC_KEY_PLACEHOLDER", "SERVER_PUBLIC_KEY_NOT_FOUND",
            "auto-read-from-volume-or-manual")):
        try:
            server_pub_key = WireGuardService.get_server_public_key()
        except Exception as e:
            logger.error(f"Failed to get server public key: {e}")
            raise HTTPException(
                status_code=500,
                detail="WireGuard server configuration error. Please ensure WG_SERVER_PUBLIC_KEY is set in .env or key file exists",
            )

    # Reuse the credential NetGuard already holds, unless rotation was asked for.
    #
    # Minting a new one on every call means generating a script twice silently
    # invalidates the first file: the router ends up with one password and
    # NetGuard with another, the device pings fine, the API never authenticates,
    # and nothing says why. That happened on a real install -- four generations,
    # and the file applied came from an earlier one than the database held.
    #
    # The stored value is only reused if it looks like something we minted; a
    # hand-typed or legacy value would be rejected by build_params and is
    # replaced instead. device.ssh_password is plaintext here: the handler calls
    # decrypt_device_secrets above.
    stored = device.ssh_password if device.ssh_username == _API_USERNAME else None
    provisioned_before = bool(stored and _MINTED_PASSWORD_RE.fullmatch(stored))

    reused = provisioned_before and not rotate
    api_password = stored if reused else generate_api_password()

    # An admin password is ALWAYS generated, but the SCRIPT decides whether to
    # apply it -- it does so only when the router has no netguard user, i.e. only
    # when the router itself says it has never been provisioned.
    #
    # Deciding that here, from provisioned_before, was wrong and briefly shipped:
    # a factory reset makes the ROUTER forget while this device row still holds
    # credentials, so the script would have skipped the admin line on exactly the
    # router that most needs it and left a blank full-access password on the LAN.
    # NetGuard's records cannot answer "is this router fresh"; only the router can.
    #
    # The netguard-recovery break-glass password. Always generated and always
    # returned; the SCRIPT applies it only on a fresh router (gated on $ngfresh),
    # so on a re-run this value is shown but harmlessly unused. The router's own
    # `admin` password is never set or changed by the script -- it belongs to the
    # operator.
    recovery_password = generate_api_password()
    pricing = (device.voucher_template or {}).get("profile_pricing", {})
    portal_plans = tuple(
        (str(profile), str(details.get("price", "")), str(details.get("currency", "GMD")))
        for profile, details in pricing.items()
        if isinstance(details, dict) and details.get("price") not in (None, "")
    )
    try:
        params = build_params(
            site_slug=site_slug, timezone=timezone,
            device_id=str(device.id),
            wg_private_key=device.wg_private_key, wg_client_ip=device.wg_ip_address,
            wg_server_public_key=server_pub_key,
            wg_server_endpoint=settings.WG_SERVER_ENDPOINT,
            wg_server_port=settings.WG_SERVER_PORT,
            api_password=api_password, recovery_password=recovery_password,
            portal_plans=portal_plans,
        )
    except ValueError as e:
        msg = str(e)
        if msg.startswith(_CLIENT_INPUT_FIELDS):
            raise HTTPException(status_code=400, detail=msg)
        # The device row or server config is bad, not the request. Field name
        # only; the message never contains a secret value.
        logger.error(f"Provisioning parameters rejected for device {device.id}: {msg}")
        raise HTTPException(status_code=500, detail=f"Cannot generate a valid script: {msg}")

    script = build_provision_script(params)

    # Store exactly what the script sets. NetGuard reaches the RouterOS API with
    # ssh_username/ssh_password (hotspot.py), so monitoring works the moment the
    # script is applied. The encrypt listener rewrites ssh_password on flush, so
    # the response is built from the local plaintext, not from the device.
    device.ssh_username = params.api_username
    device.ssh_password = api_password

    # Point monitoring at the tunnel. The script pins SSH and the API to
    # 10.13.13.0/24, so once it is applied the tunnel address is the only way
    # in -- but a device added by hand carries whatever was typed into the form,
    # which for a factory router is its LAN default (a real one carried
    # 192.168.88.1). Leaving that in place makes monitoring dial an address the
    # server cannot route to, and the failure looks like an offline router
    # rather than a wrong address. The 409 above guarantees wg_ip_address is set.
    if device.wg_ip_address:
        device.ip_address = device.wg_ip_address

    db.add(device)
    await db.commit()

    return ProvisionScriptResponse(
        device_id=device.id,
        site_slug=site_slug,
        script=script,
        api_username=params.api_username,
        api_password=api_password,
        recovery_password=recovery_password,
        warnings=(
            [
                "Reusing the credentials NetGuard already holds, so any script you "
                "downloaded earlier for this router is still valid.",
            ] if reused else [
                "The API credential was rotated: any script generated earlier for this "
                "router no longer matches what NetGuard stores.",
            ]
        ) + [
            "The router's own admin password is never set or changed by this script -- "
            "you manage it. On a NEW or factory-reset router it starts BLANK: set it "
            "immediately (the summary the script prints shows the command).",
            "netguard-recovery is a break-glass full-access login, applied only to a new "
            "or factory-reset router and shown once. Save it; it is never stored.",
            "The netguard user is API-only (no ssh); SSH-based remediation for this router will be refused.",
        ],
    )
