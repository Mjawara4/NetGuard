"""Assemble the section builders into one pasteable script."""
from .params import ProvisionParams
from . import sections

# Order is behavioural, not cosmetic:
#   preflight first so an unsuitable router is refused before anything applies;
#   clock before hotspot because voucher durations are enforced by it;
#   addressing before hotspot because the hotspot binds the bridge and pool;
#   wireguard before firewall because the firewall's tunnel-accept rule matches
#     in-interface=wireguard-netguard, which must exist by then;
#   firewall second-to-last because it can cut the installer's own session;
#   summary last so it is what remains on screen.
#
# Keepalive constraint: persistent-keepalive=25s (sections.wireguard) must stay
# below the measured 30s conntrack UDP timeout. That margin keeps every tunnel
# alive through the firewall's WAN drop. Do not tune it up without re-measuring.
SECTION_ORDER = (
    sections.preflight,
    sections.identity_and_clock,
    sections.bridge,
    sections.addressing,
    sections.dns_and_nat,
    sections.hotspot_server,
    sections.voucher_profiles,
    sections.walled_garden,
    sections.api_user,
    sections.wireguard,
    sections.capsman,
    sections.firewall,
    sections.summary,
)


def build_provision_script(p: ProvisionParams) -> str:
    """One brace-enclosed block, so RouterOS treats the script as ONE command.

    A paste into a terminal is otherwise a run of independent commands, and
    `:error` (the preflight refusal) would print and let the rest execute;
    `:error` only aborts everything when it is inside a single command. The
    block also lets `:local` persist across lines, and keeps the router
    executing server-side if the installer's session drops when the ports move.
    """
    out: list[str] = ["{"]
    for fn in SECTION_ORDER:
        out.extend(fn(p))
        out.append("")
    out.append("}")
    out.append("")
    return "\n".join(out)
