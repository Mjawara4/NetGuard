#!/usr/bin/env bash
# Apply a RouterOS script to a throwaway MikroTik CHR VM and fail on any RouterOS error.
# Usage: scripts/chr-smoke-test.sh [--paste] [--setup FILE] [--prepend FILE] [--expect-abort TEXT [--not-reached TEXT]] <script-file>
#   (default)  upload the file and run `/import` (aborts the FILE at the first error or `:error`)
#   --paste    type the file into a real pty terminal session, as a person pasting into a terminal
#              would. `:error` does NOT abort a paste unless the script is one brace block, so a
#              refusal guard must be verified in this mode. See docs/chr-smoke-test.md.
#   --setup F  first run each non-blank, non-# line of F as a RouterOS command (build the "router
#              that already has X" the script should refuse)
#   --prepend F  put the contents of F in front of the script in the SAME session. Use it (not --setup)
#              for setup that cuts the harness's own ssh, e.g. a stock firewall whose `drop all not coming
#              from LAN` refuses new connections on the ether1 management path.
#   --expect-abort TEXT   invert the verdict: PASS only if TEXT appears in the router's own output
#              (not an echo of the source) and, with --not-reached, that other text does NOT.
# Exit: 0 clean, 1 RouterOS reported an error, 2 harness/infra problem (never a silent pass).
set -uo pipefail

CHR_VERSION="${CHR_VERSION:-7.16.2}"
CACHE_DIR="${CHR_CACHE_DIR:-/tmp/chr}"
# Free port picked at run time so concurrent runs cannot collide (CHR_SSH_PORT overrides).
SSH_PORT="${CHR_SSH_PORT:-$(python3 -c 'import socket;s=socket.socket();s.bind(("127.0.0.1",0));print(s.getsockname()[1])')}"
BOOT_TIMEOUT="${CHR_BOOT_TIMEOUT:-180}"
APPLY_TIMEOUT="${CHR_APPLY_TIMEOUT:-120}"
URL="https://download.mikrotik.com/routeros/${CHR_VERSION}/chr-${CHR_VERSION}.img.zip"

# Markers RouterOS prints on failure (it often exits 0 regardless). Case-insensitive.
ERROR_MARKERS=(
  'syntax error' 'expected end of command' 'no such item' 'failure:'
  'input does not match' 'invalid value' 'bad command name' 'cannot'
  'script error' 'bad argument' 'unknown parameter' 'ambiguous' 'not enough permissions'
  'missing closing brace' 'missing value'
)
# In --expect-abort mode a refusal is the pass condition, but a parse failure never is.
SYNTAX_MARKERS=('syntax error' 'expected end of command' 'missing closing brace' 'bad command name')

MODE=import; SETUP=""; PREPEND=""; EXPECT_ABORT=""; NOT_REACHED=""
while [ $# -gt 1 ]; do
  case "$1" in
    --paste) MODE=paste; shift;;
    --setup) SETUP="$2"; shift 2;;
    --prepend) PREPEND="$2"; shift 2;;
    --expect-abort) EXPECT_ABORT="$2"; shift 2;;
    --not-reached) NOT_REACHED="$2"; shift 2;;
    *) echo "usage: $0 [--paste] [--setup FILE] [--prepend FILE] [--expect-abort TEXT [--not-reached TEXT]] <script-file>" >&2; exit 2;;
  esac
done
[ $# -eq 1 ] && [ -f "$1" ] || { echo "usage: $0 [--paste] [--setup FILE] [--prepend FILE] [--expect-abort TEXT [--not-reached TEXT]] <script-file>" >&2; exit 2; }
[ -z "$PREPEND" ] || [ -f "$PREPEND" ] || { echo "harness: --prepend file not found" >&2; exit 2; }
[ -z "$SETUP" ] || [ -f "$SETUP" ] || { echo "harness: --setup file not found" >&2; exit 2; }
[ -z "$NOT_REACHED" ] || [ -n "$EXPECT_ABORT" ] || { echo "harness: --not-reached needs --expect-abort" >&2; exit 2; }
SCRIPT="$(readlink -f "$1")"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ "$MODE" = paste ]; then
  python3 -c 'import pexpect' 2>/dev/null || { echo "harness: --paste needs python3-pexpect" >&2; exit 2; }
fi
for t in qemu-system-x86_64 qemu-img unzip curl ssh sshpass; do
  command -v "$t" >/dev/null || { echo "harness: missing tool $t" >&2; exit 2; }
done
[ -w /dev/kvm ] || { echo "harness: /dev/kvm not usable" >&2; exit 2; }

# A script with no executable statement (only comments/blank lines) proves nothing: refuse it.
if ! grep -qvE '^[[:space:]]*(#.*)?$' "$SCRIPT"; then
  echo "harness: script has no non-comment statements; nothing to verify" >&2; exit 2
fi
if grep -q 'on-error' "$SCRIPT"; then
  echo "harness: WARNING: script contains on-error; RouterOS failures inside :do{} on-error={} are suppressed, so PASS does not mean every command applied" >&2
fi

WORK="$(mktemp -d /tmp/chr-run.XXXXXX)"
QPID=""
cleanup() {
  [ -n "$QPID" ] && kill "$QPID" 2>/dev/null && wait "$QPID" 2>/dev/null
  rm -rf "$WORK"
}
trap cleanup EXIT
trap "exit 130" INT TERM

if [ -n "$PREPEND" ]; then
  cat "$PREPEND" "$SCRIPT" >"$WORK/combined.rsc" && SCRIPT="$WORK/combined.rsc"
fi

mkdir -p "$CACHE_DIR"
ZIP="$CACHE_DIR/chr-${CHR_VERSION}.img.zip"
if [ ! -s "$ZIP" ]; then
  curl -fsSL --retry 5 --retry-all-errors -C - --max-time 600 -o "$ZIP.part" "$URL" && mv "$ZIP.part" "$ZIP" \
    || { echo "harness: download failed: $URL" >&2; exit 2; }
fi
unzip -q -o "$ZIP" -d "$WORK" || { echo "harness: unzip failed" >&2; exit 2; }
IMG="$(ls "$WORK"/*.img | head -1)"
qemu-img resize -f raw "$IMG" 128M >/dev/null || { echo "harness: resize failed" >&2; exit 2; }

# ether1 is the SSH-forwarded NIC; ether2..ether8 mirror the reference L009 port count so
# generated bridge config is not rejected for missing hardware.
EXTRA_NICS=()
for i in 1 2 3 4 5 6 7; do
  EXTRA_NICS+=(-netdev "user,id=x$i,restrict=on" -device "virtio-net-pci,netdev=x$i")
done

qemu-system-x86_64 -enable-kvm -m 256 -nographic -display none -monitor none \
  -serial file:"$WORK/serial.log" \
  -drive file="$IMG",format=raw,if=virtio \
  -netdev user,id=n0,hostfwd=tcp:127.0.0.1:${SSH_PORT}-:22 -device virtio-net-pci,netdev=n0 \
  "${EXTRA_NICS[@]}" \
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

if [ -n "$SETUP" ]; then
  while IFS= read -r cmd <&3; do
    case "$cmd" in ''|'#'*) continue;; esac
    rsh "$cmd" 30 </dev/null >/dev/null 2>"$WORK/setup.err" \
      || { echo "harness: setup command failed: $cmd" >&2; cat "$WORK/setup.err" >&2; exit 2; }
  done 3<"$SETUP"
fi

OUT="$WORK/output.txt"
if [ "$MODE" = paste ]; then
  # A real pty session. Not `ssh < file`: that is not a paste (see scripts/chr-paste.py).
  python3 "$HERE/chr-paste.py" "$SSH_PORT" "$SCRIPT" "$APPLY_TIMEOUT" >"$OUT" 2>"$WORK/paste.err"
  rc=$?
  cat "$WORK/paste.err" >&2
  [ $rc -eq 2 ] && { echo "harness: could not drive the paste session" >&2; exit 2; }
  # Drop the terminal's prompt/continuation prefixes so an echoed source line compares equal to the source.
  # The terminal also redraws a long echoed line with trailing `{...` continuation prompts: drop those too.
  sed -i -E 's/^(\[[^]]*\] > |\{+\.\.\. )//; s/([[:space:]]*\{+\.\.\.[[:space:]]*)+$//' "$OUT"
else
  # Upload and /import: import aborts at the first bad line and reports it, and we still grep too.
  cp "$SCRIPT" "$WORK/smoke.rsc"
  sshpass -p '' scp -P "$SSH_PORT" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    -o LogLevel=ERROR -o ConnectTimeout=5 -O "$WORK/smoke.rsc" admin@127.0.0.1:smoke.rsc \
    >"$WORK/scp.log" 2>&1 || sshpass -p '' scp -P "$SSH_PORT" -o StrictHostKeyChecking=no \
    -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR -o ConnectTimeout=5 "$WORK/smoke.rsc" admin@127.0.0.1:smoke.rsc \
    >"$WORK/scp.log" 2>&1 || { echo "harness: upload failed" >&2; cat "$WORK/scp.log" >&2; exit 2; }
  rsh '/import file-name=smoke.rsc verbose=yes' "$APPLY_TIMEOUT" >"$OUT" 2>&1
  rc=$?
fi
echo "----- router output ($MODE) -----"
cat "$OUT"
echo "----- end router output -----"

# verbose=yes echoes "#line N" and each SOURCE line (comments included). Strip those before
# matching so a comment that says "cannot" is not mistaken for a RouterOS diagnostic.
DIAG="$WORK/diag.txt"
awk 'NR==FNR { t=$0; gsub(/^[ \t]+|[ \t\r]+$/,"",t); if (t!="") src[t]=1; next }
     { t=$0; gsub(/^[ \t]+|[ \t\r]+$/,"",t); if (t=="" || t ~ /^#line / || (t in src)) next; print }' \
  "$SCRIPT" "$OUT" >"$DIAG"

if [ -n "$EXPECT_ABORT" ]; then
  # PASS means the script REFUSED: the refusal text came from the router (echoes of the source are
  # already filtered out of DIAG), nothing after the refusal ran, and it did not fail to parse.
  for m in "${SYNTAX_MARKERS[@]}"; do
    if grep -qi -- "$m" "$DIAG"; then echo "harness: FAIL: parse failure '$m' (a refusal that cannot parse is not a refusal)" >&2; exit 1; fi
  done
  if ! grep -qF -- "$EXPECT_ABORT" "$DIAG"; then
    echo "harness: FAIL: expected the refusal '$EXPECT_ABORT' in the router's output; it never appeared" >&2; exit 1
  fi
  if [ -n "$NOT_REACHED" ] && grep -qF -- "$NOT_REACHED" "$DIAG"; then
    echo "harness: FAIL: '$EXPECT_ABORT' was printed but the script ran on regardless ('$NOT_REACHED' appeared)" >&2; exit 1
  fi
  echo "harness: PASS (refused as expected, mode=$MODE)" >&2; exit 0
fi

hits=0
# A prompt RouterOS printed, WHATEVER the swallowed line was: a blank line leaves `password: `, a real
# command leaves `password: ****` (one asterisk per swallowed character). Anchored at the line start with
# only letters before the prompt, and only asterisks after it, so `API user: x (password: see ...)` and
# `admin password:   set to ...` in the script's own output are not mistaken for one.
PROMPT_RE='^[A-Za-z ]*password: *[*]*$|\[[yY]/[nN]\]: *[A-Za-z]?$'
if [ "$MODE" = paste ] && grep -Eq "$PROMPT_RE" "$DIAG"; then
  # An interactive CLI asks for a missing required argument and reads the NEXT pasted line as the
  # answer. `/import` just errors, so this only shows up in a paste.
  echo "harness: FAIL: the script made RouterOS prompt interactively; a paste feeds its next line into the prompt:" >&2
  grep -E "$PROMPT_RE" "$DIAG" | sed 's/^/    /' >&2
  hits=1
fi
for m in "${ERROR_MARKERS[@]}"; do
  if grep -qi -- "$m" "$DIAG"; then
    echo "harness: FAIL: RouterOS error marker '$m':" >&2
    grep -i -- "$m" "$DIAG" | sed 's/^/    /' >&2
    hits=1
  fi
done
[ $rc -eq 124 ] && { echo "harness: apply timed out" >&2; exit 2; }
[ $hits -eq 1 ] && exit 1
if [ "$MODE" = paste ]; then
  # A paste prints no `#line` trace. The driver's sentinel proves the session ran to the end.
  [ $rc -eq 0 ] && grep -q 'CHR-PASTE-END status=0' "$OUT" \
    || { echo "harness: paste never reached its end sentinel (rc=$rc); refusing to pass" >&2; exit 1; }
else
  # RouterOS prints no success line. Prove the import ran: the script has a non-comment statement
  # (checked above) and verbose=yes must have traced it. No trace or non-zero ssh status is no pass.
  grep -q '^#line' "$OUT" && [ $rc -eq 0 ] \
    || { echo "harness: import produced no statement trace (ssh rc=$rc); refusing to pass" >&2; exit 1; }
fi
echo "harness: PASS" >&2
exit 0
