# CHR smoke test

`scripts/chr-smoke-test.sh <script.rsc>` boots a throwaway MikroTik CHR (RouterOS 7.16.2) under
QEMU/KVM, uploads the script, runs `/import file-name=smoke.rsc verbose=yes`, prints the router's
own output, and exits non-zero on any RouterOS error. The VM and temp dir are removed on exit
(`trap`), including on failure or Ctrl-C.

## Run

    scripts/chr-smoke-test.sh path/to/script.rsc; echo $?

Needs `qemu-system-x86`, `qemu-utils`, `sshpass`, `unzip`, `curl`, and `/dev/kvm`.
First run downloads the image (~40 MB) to `/tmp/chr/`; a run takes about 1 minute.
The SSH forward port is chosen free at run time (localhost only), so concurrent runs are safe.
Env overrides: `CHR_VERSION`, `CHR_SSH_PORT` (pin a port), `CHR_BOOT_TIMEOUT`,
`CHR_APPLY_TIMEOUT`, `CHR_CACHE_DIR`.

## Exit codes

- 0: import ran and no error marker appeared.
- 1: RouterOS reported an error, or the import left no statement trace (refuses to pass silently).
- 2: harness/infra problem, or a script with only comments/blank lines (nothing to verify) (no KVM, download, boot or SSH timeout, upload failure). Not a verdict on the script.

## WARNING: PASS does not mean every command applied

Failures inside `:do { ... } on-error={ ... }` are swallowed by RouterOS and never reach the
output, so a script full of guarded commands passes even if every guarded command is invalid
(verified: `:do { /ip bogus-menu x } on-error={}` exits 0). The harness prints a WARNING when the
script contains `on-error`. Guarded sections (e.g. license and device-mode preflight reads) must be
verified some other way, for example by running the guarded command unguarded in a separate script.

## Error markers checked (case-insensitive, on the router's own diagnostics)

`syntax error`, `expected end of command`, `no such item`, `failure:`, `input does not match`,
`invalid value`, `bad command name`, `cannot`, `script error`, `bad argument`, `unknown parameter`,
`ambiguous`, `not enough permissions`.

`verbose=yes` echoes every source line, comments included. Those echoes (and `#line N` lines) are
removed before matching, so a comment containing "cannot" does not false-fail. Consequence: output
that legitimately prints a marker word (for example `:put "cannot"`) is still flagged.
Markers proven live so far: `input does not match`, `script error`, `no such item`, `syntax error`,
`expected end of command`, `bad command name`. The rest are unexercised.

RouterOS `/import` stops at the first failing line and prints `Script Error: ...`, so only the first
error is reported; fix and re-run. RouterOS prints no success line, so a pass requires the verbose
`#line N` trace to be present and ssh to return 0. A marker that is not in the list above would not
be caught by grep alone, though `/import` aborting normally surfaces it as `Script Error`.

## Limits

- Image is 7.16.2 stable; the fleet runs 7.25beta5. A pass proves the syntax is valid on 7.16+, not
  that a 7.25beta-only feature works.
- A CHR has no wireless hardware: CAPsMAN config can be parsed, but no AP will adopt and radio
  settings cannot be exercised.
- A CHR reports a different license level (free/trial CHR) than a real L009, so license-ceiling
  logic must be covered by unit tests, not this harness.
- The VM has 8 NICs, so `ether1`-`ether8` exist (ether1 is the SSH-forwarded one; the others are
  isolated). `sfp-sfpplus1` and other L009-only ports do not exist and will fail for that reason,
  not because of syntax. Board name is `CHR`, license level `free`.
- Import validates parse and command semantics against the router's current state; it does not
  verify traffic behaviour.
