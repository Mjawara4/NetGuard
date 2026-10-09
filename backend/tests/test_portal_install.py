import pytest

from app.services import portal_install as pi

DIR = "test"
LOGIN, BACKUP = "test/login.html", "test/login.netguard-backup.html"
CUSTOM = "<html><body><h1>Kumbija WiFi</h1></body></html>"
NETGUARD = "<!doctype html><!-- NETGUARD-PORTAL --><html><body>Buy WiFi</body></html>"
LEGACY_NETGUARD = "<html><body><p>Choose a plan and pay securely with Modem Pay.</p></body></html>"
BUTTON = "<!-- NETGUARD-BUY-START --><a>Buy WiFi</a><!-- NETGUARD-BUY-END -->"


class Files:
    """A router's file store. `unreadable` models pages too big to read back."""

    def __init__(self, files=None, unreadable=(), corrupt_writes=False):
        self.files = dict(files or {})
        self.unreadable = set(unreadable)
        self.corrupt_writes = corrupt_writes
        self.writes = []

    def exists(self, name):
        return name in self.files

    def read(self, name):
        return None if name in self.unreadable else self.files.get(name)

    def write(self, name, contents):
        self.writes.append(name)
        self.files[name] = contents[:10] if self.corrupt_writes else contents


@pytest.mark.parametrize("html,expected", [
    (NETGUARD, True), (LEGACY_NETGUARD, True), (CUSTOM, False),
    (CUSTOM.replace("</body>", BUTTON + "</body>"), False), ("", False), (None, False),
])
def test_only_netguards_own_page_is_recognised_as_netguards(html, expected):
    assert pi.is_netguard_page(html) is expected


def test_describe_reports_what_the_router_is_serving():
    assert pi.describe(Files({LOGIN: CUSTOM}), DIR)["login_page"] == "custom"
    assert pi.describe(Files({LOGIN: NETGUARD}), DIR)["login_page"] == "netguard"
    assert pi.describe(Files({}), DIR)["login_page"] == "missing"
    assert pi.describe(Files({LOGIN: CUSTOM}, unreadable={LOGIN}), DIR)["login_page"] == "unreadable"


def test_describe_does_not_count_a_copy_of_netguards_page_as_the_users_backup():
    assert pi.describe(Files({LOGIN: NETGUARD, BACKUP: NETGUARD}), DIR)["has_backup"] is False
    assert pi.describe(Files({LOGIN: NETGUARD, BACKUP: CUSTOM}), DIR)["has_backup"] is True


# --- adding the Buy button to the user's own page -------------------------

def test_install_custom_backs_up_the_original_then_adds_the_button():
    files = Files({LOGIN: CUSTOM})
    pi.install_custom(files, DIR, BUTTON)
    assert files.files[BACKUP] == CUSTOM
    assert files.files[LOGIN] == CUSTOM.replace("</body>", BUTTON + "</body>")


def test_install_custom_twice_keeps_one_button_and_the_first_backup():
    files = Files({LOGIN: CUSTOM})
    pi.install_custom(files, DIR, BUTTON)
    pi.install_custom(files, DIR, BUTTON.replace("Buy WiFi", "Buy now"))
    assert files.files[BACKUP] == CUSTOM
    assert files.files[LOGIN].count("NETGUARD-BUY-START") == 1
    assert "Buy now" in files.files[LOGIN]


def test_install_custom_never_backs_up_a_page_that_already_has_our_button():
    files = Files({LOGIN: CUSTOM.replace("</body>", BUTTON + "</body>")})
    pi.install_custom(files, DIR, BUTTON)
    assert files.files[BACKUP] == CUSTOM


def test_install_custom_replaces_a_stale_backup_of_netguards_page():
    files = Files({LOGIN: CUSTOM, BACKUP: NETGUARD})
    pi.install_custom(files, DIR, BUTTON)
    assert files.files[BACKUP] == CUSTOM


def test_install_custom_brings_the_users_page_back_when_netguards_is_showing():
    files = Files({LOGIN: NETGUARD, BACKUP: CUSTOM})
    pi.install_custom(files, DIR, BUTTON)
    assert files.files[LOGIN] == CUSTOM.replace("</body>", BUTTON + "</body>")
    assert files.files[BACKUP] == CUSTOM


def test_install_custom_refuses_when_there_is_no_user_page_to_keep():
    files = Files({LOGIN: NETGUARD, BACKUP: NETGUARD})
    with pytest.raises(pi.PortalError):
        pi.install_custom(files, DIR, BUTTON)
    assert files.writes == []


def test_install_custom_changes_nothing_when_the_page_cannot_be_read():
    files = Files({LOGIN: CUSTOM}, unreadable={LOGIN})
    with pytest.raises(pi.PortalError):
        pi.install_custom(files, DIR, BUTTON)
    assert files.writes == []


def test_install_custom_leaves_login_alone_when_the_backup_did_not_survive_the_write():
    files = Files({LOGIN: CUSTOM}, corrupt_writes=True)
    with pytest.raises(pi.PortalError):
        pi.install_custom(files, DIR, BUTTON)
    assert files.files[LOGIN] == CUSTOM


# --- the user explicitly choosing NetGuard's portal ------------------------

def test_install_netguard_keeps_a_copy_of_the_users_page_first():
    files = Files({LOGIN: CUSTOM.replace("</body>", BUTTON + "</body>")})
    pi.install_netguard(files, DIR, NETGUARD)
    assert files.files[BACKUP] == CUSTOM
    assert files.files[LOGIN] == NETGUARD


def test_install_netguard_does_not_overwrite_an_existing_copy_of_the_users_page():
    files = Files({LOGIN: NETGUARD, BACKUP: CUSTOM})
    pi.install_netguard(files, DIR, NETGUARD + " v2")
    assert files.files[BACKUP] == CUSTOM
    assert files.files[LOGIN] == NETGUARD + " v2"


def test_install_netguard_refuses_to_replace_a_page_it_could_not_back_up():
    files = Files({LOGIN: CUSTOM}, unreadable={LOGIN})
    with pytest.raises(pi.PortalError):
        pi.install_netguard(files, DIR, NETGUARD)
    assert files.writes == []


def test_install_netguard_on_a_router_with_no_login_page_just_installs():
    files = Files({})
    pi.install_netguard(files, DIR, NETGUARD)
    assert files.files == {LOGIN: NETGUARD}


# --- going back ------------------------------------------------------------

def test_restore_puts_the_users_page_back():
    files = Files({LOGIN: NETGUARD, BACKUP: CUSTOM})
    pi.restore(files, DIR)
    assert files.files[LOGIN] == CUSTOM


def test_restore_refuses_a_backup_that_is_only_netguards_page():
    files = Files({LOGIN: NETGUARD, BACKUP: NETGUARD})
    with pytest.raises(pi.PortalError):
        pi.restore(files, DIR)
    assert files.writes == []


# --- which folders hold a portal, and whether the owner's choice is honoured ---

def test_portal_folders_are_the_folders_holding_a_login_page():
    names = ["hotspot", "hotspot/login.html", "hotspot/xml/login.html", "test/login.html",
             "test/login.netguard-backup.html", "skins/status.html", "flash/hotspot/login.html",
             "log.0.txt", "login.html"]
    assert pi.portal_folders(names) == ["flash/hotspot", "hotspot", "test"]


def test_portal_folders_skip_names_the_router_script_could_not_quote_safely():
    assert pi.portal_folders(['bad"dir/login.html', "a b/login.html", "../x/login.html", "ok/login.html"]) == ["ok"]


def test_no_attention_needed_when_the_router_serves_what_the_owner_chose():
    status = {"directory": "test", "login_page": "custom"}
    assert pi.attention("custom", "test", status) is None
    assert pi.attention("custom", "", status) is None
    assert pi.attention("netguard", "", {"directory": "hotspot", "login_page": "netguard"}) is None


def test_attention_when_the_router_left_the_folder_the_owner_chose():
    assert pi.attention("custom", "test", {"directory": "hotspot", "login_page": "netguard"}) == "wrong_folder"
    assert pi.attention("custom", "test", {"directory": "hotspot", "login_page": "custom"}) == "wrong_folder"


def test_attention_when_netguards_page_shows_on_a_router_set_to_the_owners_portal():
    assert pi.attention("custom", "", {"directory": "hotspot", "login_page": "netguard"}) == "netguard_page"


def test_the_portal_hotspot_is_the_one_the_owner_named_else_the_first_enabled():
    a, b, c = ({"name": "a", "disabled": True}, {"name": "b", "disabled": False}, {"name": "c", "disabled": False})
    assert pi.pick_hotspot([a, b, c]) is b
    assert pi.pick_hotspot([a, b, c], "c") is c
    assert pi.pick_hotspot([a, b, c], "gone") is b
    assert pi.pick_hotspot([a]) is a
    assert pi.pick_hotspot([]) is None


ME, OTHER = "9aa95e41-b63b-42f1-a896-a239ceeac95b", "2563d54e-924b-49ee-8b32-ca0c79a1c75f"


def _page_for(router):
    button = ('<!-- NETGUARD-BUY-START --><a href="https://app.netguard.fun/buy?router=' + router
              + '&mac=$(mac)">Buy WiFi</a><script>var dst="https://app.netguard.fun/buy?router=' + router
              + '&connected=1"</script><!-- NETGUARD-BUY-END -->')
    return CUSTOM.replace("</body>", button + "</body>")


def test_describe_says_whose_buy_button_the_page_carries():
    assert pi.describe(Files({LOGIN: CUSTOM}), DIR, ME)["buy_button"] == "none"
    assert pi.describe(Files({LOGIN: _page_for(ME)}), DIR, ME)["buy_button"] == "this"
    assert pi.describe(Files({LOGIN: _page_for(OTHER)}), DIR, ME)["buy_button"] == "other"
    assert pi.describe(Files({LOGIN: NETGUARD}), DIR, ME)["buy_button"] == "none"
    assert pi.describe(Files({}), DIR, ME)["buy_button"] == "none"


def test_a_link_to_another_router_outside_our_button_is_the_owners_business():
    page = CUSTOM.replace("</body>", '<a href="https://app.netguard.fun/buy?router=' + OTHER + '">x</a></body>')
    assert pi.describe(Files({LOGIN: page}), DIR, ME)["buy_button"] == "none"


def test_attention_when_the_buy_button_belongs_to_another_router():
    status = {"directory": "test", "login_page": "custom", "buy_button": "other"}
    assert pi.attention("custom", "test", status) == "other_router_button"
    assert pi.attention("custom", "test", {**status, "buy_button": "this"}) is None
