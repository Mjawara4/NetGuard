"""Credential generation for provisioned routers."""
import secrets
import string

# Alphanumeric only, deliberately. RouterOS config has several quoting
# contexts and a password containing a quote, `$`, `;`, backslash or a brace
# either fails to parse or creates a user whose password differs from the one
# NetGuard stored -- a router that provisions "successfully" and can never be
# reached. 24 alphanumerics is ~143 bits; the lost symbol classes cost
# nothing that matters.
# This must stay in agreement with the api_password check in params.py
# (`[A-Za-z0-9]+`): widening it here makes every generated password fail there.
#
# I, l, 1, O and 0 are excluded because these passwords get READ OFF A SCREEN.
# A real lockout came of it: the admin password `beNpMv11VRVNsWla0IerlAQY` was
# transcribed from a screenshot as `...WIaOlerIAQY` and as `...Wla0Ier1AQY`,
# neither correct, and six attempts failed before the right string was found by
# trying every combination of the ambiguous positions. The router was reachable
# the whole time and nobody could log in.
#
# The cost is nothing: 57 characters instead of 62 is 141 bits over 24
# characters instead of 143. Length carries the strength, not the alphabet.
AMBIGUOUS_CHARACTERS = "Il1O0"
API_PASSWORD_ALPHABET = "".join(
    c for c in (string.ascii_letters + string.digits)
    if c not in AMBIGUOUS_CHARACTERS
)


def generate_api_password(length: int = 24) -> str:
    return "".join(secrets.choice(API_PASSWORD_ALPHABET) for _ in range(length))
