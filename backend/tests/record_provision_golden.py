"""Re-record the golden provisioning script.

Run from backend/:  python tests/record_provision_golden.py
Then READ the whole diff of provision_expected.rsc before committing: a golden
file recorded without being read just freezes whatever bug exists.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.provisioning.params import build_params
from app.services.provisioning.script import build_provision_script

FIXED = dict(
    site_slug="serrekunda-counter",
    wg_private_key="cHJpdmF0ZS1rZXktbm90LXJlYWwtcGFkZGluZy0zYiE=", wg_client_ip="10.13.13.7",
    wg_server_public_key="c2VydmVyLS1rZXktbm90LXJlYWwtcGFkZGluZy0zYiE=",
    wg_server_endpoint="74.208.167.166", wg_server_port=51820,
    api_password="Xk7mQp2rTz9wLb4nHc6v", recovery_password="Qw8ZeRtY3uIoP5aSdF1g",
    device_id="11111111-1111-1111-1111-111111111111",
    # The golden covers the fullest script: the one that also installs the portal page.
    portal_mode="netguard",
)
OUT = Path(__file__).parent / "fixtures" / "provision_expected.rsc"

if __name__ == "__main__":
    OUT.write_text(build_provision_script(build_params(**FIXED)))
    print(f"wrote {OUT}")
