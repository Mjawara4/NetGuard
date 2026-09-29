#!/usr/bin/env bash
# Apply a RouterOS script to a throwaway MikroTik CHR VM and fail on any RouterOS error.
# Usage: scripts/chr-smoke-test.sh <script-file>
# Exit: 0 clean, 1 RouterOS reported an error, 2 harness/infra problem (never a silent pass).
set -uo pipefail

CHR_VERSION="${CHR_VERSION:-7.16.2}"
CACHE_DIR="${CHR_CACHE_DIR:-/tmp/chr}"
SSH_PORT="${CHR_SSH_PORT:-2222}"
BOOT_TIMEOUT="${CHR_BOOT_TIMEOUT:-180}"
APPLY_TIMEOUT="${CHR_APPLY_TIMEOUT:-120}"
URL="https://download.mikrotik.com/routeros/${CHR_VERSION}/chr-${CHR_VERSION}.img.zip"

# Markers RouterOS prints on failure (it often exits 0 regardless). Case-insensitive.
ERROR_MARKERS=(
  'syntax error' 'expected end of command' 'no such item' 'failure:'
  'input does not match' 'invalid value' 'bad command name' 'cannot'
  'script error' 'bad argument' 'unknown parameter' 'ambiguous' 'not enough permissions'
)

[ $# -eq 1 ] && [ -f "$1" ] || { echo "usage: $0 <script-file>" >&2; exit 2; }
SCRIPT="$(readlink -f "$1")"
for t in qemu-system-x86_64 qemu-img unzip curl ssh sshpass; do
  command -v "$t" >/dev/null || { echo "harness: missing tool $t" >&2; exit 2; }
done
[ -w /dev/kvm ] || { echo "harness: /dev/kvm not usable" >&2; exit 2; }

WORK="$(mktemp -d /tmp/chr-run.XXXXXX)"
QPID=""
cleanup() {
  [ -n "$QPID" ] && kill "$QPID" 2>/dev/null && wait "$QPID" 2>/dev/null
  rm -rf "$WORK"
}
trap cleanup EXIT INT TERM

mkdir -p "$CACHE_DIR"
ZIP="$CACHE_DIR/chr-${CHR_VERSION}.img.zip"
if [ ! -s "$ZIP" ]; then
  curl -fsSL --retry 5 --retry-all-errors -C - --max-time 600 -o "$ZIP.part" "$URL" && mv "$ZIP.part" "$ZIP" \
    || { echo "harness: download failed: $URL" >&2; exit 2; }
fi
unzip -q -o "$ZIP" -d "$WORK" || { echo "harness: unzip failed" >&2; exit 2; }
IMG="$(ls "$WORK"/*.img | head -1)"
qemu-img resize -f raw "$IMG" 128M >/dev/null || { echo "harness: resize failed" >&2; exit 2; }

qemu-system-x86_64 -enable-kvm -m 256 -nographic -display none -monitor none \
  -serial file:"$WORK/serial.log" \
  -drive file="$IMG",format=raw,if=virtio \
  -netdev user,id=n0,hostfwd=tcp:127.0.0.1:${SSH_PORT}-:22 -device virtio-net-pci,netdev=n0 \
  >"$WORK/qemu.log" 2>&1 &
QPID=$!

# "+ct": no colours, no terminal probing, so output is plain text and no prompt can hang us.
SSH_OPTS=(-p "$SSH_PORT" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null
  -o LogLevel=ERROR -o ConnectTimeout=5 -o PreferredAuthentications=password,keyboard-interactive
  -o PubkeyAuthentication=no -o KexAlgorithms=+diffie-hellman-group14-sha1,diffie-hellman-group-exchange-sha256
  -o HostKeyAlgorithms=+ssh-rsa -o ServerAliveInterval=5 -o ServerAliveCountMax=6)
rsh() { timeout "${2:-30}" sshpass -p '' ssh "${SSH_OPTS[@]}" "admin+ct@127.0.0.1" "$1"; }

echo "harness: booting CHR ${CHR_VERSION} (timeout ${BOOT_TIMEOUT}s)" >&2
deadline=$((SECONDS + BOOT_TIMEOUT)); up=0
while [ $SECONDS -lt $deadline ]; do
  kill -0 "$QPID" 2>/dev/null || { echo "harness: qemu died:" >&2; cat "$WORK/qemu.log" >&2; exit 2; }
  if out="$(rsh '/system resource print' 15 2>&1)" && grep -qi 'version' <<<"$out"; then up=1; break; fi
  sleep 3
done
[ $up -eq 1 ] || { echo "harness: CHR never became reachable over SSH" >&2; tail -5 "$WORK/serial.log" >&2; exit 2; }
echo "harness: router up: $(grep -i '^ *version' <<<"$out" | head -1 | xargs)" >&2

# Upload and /import: import aborts at the first bad line and reports it, and we still grep too.
cp "$SCRIPT" "$WORK/smoke.rsc"
sshpass -p '' scp -P "$SSH_PORT" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
  -o LogLevel=ERROR -o ConnectTimeout=5 -O "$WORK/smoke.rsc" admin@127.0.0.1:smoke.rsc \
  >"$WORK/scp.log" 2>&1 || sshpass -p '' scp -P "$SSH_PORT" -o StrictHostKeyChecking=no \
  -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR -o ConnectTimeout=5 "$WORK/smoke.rsc" admin@127.0.0.1:smoke.rsc \
  >"$WORK/scp.log" 2>&1 || { echo "harness: upload failed" >&2; cat "$WORK/scp.log" >&2; exit 2; }

OUT="$WORK/output.txt"
rsh '/import file-name=smoke.rsc verbose=yes' "$APPLY_TIMEOUT" >"$OUT" 2>&1
rc=$?
echo "----- router output -----"
cat "$OUT"
echo "----- end router output -----"

hits=0
for m in "${ERROR_MARKERS[@]}"; do
  if grep -qi -- "$m" "$OUT"; then
    echo "harness: FAIL: RouterOS error marker '$m':" >&2
    grep -i -- "$m" "$OUT" | sed 's/^/    /' >&2
    hits=1
  fi
done
[ $rc -eq 124 ] && { echo "harness: apply timed out" >&2; exit 2; }
[ $hits -eq 1 ] && exit 1
# RouterOS prints no success line, so prove the import actually ran: verbose=yes echoes
# "#line N" for each statement. No echo, or a non-zero ssh status, is not a pass.
grep -q '^#line' "$OUT" && [ $rc -eq 0 ] \
  || { echo "harness: import produced no statement trace (ssh rc=$rc); refusing to pass" >&2; exit 1; }
echo "harness: PASS" >&2
exit 0
