"""Test helper: read the section builders as if each object were a plain command.

Every object the script creates is guarded (`:if ([:len [<menu> find where ..]] = 0)
do={ <menu> add ... }`) so a stock router or a re-run does not collide. Older
tests assert on the command itself, so this proxy strips that one guard shape
and leaves everything else untouched. The guards are tested on the raw output
in test_provision_idempotent.py.
"""
import re

from app.services.provisioning import sections as _sections

_GUARD = re.compile(r":if \(\[:len \[[^\]]* find where [^\]]*\]\] = 0\) do=\{ (.*) \}")


def unwrap(line: str) -> str:
    m = _GUARD.fullmatch(line)
    if not m:
        return line
    inner = m.group(1)
    # "Above the router's own rule" adds: `:local t [find ...]; :if (...) do={ ADD place-before=[:pick $t 0] }
    # else={ ADD <fallback> }`. The plain shape tests read the fallback add (a blank router's).
    e = re.search(r" else=\{ (/.*?) \} *$", inner) if inner.startswith(":local t ") else None
    return e.group(1) if e else inner


class _Unwrapped:
    def __getattr__(self, name):
        fn = getattr(_sections, name)
        if not callable(fn):
            return fn
        return lambda p: [unwrap(l) for l in fn(p)]


sections = _Unwrapped()
