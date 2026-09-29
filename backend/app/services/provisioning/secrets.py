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
API_PASSWORD_ALPHABET = string.ascii_letters + string.digits


def generate_api_password(length: int = 24) -> str:
    return "".join(secrets.choice(API_PASSWORD_ALPHABET) for _ in range(length))
