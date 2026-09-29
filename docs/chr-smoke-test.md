# CHR smoke test

`scripts/chr-smoke-test.sh <script.rsc>` boots a throwaway MikroTik CHR (RouterOS 7.16.2) under
QEMU/KVM, uploads the script, runs `/import file-name=smoke.rsc verbose=yes`, prints the router's
own output, and exits non-zero on any RouterOS error. The VM and temp dir are removed on exit
(`trap`), including on failure or Ctrl-C.

## Run

    scripts/chr-smoke-test.sh path/to/script.rsc; echo $?

Needs `qemu-system-x86`, `qemu-utils`, `sshpass`, `unzip`, `curl`, and `/dev/kvm`.
First run downloads the image (~40 MB) to `/tmp/chr/`; a run takes about 1 minute.
Env overrides: `CHR_VERSION`, `CHR_SSH_PORT` (default 2222, localhost only), `CHR_BOOT_TIMEOUT`,
`CHR_APPLY_TIMEOUT`, `CHR_CACHE_DIR`.

## Exit codes

- 0: import ran and no error marker appeared.
- 1: RouterOS reported an error, or the import left no statement trace (refuses to pass silently).
- 2: harness/infra problem (no KVM, download, boot or SSH timeout, upload failure). Not a verdict on the script.

## Error markers checked (case-insensitive, on the router's output)

`syntax error`, `expected end of command`, `no such item`, `failure:`, `input does not match`,
`invalid value`, `bad command name`, `cannot`, `script error`, `bad argument`, `unknown parameter`,
`ambiguous`, `not enough permissions`.

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
- Applying to a factory-default CHR: interface names are `ether1` only. Scripts referencing L009
  ports (`ether2..`, `sfp-sfpplus1`) will fail here for that reason, not because of syntax.
- Import validates parse and command semantics against the router's current state; it does not
  verify traffic behaviour.
