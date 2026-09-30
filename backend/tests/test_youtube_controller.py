from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from backend.services.youtube_controller import (
    ControllerError,
    END_MARKER,
    PermissionDeniedError,
    START_MARKER,
    YOUTUBE_DOMAINS,
    YouTubeController,
)


def controller_for(tmp_path: Path, contents: bytes = b"127.0.0.1 localhost\r\n") -> YouTubeController:
    hosts = tmp_path / "hosts"
    hosts.write_bytes(contents)
    return YouTubeController(hosts)


def test_block_adds_all_domains(tmp_path):
    controller = controller_for(tmp_path)
    assert not controller.is_youtube_blocked()
    controller.block_youtube()
    contents = controller.hosts_path.read_bytes()
    assert contents.startswith(b"127.0.0.1 localhost\r\n")
    for domain in YOUTUBE_DOMAINS:
        assert b"127.0.0.1 " + domain.encode() + b"\r\n" in contents
    assert controller.is_youtube_blocked()


def test_block_is_idempotent(tmp_path):
    controller = controller_for(tmp_path)
    controller.block_youtube()
    first = controller.hosts_path.read_bytes()
    controller.block_youtube()
    assert controller.hosts_path.read_bytes() == first
    assert first.count(START_MARKER) == 1
    assert first.count(END_MARKER) == 1


@pytest.mark.parametrize("original", [
    b"",
    b"127.0.0.1 localhost",
    b"127.0.0.1 localhost\n",
    b"# Comment with non-UTF8 byte: \xff\r\n192.168.1.20 work.internal\r\n",
    b"\xef\xbb\xbf# UTF-8 BOM\r\n127.0.0.1 localhost",
    b"127.0.0.1 youtube.com\r\n127.0.0.1 localhost\r\n",
])
def test_round_trip_preserves_every_unrelated_byte(tmp_path, original):
    controller = controller_for(tmp_path, original)
    controller.block_youtube()
    controller.block_youtube()
    controller.unblock_youtube(20)
    assert controller.hosts_path.read_bytes() == original
    assert not controller.is_youtube_blocked()
    controller.unblock_youtube(20)
    assert controller.hosts_path.read_bytes() == original


def test_unblock_preserves_entries_before_and_after_section(tmp_path):
    before = b"# existing\r\n127.0.0.1 youtube.com\r\n"
    after = b"192.168.1.20 private.internal\r\n# final comment"
    managed = START_MARKER + b"\r\n127.0.0.1 youtube.com\r\n" + END_MARKER + b"\r\n"
    controller = controller_for(tmp_path, before + managed + after)
    controller.block_youtube()
    controller.unblock_youtube(5)
    assert controller.hosts_path.read_bytes() == before + after


@pytest.mark.parametrize("malformed", [
    START_MARKER + b"\n127.0.0.1 youtube.com\n",
    END_MARKER + b"\n",
    END_MARKER + b"\n" + START_MARKER + b"\n",
    START_MARKER + b"\n" + START_MARKER + b"\n" + END_MARKER + b"\n",
    START_MARKER + b"\n" + END_MARKER + b"\n" + END_MARKER + b"\n",
    START_MARKER + b" malformed\n" + END_MARKER + b"\n",
    b"# === YOUTUBE_GATEKEEPER_START ==\n# === YOUTUBE_GATEKEEPER_END ==\n",
])
def test_malformed_sections_are_never_changed(tmp_path, malformed):
    controller = controller_for(tmp_path, malformed)
    for operation in (controller.is_youtube_blocked, controller.block_youtube, lambda: controller.unblock_youtube(10)):
        with pytest.raises(ControllerError):
            operation()
        assert controller.hosts_path.read_bytes() == malformed


def test_partial_section_does_not_report_blocked(tmp_path):
    controller = controller_for(tmp_path, START_MARKER + b"\n127.0.0.1 youtube.com\n" + END_MARKER)
    assert not controller.is_youtube_blocked()
    controller.block_youtube()
    assert controller.is_youtube_blocked()
    assert controller.hosts_path.read_bytes().endswith(END_MARKER)


@pytest.mark.parametrize("duration", [None, 0, -5, True, 1.5, "20", 10**100])
def test_unlock_requires_bounded_integer_time(tmp_path, duration):
    controller = controller_for(tmp_path)
    controller.block_youtube()
    before = controller.hosts_path.read_bytes()
    with pytest.raises(ControllerError):
        controller.unblock_youtube(duration)
    assert controller.hosts_path.read_bytes() == before
    assert controller.get_current_access_expiry() is None


def test_expiry_is_aware_and_cleared_on_block(tmp_path):
    controller = controller_for(tmp_path)
    before = datetime.now(timezone.utc)
    controller.unblock_youtube(20)
    assert before + timedelta(minutes=20) <= controller.get_current_access_expiry() <= datetime.now(timezone.utc) + timedelta(minutes=20)
    controller.block_youtube()
    assert controller.get_current_access_expiry() is None


def test_permission_error_is_clear(tmp_path, monkeypatch):
    controller = controller_for(tmp_path)

    def deny(*args, **kwargs):
        raise PermissionError("Access denied")

    monkeypatch.setattr(Path, "open", deny)
    for operation in (controller.is_youtube_blocked, controller.block_youtube, lambda: controller.unblock_youtube(10)):
        with pytest.raises(PermissionDeniedError, match="Permission denied"):
            operation()


def test_missing_hosts_is_not_silently_created(tmp_path):
    controller = YouTubeController(tmp_path / "missing")
    with pytest.raises(ControllerError, match="does not exist"):
        controller.block_youtube()
    assert not controller.hosts_path.exists()


def test_preview_creates_only_named_file_and_never_flushes_dns(tmp_path, monkeypatch):
    def unexpected(*args, **kwargs):
        raise AssertionError("A temporary hosts file must not flush system DNS")

    monkeypatch.setattr("backend.services.youtube_controller.subprocess.run", unexpected)
    controller = YouTubeController(tmp_path / "preview" / "hosts", dry_run=True)
    controller.block_youtube()
    assert controller.is_youtube_blocked()
    controller.unblock_youtube(5)
    assert not controller.is_youtube_blocked()


def test_utf16_rejected_without_modification(tmp_path):
    original = "127.0.0.1 localhost".encode("utf-16")
    controller = controller_for(tmp_path, original)
    with pytest.raises(ControllerError, match="UTF-16"):
        controller.block_youtube()
    assert controller.hosts_path.read_bytes() == original


def test_preview_refuses_a_system_hosts_target(tmp_path, monkeypatch):
    hosts = tmp_path / "system-hosts"
    hosts.write_bytes(b"# original\r\n")
    monkeypatch.setattr("backend.services.youtube_controller._system_hosts_path", lambda: hosts)
    with pytest.raises(ControllerError, match="cannot modify"):
        YouTubeController(hosts, dry_run=True)
    assert hosts.read_bytes() == b"# original\r\n"


def test_failed_write_is_rolled_back(tmp_path, monkeypatch):
    controller = controller_for(tmp_path)
    original = controller.hosts_path.read_bytes()
    calls = []

    def fail_first_sync(descriptor):
        calls.append(descriptor)
        if len(calls) == 1:
            raise OSError("Simulated sync failure")

    monkeypatch.setattr("backend.services.youtube_controller.os.fsync", fail_first_sync)
    with pytest.raises(ControllerError, match="Simulated sync failure"):
        controller.block_youtube()
    assert len(calls) == 2
    assert controller.hosts_path.read_bytes() == original


def test_idempotent_operations_do_not_repeat_dns_flush(tmp_path, monkeypatch):
    controller = controller_for(tmp_path)
    calls = []
    monkeypatch.setattr(controller, "_flush_dns", lambda: calls.append("flush"))
    controller.block_youtube()
    controller.block_youtube()
    assert len(calls) == 1
    controller.unblock_youtube(5)
    controller.unblock_youtube(5)
    assert len(calls) == 2
