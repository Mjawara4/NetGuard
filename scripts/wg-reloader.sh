#!/bin/sh
# Keep the live wg0 interface in step with its config file.
#
# WHY THIS EXISTS
#
# The NetGuard backend appends peers to the WireGuard config but cannot load
# them. wg0 lives in the wireguard container's network namespace, and no
# container in this stack has the docker socket, so nothing could reach the
# interface to reload it. A peer written by provision-wireguard therefore stayed
# inert until the container happened to restart. Combined with the provisioning
# script pinning SSH and the API to the tunnel subnet, a freshly provisioned
# router could never be reached -- and nothing anywhere reported an error.
#
# This runs INSIDE that namespace (network_mode: service:wireguard in
# docker-compose.yml), which is the only place `wg syncconf wg0` can work.
#
# `wg syncconf` adds and removes peers without disturbing the sessions of peers
# that are staying, so syncing does NOT interrupt a live tunnel. That matters:
# this stack has a production router passing tens of gigabytes through wg0.
set -eu

IFACE="${WG_IFACE:-wg0}"
POLL="${WG_RELOAD_POLL:-10}"

CONF="/config/wg_confs/${IFACE}.conf"
[ -f "$CONF" ] || CONF="/config/${IFACE}.conf"

log() { echo "[wg-reloader] $*"; }

if ! command -v wg >/dev/null 2>&1; then
    log "installing wireguard-tools"
    apk add --no-cache wireguard-tools >/dev/null 2>&1 || {
        log "FATAL: could not install wireguard-tools"
        exit 1
    }
fi

# Refuse to sync from a config that would wipe the interface. Without this, a
# truncated or half-written file would remove every live peer.
sane() {
    grep -q '^\[Interface\]' "$1" && grep -q '^PrivateKey' "$1"
}

sync_now() {
    mkdir -p /etc/wireguard
    cp "$CONF" "/etc/wireguard/${IFACE}.conf"
    chmod 600 "/etc/wireguard/${IFACE}.conf"

    if ! sane "/etc/wireguard/${IFACE}.conf"; then
        log "refusing to sync: $CONF has no [Interface] with a PrivateKey"
        return 1
    fi

    if ! wg-quick strip "$IFACE" >"/tmp/${IFACE}.stripped" 2>/dev/null; then
        log "could not parse $CONF; leaving the interface alone"
        return 1
    fi

    if ! wg syncconf "$IFACE" "/tmp/${IFACE}.stripped" 2>/dev/null; then
        log "syncconf failed (is $IFACE up yet?); will retry"
        return 1
    fi

    log "synced $(grep -c '^\[Peer\]' "/tmp/${IFACE}.stripped") peer(s) from $CONF"
    return 0
}

log "watching $CONF every ${POLL}s for interface $IFACE"

# Sync once at startup as well as on change. This self-heals the case this
# script was written for: peers already sitting in the config that the running
# interface never loaded.
last=""
while :; do
    if [ -f "$CONF" ]; then
        now=$(md5sum "$CONF" | cut -d' ' -f1)
        if [ "$now" != "$last" ]; then
            if sync_now; then
                last="$now"
            fi
        fi
    else
        log "config $CONF is not present"
    fi
    sleep "$POLL"
done
