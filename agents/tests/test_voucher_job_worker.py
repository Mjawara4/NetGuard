import json

import fakeredis
import pytest

import voucher_job_worker as w


@pytest.fixture
def fake_redis(monkeypatch):
    fake = fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(w, "_client", lambda: fake)
    return fake


# ---------------------------------------------------------------------------
# Queue claiming
# ---------------------------------------------------------------------------

def test_claims_a_job_from_the_queue(fake_redis):
    job = {"batch_id": "b1", "device_id": "d1", "qty": 2, "prefix": "T",
           "profile": "default", "time_limit": None, "data_limit": None,
           "comment": "Batch-T"}
    fake_redis.lpush(w.QUEUE_KEY, json.dumps(job))
    claimed = w.claim_job(timeout=1)
    assert claimed == job


def test_claim_returns_none_when_queue_empty(fake_redis):
    assert w.claim_job(timeout=1) is None


def test_claim_returns_none_on_redis_error(monkeypatch):
    class Boom:
        def brpop(self, *a, **k):
            raise RuntimeError("redis down")

    monkeypatch.setattr(w, "_client", lambda: Boom())
    # The worker must survive a Redis outage and keep retrying, not crash.
    assert w.claim_job(timeout=1) is None


def test_claim_drops_malformed_payload_without_raising(fake_redis):
    fake_redis.lpush(w.QUEUE_KEY, "not json")
    assert w.claim_job(timeout=1) is None


# ---------------------------------------------------------------------------
# generate_usernames -- the brief's own convenience wrapper contract
# ---------------------------------------------------------------------------

def test_generate_usernames_are_unique_and_prefixed():
    names = w.generate_usernames("ABC", 50)
    assert len(names) == 50
    assert len(set(names)) == 50
    assert all(n.startswith("ABC") for n in names)


# ---------------------------------------------------------------------------
# Naming-format equivalence with backend/app/services/voucher_jobs.py
#
# These mirror backend/tests/test_voucher_jobs.py's own naming tests
# assertion-for-assertion. A reviewer diffing the two test files (and the two
# generate_candidate implementations) should see the same shapes asserted on
# both sides of the agents/backend split, for all three naming modes.
# ---------------------------------------------------------------------------

def test_max_collision_attempts_matches_original_qty_times_three():
    assert w.max_collision_attempts(10) == 30
    assert w.max_collision_attempts(1) == 3


def test_generate_candidate_non_random_uses_prefix_and_suffix():
    username, password = w.generate_candidate("PROMO", length=4, random_mode=False)
    assert username.startswith("PROMO")
    assert len(username) == len("PROMO") + 4
    assert username[len("PROMO"):].isdigit()
    assert password.isdigit()
    assert len(password) == 4


def test_generate_candidate_random_numeric_username_equals_password():
    username, password = w.generate_candidate("", length=6, random_mode=True, fmt="numeric")
    assert username.isdigit()
    assert len(username) == 6
    assert password == username


def test_generate_candidate_random_alphanumeric_splits_length():
    username, password = w.generate_candidate("", length=8, random_mode=True, fmt="alphanumeric")
    assert password == username
    assert len(username) == 8
    letters = username[:4]
    digits = username[4:]
    assert letters.isalpha() and letters.islower()
    assert digits.isdigit()


# ---------------------------------------------------------------------------
# Device lookup -- mirrors the fetch-full-list-then-filter pattern already
# used by monitor_agent.py / fix_agent.py / diagnoser_agent.py / wg_agent.py.
# ---------------------------------------------------------------------------

def test_fetch_device_looks_up_by_id_from_full_device_list(monkeypatch):
    devices = [
        {"id": "d1", "ip_address": "10.13.13.1"},
        {"id": "d2", "ip_address": "10.13.13.2"},
    ]

    class FakeResp:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return devices

    captured = {}

    def fake_get(url, headers=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        return FakeResp()

    monkeypatch.setattr(w.requests, "get", fake_get)

    device = w.fetch_device("d2")
    assert device == {"id": "d2", "ip_address": "10.13.13.2"}
    assert captured["url"] == f"{w.API_URL}/inventory/devices"
    assert captured["headers"] == w.get_headers()


def test_fetch_device_returns_none_when_not_found(monkeypatch):
    class FakeResp:
        def raise_for_status(self):
            pass

        def json(self):
            return [{"id": "other"}]

    monkeypatch.setattr(w.requests, "get", lambda *a, **k: FakeResp())
    assert w.fetch_device("missing") is None


def test_fetch_device_returns_none_on_request_error(monkeypatch):
    import requests

    def fake_get(*a, **k):
        raise requests.exceptions.RequestException("boom")

    monkeypatch.setattr(w.requests, "get", fake_get)
    assert w.fetch_device("d1") is None


# ---------------------------------------------------------------------------
# Progress reporting -- HTTP mocked; the real endpoint lands in Task 4.
# ---------------------------------------------------------------------------

def test_report_progress_posts_expected_payload(monkeypatch):
    captured = {}

    class FakeResp:
        def raise_for_status(self):
            pass

    def fake_post(url, json=None, headers=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers
        return FakeResp()

    monkeypatch.setattr(w.requests, "post", fake_post)

    ok = w.report_progress("batch-1", [{"username": "u1", "password": "p1"}], "running")
    assert ok is True
    assert captured["url"] == f"{w.API_URL}/hotspot/jobs/batch-1/progress"
    assert captured["json"] == {"vouchers": [{"username": "u1", "password": "p1"}], "status": "running"}
    assert captured["headers"] == w.get_headers()


def test_report_progress_returns_false_on_request_error(monkeypatch):
    import requests

    def fake_post(*a, **k):
        raise requests.exceptions.RequestException("404 not found")

    monkeypatch.setattr(w.requests, "post", fake_post)
    assert w.report_progress("batch-1", [], "complete") is False


# ---------------------------------------------------------------------------
# process_job -- the router and the backend API are both mocked, per the
# brief: end-to-end verification against a real progress endpoint waits on
# Task 4.
# ---------------------------------------------------------------------------

class FakeResource:
    """Stands in for api.get_resource('/ip/hotspot/user')."""

    def __init__(self, fail_names=None):
        self.calls = []
        self.fail_names = fail_names or set()

    def add(self, **params):
        self.calls.append(params)
        if params["name"] in self.fail_names:
            raise RuntimeError("already exists")


class FakeApi:
    def __init__(self, resource):
        self._resource = resource

    def get_resource(self, path):
        return self._resource


class FakePool:
    def __init__(self, ip, username=None, password=None, port=None, plaintext_login=None, use_ssl=None, resource=None):
        self.connect_args = {
            "ip": ip, "username": username, "password": password, "port": port,
        }
        self._resource = resource
        self.disconnected = False

    def get_api(self):
        return FakeApi(self._resource)

    def disconnect(self):
        self.disconnected = True


def _job(**overrides):
    job = {
        "batch_id": "batch-1",
        "device_id": "d1",
        "qty": 12,
        "prefix": "T",
        "profile": "default",
        "time_limit": "1h",
        "data_limit": 1000,
        "comment": "Batch-T",
        "length": None,
        "random_mode": False,
        "format": "alphanumeric",
    }
    job.update(overrides)
    return job


@pytest.fixture
def fake_device(monkeypatch):
    device = {
        "id": "d1",
        "ip_address": "10.13.13.5",
        "ssh_username": "admin",
        "ssh_password": "secret",
        "ssh_port": 8728,
    }
    monkeypatch.setattr(w, "fetch_device", lambda device_id: device)
    return device


def _install_fake_router(monkeypatch, resource):
    def fake_pool_factory(ip, **kwargs):
        return FakePool(ip, resource=resource, **kwargs)

    monkeypatch.setattr(w.routeros_api, "RouterOsApiPool", fake_pool_factory)


def _install_progress_capture(monkeypatch):
    calls = []

    def fake_report_progress(batch_id, vouchers, status):
        calls.append((batch_id, list(vouchers), status))
        return True

    monkeypatch.setattr(w, "report_progress", fake_report_progress)
    return calls


def test_process_job_happy_path_batches_progress_and_completes(monkeypatch, fake_device):
    resource = FakeResource()
    _install_fake_router(monkeypatch, resource)
    calls = _install_progress_capture(monkeypatch)

    job = _job(qty=12)
    w.process_job(job)

    # running (empty, at start), running (10 batched), complete (final 2)
    assert calls[0] == ("batch-1", [], "running")
    assert calls[1][2] == "running"
    assert len(calls[1][1]) == 10
    assert calls[2][2] == "complete"
    assert len(calls[2][1]) == 2

    all_vouchers = calls[1][1] + calls[2][1]
    assert len(all_vouchers) == 12
    assert len(resource.calls) == 12
    # every param the collision-retry contract requires, including the
    # 4-digit password, time_limit and data_limit translation
    for call in resource.calls:
        assert call["name"].startswith("T")
        assert len(call["password"]) == 4
        assert call["profile"] == "default"
        assert call["comment"] == "Batch-T"
        assert call["limit-uptime"] == "1h"
        assert call["limit-bytes-total"] == 1000


def test_process_job_retries_past_collisions_within_qty_times_three_budget(monkeypatch, fake_device):
    # Force the very first attempted name to collide; the loop must retry
    # with a fresh candidate rather than aborting or double-counting it.
    calls_seen = {}

    class CollideOnceResource(FakeResource):
        def add(self, **params):
            if not calls_seen.get("collided"):
                calls_seen["collided"] = True
                self.calls.append(params)
                raise RuntimeError("user already exists")
            return super().add(**params)

    resource = CollideOnceResource()
    _install_fake_router(monkeypatch, resource)
    calls = _install_progress_capture(monkeypatch)

    job = _job(qty=3)
    w.process_job(job)

    assert len(resource.calls) == 4  # 1 collision + 3 successful creates
    assert calls[-1][2] == "complete"
    assert len(calls[-1][1]) == 3


def test_process_job_marks_failed_with_partial_vouchers_when_router_connect_fails(monkeypatch, fake_device):
    def blow_up(ip, **kwargs):
        raise ConnectionError("no route to host")

    monkeypatch.setattr(w.routeros_api, "RouterOsApiPool", blow_up)
    calls = _install_progress_capture(monkeypatch)

    job = _job(qty=5)
    w.process_job(job)

    assert calls[0] == ("batch-1", [], "running")
    assert calls[-1][2] == "failed"
    assert calls[-1][1] == []  # nothing was created before the connection failed


def test_process_job_marks_failed_when_device_not_found(monkeypatch):
    monkeypatch.setattr(w, "fetch_device", lambda device_id: None)
    calls = _install_progress_capture(monkeypatch)

    job = _job(qty=5)
    w.process_job(job)

    assert calls[-1][2] == "failed"
    assert calls[-1][1] == []


def test_process_job_pending_kept_when_progress_report_fails_then_flushed(monkeypatch, fake_device):
    resource = FakeResource()
    _install_fake_router(monkeypatch, resource)

    calls = []

    def flaky_report_progress(batch_id, vouchers, status):
        # Fail every intermediate ("running") report, succeed on "complete".
        calls.append((batch_id, list(vouchers), status))
        return status == "complete"

    monkeypatch.setattr(w, "report_progress", flaky_report_progress)

    job = _job(qty=12)
    w.process_job(job)

    # The final "complete" call must carry every voucher that was never
    # successfully flushed -- none may be silently dropped just because an
    # earlier intermediate report failed.
    final_batch_id, final_vouchers, final_status = calls[-1]
    assert final_status == "complete"
    assert len(final_vouchers) == 12
