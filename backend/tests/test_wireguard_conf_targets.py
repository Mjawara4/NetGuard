"""Which file a new WireGuard peer gets written to.

This exists because of a silent production failure: the backend appended peers
to /etc/wireguard/wg0.conf, while the running linuxserver/wireguard container
reads /config/wg_confs/wg0.conf -- a DIFFERENT file it migrates the legacy one
into at startup. Peers written after that migration went to a file nothing
read, so a freshly provisioned router could never complete a handshake, and
nothing anywhere reported an error.

The fix writes to every conf the server might read, so the peer is present
whichever file wins, and survives a restart that re-migrates.
"""
import pytest

from app.services.wireguard import WireGuardService

PUB = "mObFn4U7/OciMQZ8qcA5WYJjAnHuqZI8Cf9ptrYKO2M="
PUB2 = "RqdPl5ceQp6WiZSiLSqODiQOpMab3GSjDQwrMheqHHY="


def _peers(path):
    return path.read_text() if path.exists() else ""


def test_writes_to_wg_confs_when_the_server_reads_it(tmp_path):
    """wg_confs/wg0.conf exists, so that is what the running server reads."""
    active_dir = tmp_path / "wg_confs"
    active_dir.mkdir()
    (active_dir / "wg0.conf").write_text("[Interface]\nPrivateKey = x\n")
    (tmp_path / "wg0.conf").write_text("[Interface]\nPrivateKey = x\n")

    WireGuardService.add_peer_to_conf(PUB, "10.13.13.9", conf_dir=str(tmp_path))

    assert PUB in _peers(active_dir / "wg0.conf"), (
        "peer missing from wg_confs/wg0.conf -- this is the exact production bug: "
        "the file the server actually reads never received the peer"
    )


def test_keeps_the_legacy_conf_in_sync_too(tmp_path):
    """A restart may re-migrate legacy -> wg_confs, so legacy must carry it as well."""
    active_dir = tmp_path / "wg_confs"
    active_dir.mkdir()
    (active_dir / "wg0.conf").write_text("[Interface]\nPrivateKey = x\n")
    (tmp_path / "wg0.conf").write_text("[Interface]\nPrivateKey = x\n")

    WireGuardService.add_peer_to_conf(PUB, "10.13.13.9", conf_dir=str(tmp_path))

    assert PUB in _peers(tmp_path / "wg0.conf"), (
        "peer missing from the legacy conf; a container restart that re-migrates "
        "legacy over wg_confs would silently drop this peer"
    )


def test_falls_back_to_legacy_when_there_is_no_wg_confs(tmp_path):
    """Older images and fresh installs have no wg_confs directory."""
    (tmp_path / "wg0.conf").write_text("[Interface]\nPrivateKey = x\n")

    WireGuardService.add_peer_to_conf(PUB, "10.13.13.9", conf_dir=str(tmp_path))

    assert PUB in _peers(tmp_path / "wg0.conf")
    assert not (tmp_path / "wg_confs").exists(), (
        "must not invent a wg_confs directory; its presence is the signal this "
        "code uses to decide which file the server reads"
    )


def test_is_idempotent_per_file(tmp_path):
    """Re-provisioning the same device must not append the peer twice."""
    active_dir = tmp_path / "wg_confs"
    active_dir.mkdir()
    (active_dir / "wg0.conf").write_text("[Interface]\nPrivateKey = x\n")
    (tmp_path / "wg0.conf").write_text("[Interface]\nPrivateKey = x\n")

    WireGuardService.add_peer_to_conf(PUB, "10.13.13.9", conf_dir=str(tmp_path))
    WireGuardService.add_peer_to_conf(PUB, "10.13.13.9", conf_dir=str(tmp_path))

    for target in (active_dir / "wg0.conf", tmp_path / "wg0.conf"):
        assert _peers(target).count(PUB) == 1, f"{target} got a duplicate peer"


def test_repairs_a_conf_that_is_missing_the_peer(tmp_path):
    """If only one file has the peer, the other still gets it.

    This is the state production is in today: both files happen to match, but
    only because nothing has been provisioned since the last restart.
    """
    active_dir = tmp_path / "wg_confs"
    active_dir.mkdir()
    (active_dir / "wg0.conf").write_text(
        f"[Interface]\nPrivateKey = x\n\n[Peer]\nPublicKey = {PUB}\nAllowedIPs = 10.13.13.9/32\n"
    )
    (tmp_path / "wg0.conf").write_text("[Interface]\nPrivateKey = x\n")

    WireGuardService.add_peer_to_conf(PUB, "10.13.13.9", conf_dir=str(tmp_path))

    assert _peers(tmp_path / "wg0.conf").count(PUB) == 1
    assert _peers(active_dir / "wg0.conf").count(PUB) == 1


def test_adds_a_second_distinct_peer_without_touching_the_first(tmp_path):
    active_dir = tmp_path / "wg_confs"
    active_dir.mkdir()
    (active_dir / "wg0.conf").write_text("[Interface]\nPrivateKey = x\n")
    (tmp_path / "wg0.conf").write_text("[Interface]\nPrivateKey = x\n")

    WireGuardService.add_peer_to_conf(PUB, "10.13.13.9", conf_dir=str(tmp_path))
    WireGuardService.add_peer_to_conf(PUB2, "10.13.13.10", conf_dir=str(tmp_path))

    body = _peers(active_dir / "wg0.conf")
    assert PUB in body and PUB2 in body
    assert "10.13.13.9/32" in body and "10.13.13.10/32" in body


def test_creates_the_conf_when_the_directory_is_empty(tmp_path):
    """First-ever peer on a fresh volume."""
    WireGuardService.add_peer_to_conf(PUB, "10.13.13.9", conf_dir=str(tmp_path))

    assert PUB in _peers(tmp_path / "wg0.conf")


def test_default_conf_dir_is_the_mounted_wireguard_directory():
    """The default must stay the path the compose file bind-mounts."""
    from app.services import wireguard

    assert wireguard.WG_CONF_DIR == "/etc/wireguard"
