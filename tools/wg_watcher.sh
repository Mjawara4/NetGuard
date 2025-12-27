#!/bin/bash
# Watcher script to reload WireGuard when config changes

WG_CONF="/root/NetGuard/wireguard-config/wg_confs/wg0.conf"
LAST_HASH_FILE="/root/NetGuard/.wg_last_hash"
LOG_FILE="/root/NetGuard/wg_watcher.log"

timestamp() {
    date "+%Y-%m-%d %H:%M:%S"
}

if [ ! -f "$WG_CONF" ]; then
    echo "$(timestamp) Config file not found: $WG_CONF" >> "$LOG_FILE"
    exit 0
fi

CURRENT_HASH=$(md5sum "$WG_CONF" | awk '{print $1}')

if [ ! -f "$LAST_HASH_FILE" ]; then
    echo "$CURRENT_HASH" > "$LAST_HASH_FILE"
    # First run, assume up to date or don't trigger restart yet
    exit 0
fi

LAST_HASH=$(cat "$LAST_HASH_FILE")

if [ "$CURRENT_HASH" != "$LAST_HASH" ]; then
    echo "$(timestamp) Change detected. Previous: $LAST_HASH, New: $CURRENT_HASH" >> "$LOG_FILE"
    
    # Reload WireGuard
    # We use /bin/sh -c inside docker to properly handle the redirection <(...)
    # But <() is bashism. wg-quick strip prints to stdout.
    # We can pipe it: wg-quick strip wg0 | wg syncconf wg0 /dev/stdin
    
    docker exec netguard-wireguard /bin/sh -c 'wg-quick strip wg0 | wg syncconf wg0 /dev/stdin' >> "$LOG_FILE" 2>&1
    
    EXIT_CODE=$?
    
    if [ $EXIT_CODE -eq 0 ]; then
        echo "$(timestamp) Reload successful." >> "$LOG_FILE"
        echo "$CURRENT_HASH" > "$LAST_HASH_FILE"
    else
        echo "$(timestamp) Reload FAILED with code $EXIT_CODE" >> "$LOG_FILE"
    fi
fi
