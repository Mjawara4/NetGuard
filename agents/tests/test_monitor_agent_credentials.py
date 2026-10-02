"""The agent must use each router's own credential, not a global default.

It used to do:

    pwd = device.get('ssh_password') or SSH_PASSWORD

against GET /inventory/devices, whose response strips ssh_password. That key was
therefore always absent and every router got SSH_PASSWORD, which defaults to
"admin". Against a provisioned router the agent authenticated as `netguard` with
the wrong password, forever: CPU/memory/uptime N/A in the dashboard and a login
failure in the router's log every 40 seconds, while ping and the tunnel were
perfect the whole time.
"""
import importlib
import sys
import types

import pytest


@pytest.fixture
def agent(monkeypatch):
    monkeypatch.setenv("NETGUARD_API_KEY", "test-key")
    monkeypatch.setenv("SSH_USER", "admin")
    monkeypatch.setenv("SSH_PASSWORD", "admin")
    sys.modules.pop("monitor_agent", None)
    return importlib.import_module("monitor_agent")


def test_credentials_are_keyed_by_device_id(agent):
    rows = [
        {"id": "a", "ip_address": "10.13.13.3", "ssh_username": "netguard",
         "ssh_password": "RealPw23RealPw23RealPw23", "ssh_port": 8728},
        {"id": "b", "ip_address": "10.13.13.4", "ssh_username": "netguard",
         "ssh_password": "OtherPw23OtherPw23Other", "ssh_port": 8728},
    ]
    index = agent.index_credentials(rows)
    assert index["a"]["ssh_password"] == "RealPw23RealPw23RealPw23"
    assert index["b"]["ssh_password"] == "OtherPw23OtherPw23Other"


def test_the_stored_credential_wins_over_the_global_default(agent):
    index = agent.index_credentials([
        {"id": "a", "ip_address": "10.13.13.3", "ssh_username": "netguard",
         "ssh_password": "RealPw23RealPw23RealPw23", "ssh_port": 8728},
    ])
    user, pwd, port = agent.credentials_for({"id": "a", "ssh_username": "netguard"}, index)
    assert (user, pwd) == ("netguard", "RealPw23RealPw23RealPw23"), (
        "the agent sent the global default instead of the router's own password"
    )
    assert port == 8728


def test_falls_back_only_when_there_is_no_stored_credential(agent):
    user, pwd, _ = agent.credentials_for({"id": "zz", "ssh_username": None}, {})
    assert (user, pwd) == ("admin", "admin"), "legacy devices must still be polled"


def test_a_device_missing_from_the_index_does_not_borrow_another_password(agent):
    index = agent.index_credentials([
        {"id": "a", "ip_address": "10.13.13.3", "ssh_username": "netguard",
         "ssh_password": "RealPw23RealPw23RealPw23", "ssh_port": 8728},
    ])
    user, pwd, _ = agent.credentials_for({"id": "b", "ssh_username": "netguard"}, index)
    assert pwd != "RealPw23RealPw23RealPw23", "credentials leaked across devices"


def test_port_22_is_still_corrected_to_the_api_port(agent):
    """A device row saying 22 means SSH; the API lives on 8728."""
    index = agent.index_credentials([
        {"id": "a", "ip_address": "10.13.13.3", "ssh_username": "netguard",
         "ssh_password": "RealPw23RealPw23RealPw23", "ssh_port": 22},
    ])
    _, _, port = agent.credentials_for({"id": "a", "ssh_username": "netguard"}, index)
    assert port == 8728
