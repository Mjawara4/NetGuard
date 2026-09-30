#!/usr/bin/env python3
"""Paste a RouterOS script into a CHR over a REAL pty ssh session, like a person at a terminal.

Usage: chr-paste.py <ssh-port> <script-file> <timeout-seconds>

Why this exists: `/import` and a terminal paste are different execution models. `/import`
aborts the file at `:error`; a paste feeds independent lines to the CLI, so a refusal prints and
the rest still runs unless the script is one brace-enclosed block. A harness that only ever
imports cannot see that difference (it hid exactly that defect through three reviews).

A non-tty `ssh < file` is NOT a paste (RouterOS handles each line separately there), so this
drives a pty: answers the first-login licence prompt, the forced password change and RouterOS's
terminal size probe, sends the script with CR line endings in one write, and appends a sentinel
so it knows when the session is finished. Prints the cleaned transcript. Exit 0 = sentinel seen,
3 = timed out waiting for it, 2 = could not log in.
"""
import re
import sys
import time

try:
    import pexpect
except ImportError:
    print("chr-paste: python3-pexpect is required", file=sys.stderr)
    sys.exit(2)

port, path, timeout = sys.argv[1], sys.argv[2], float(sys.argv[3])
ssh = ["ssh", "-tt", "-p", port, "-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null",
       "-o", "LogLevel=ERROR", "-o", "PreferredAuthentications=password,keyboard-interactive",
       "-o", "PubkeyAuthentication=no",
       "-o", "KexAlgorithms=+diffie-hellman-group14-sha1,diffie-hellman-group-exchange-sha256",
       "-o", "HostKeyAlgorithms=+ssh-rsa", "admin+c512w@127.0.0.1"]
child = pexpect.spawn(ssh[0], ssh[1:], encoding="latin-1", timeout=30, dimensions=(50, 512))
transcript = []

prompts = [r"\] > ", r"Y/n\]", r"press Enter \(q", r"new password> ", r"repeat new password> ",
           r"\[y/N\]", "\x1b\\[6n", "assword: "]
reply = {1: "n", 2: "q", 3: "harnesspw1\r", 4: "harnesspw1\r", 5: "n", 6: "\x1b[50;512R", 7: "\r"}
try:
    for _ in range(80):
        i = child.expect(prompts, timeout=20)
        transcript.append(child.before + child.after)
        if i == 0:
            break
        child.send(reply[i])
    else:
        raise pexpect.TIMEOUT("login did not settle")
except (pexpect.TIMEOUT, pexpect.EOF):
    print("chr-paste: could not reach a RouterOS prompt", file=sys.stderr)
    sys.exit(2)

# Only what the paste produces goes in the transcript: the login phase (licence prompt, forced password
# change) would otherwise look like the script prompting.
transcript = []
data = open(path).read().replace("\n", "\r")
child.send(data + "\r:put (\"CHR-PASTE-\" . \"DONE\")\r")
status = 0
try:
    child.expect("CHR-PASTE-DONE", timeout=timeout)  # the typed echo reads "CHR-PASTE-" . "DONE", never this
    transcript.append(child.before)
except pexpect.TIMEOUT:
    transcript.append(child.before or "")
    status = 3
except pexpect.EOF:
    transcript.append(child.before or "")
    status = 3

text = "".join(transcript)
text = re.sub(r"\x1b\[[0-9;?]*[a-zA-Z]", "", text).replace("\r", "")
print(text)
print("CHR-PASTE-END status=%d" % status)
sys.exit(status)
