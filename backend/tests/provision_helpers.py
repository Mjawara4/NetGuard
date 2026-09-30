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
    # A trailing `; <follow-up>` (e.g. the forward rule's move) belongs to the guard, not the add.
    return m.group(1).split("; ")[0]


class _Unwrapped:
    def __getattr__(self, name):
        fn = getattr(_sections, name)
        if not callable(fn):
            return fn
        return lambda p: [unwrap(l) for l in fn(p)]


sections = _Unwrapped()
