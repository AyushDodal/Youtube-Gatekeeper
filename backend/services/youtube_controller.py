"""Manage only YouTube Gatekeeper's section of a Windows hosts file.

An explicit ``hosts_path`` is intended for tests and the visible preview mode.
The session manager owns durable expiration and re-blocking; this controller
does not create a timer or background process of its own.
"""

from __future__ import annotations

import ctypes
import logging
import os
from pathlib import Path
import subprocess
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import BinaryIO, Iterator


logger = logging.getLogger(__name__)

START_MARKER = b"# === YOUTUBE_GATEKEEPER_START ==="
END_MARKER = b"# === YOUTUBE_GATEKEEPER_END ==="
# This comment records ownership of the newline we add to a file whose last
# original line was unterminated. It lets unblock restore the original bytes.
JOINED_MARKER = b"# YOUTUBE_GATEKEEPER_ADDED_SEPARATOR_NEWLINE"
YOUTUBE_DOMAINS = (
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "youtu.be",
    "www.youtu.be",
)


class ControllerError(RuntimeError):
    """The hosts file could not be read or safely changed."""


class PermissionDeniedError(ControllerError):
    """The process does not have permission to access the hosts file."""


def _system_hosts_path() -> Path:
    return Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32/drivers/etc/hosts"


class YouTubeController:
    def __init__(self, hosts_path: Path | None = None, *, dry_run: bool = False) -> None:
        self.dry_run = dry_run
        if hosts_path is None:
            if dry_run:
                hosts_path = Path(__file__).resolve().parents[2] / "data/hosts.preview"
            elif os.name != "nt":
                raise ControllerError("Real hosts-file control is supported only on Windows.")
            else:
                hosts_path = _system_hosts_path()
        self.hosts_path = Path(hosts_path).resolve()
        self._is_system_file = self.hosts_path == _system_hosts_path().resolve()
        if self._is_system_file and (dry_run or os.name != "nt"):
            raise ControllerError("Preview mode cannot modify the Windows system hosts file.")
        self.warning: str | None = None
        self._expires_at: datetime | None = None
        self._mutex = threading.RLock()
        if dry_run:
            try:
                self.hosts_path.parent.mkdir(parents=True, exist_ok=True)
                # Exclusive create never truncates an existing preview file.
                with self.hosts_path.open("xb") as handle:
                    handle.write(b"# YouTube Gatekeeper preview hosts file\r\n")
            except FileExistsError:
                pass
            except OSError as exc:
                raise self._file_error(exc) from exc

    def _file_error(self, exc: OSError) -> ControllerError:
        if isinstance(exc, PermissionError) or getattr(exc, "winerror", None) in (5, 1314):
            suffix = (
                " Open PowerShell as Administrator and start the backend again."
                if self._is_system_file
                else " Check this file's permissions and whether another application has locked it."
            )
            return PermissionDeniedError(f"Permission denied for hosts file {self.hosts_path}.{suffix}")
        if isinstance(exc, FileNotFoundError):
            return ControllerError(f"Hosts file does not exist: {self.hosts_path}")
        return ControllerError(f"Cannot access hosts file {self.hosts_path}: {exc}")

    @staticmethod
    def _section(data: bytes) -> tuple[int, int, bytes, bool] | None:
        """Return the complete owned span, body and separator ownership flag."""
        if data.startswith((b"\xff\xfe", b"\xfe\xff")):
            raise ControllerError("UTF-16 hosts files are unsupported; use an ASCII or UTF-8 hosts file.")
        starts: list[tuple[int, int]] = []
        ends: list[tuple[int, int]] = []
        offset = 0
        for line in data.splitlines(keepends=True):
            content = line.rstrip(b"\r\n")
            for marker, locations in ((START_MARKER, starts), (END_MARKER, ends)):
                if marker.split()[2] in content:
                    if content != marker:
                        raise ControllerError("Malformed Gatekeeper marker. Repair the managed section before retrying.")
                    locations.append((offset, offset + len(line)))
            offset += len(line)
        if not starts and not ends:
            return None
        if len(starts) != 1 or len(ends) != 1 or starts[0][0] >= ends[0][0]:
            raise ControllerError("Missing, duplicate or out-of-order Gatekeeper markers. Hosts file left unchanged.")
        start, body_start = starts[0]
        body_end, end = ends[0]
        body = data[body_start:body_end]
        joined = JOINED_MARKER in body.splitlines()
        if joined:
            if start >= 2 and data[start - 2:start] == b"\r\n":
                start -= 2
            elif start >= 1 and data[start - 1:start] in (b"\n", b"\r"):
                start -= 1
            else:
                raise ControllerError("Invalid Gatekeeper separator metadata. Hosts file left unchanged.")
        return start, end, body, joined

    @staticmethod
    def _newline(data: bytes) -> bytes:
        first_lf = data.find(b"\n")
        if first_lf > 0 and data[first_lf - 1:first_lf] == b"\r":
            return b"\r\n"
        return b"\n" if first_lf >= 0 else b"\r\n"

    def _read(self) -> bytes:
        try:
            return self.hosts_path.read_bytes()
        except OSError as exc:
            raise self._file_error(exc) from exc

    def is_youtube_blocked(self) -> bool:
        """Whether the managed section maps every supported domain to loopback."""
        with self._mutex:
            section = self._section(self._read())
            if section is None:
                return False
            mappings: set[bytes] = set()
            for line in section[2].splitlines():
                fields = line.split(b"#", 1)[0].split()
                if fields and fields[0] == b"127.0.0.1":
                    mappings.update(domain.lower() for domain in fields[1:])
            return all(domain.encode("ascii") in mappings for domain in YOUTUBE_DOMAINS)

    @contextmanager
    def _locked_writer(self) -> Iterator[BinaryIO]:
        if self._is_system_file and not ctypes.windll.shell32.IsUserAnAdmin():
            raise PermissionDeniedError(
                "Administrator privileges are required to modify the Windows hosts file. "
                "Open PowerShell as Administrator and start the backend again."
            )
        try:
            with self.hosts_path.open("r+b") as handle:
                if os.name == "nt":
                    import msvcrt

                    # Lock the full ordinary file range, including room for an
                    # appended section, throughout the read/modify/write cycle.
                    try:
                        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 2**31 - 1)
                    except OSError as exc:
                        raise ControllerError("The hosts file is busy. Close other hosts editors and retry.") from exc
                    try:
                        yield handle
                    finally:
                        handle.seek(0)
                        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 2**31 - 1)
                else:
                    # Non-Windows paths are explicit test/preview files only.
                    yield handle
        except OSError as exc:
            raise self._file_error(exc) from exc

    @staticmethod
    def _replace_contents(handle: BinaryIO, original: bytes, updated: bytes) -> None:
        if updated == original:
            return
        try:
            handle.seek(0)
            handle.write(updated)
            handle.truncate()
            handle.flush()
            os.fsync(handle.fileno())
        except OSError as exc:
            # Keep the original inode and permissions. If a write fails midway,
            # attempt to restore the bytes before reporting the failure.
            try:
                handle.seek(0)
                handle.write(original)
                handle.truncate()
                handle.flush()
                os.fsync(handle.fileno())
            except OSError:
                raise ControllerError("Hosts update and rollback failed. Restore the hosts file manually.") from exc
            raise

    def _flush_dns(self) -> None:
        self.warning = None
        if not self._is_system_file:
            return
        executable = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32/ipconfig.exe"
        try:
            subprocess.run(
                [str(executable), "/flushdns"],
                check=True,
                timeout=10,
                capture_output=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            self.warning = "Hosts file updated, but DNS cache flush failed. Close and reopen your browser."
            logger.warning("%s (%s)", self.warning, type(exc).__name__)

    def block_youtube(self) -> None:
        with self._mutex:
            with self._locked_writer() as handle:
                original = handle.read()
                section = self._section(original)
                newline = self._newline(original)
                joined = bool(original and not original.endswith((b"\r", b"\n"))) if section is None else section[3]
                lines = [START_MARKER]
                if joined:
                    lines.append(JOINED_MARKER)
                lines.extend(b"127.0.0.1 " + domain.encode("ascii") for domain in YOUTUBE_DOMAINS)
                lines.append(END_MARKER)
                managed = newline.join(lines)
                if section is None:
                    updated = original + (newline if joined else b"") + managed + newline
                else:
                    start, end, _, _ = section
                    # A preexisting end marker may itself have no final newline.
                    if original[end - 1:end] in (b"\r", b"\n"):
                        managed += newline
                    updated = original[:start] + (newline if joined else b"") + managed + original[end:]
                self._replace_contents(handle, original, updated)
            self._expires_at = None
            if updated != original:
                self._flush_dns()

    def unblock_youtube(self, duration_minutes: int) -> None:
        # In particular, reject bool (a subclass of int), floats, None and zero.
        if type(duration_minutes) is not int or duration_minutes <= 0:
            raise ControllerError("YouTube access requires a positive integer duration in minutes.")
        try:
            expires_at = datetime.now(timezone.utc) + timedelta(minutes=duration_minutes)
        except OverflowError as exc:
            raise ControllerError("YouTube access duration is out of range.") from exc
        with self._mutex:
            changed = False
            with self._locked_writer() as handle:
                original = handle.read()
                section = self._section(original)
                if section is not None:
                    updated = original[:section[0]] + original[section[1]:]
                    self._replace_contents(handle, original, updated)
                    changed = updated != original
            self._expires_at = expires_at
            if changed:
                self._flush_dns()

    def get_current_access_expiry(self) -> datetime | None:
        """Informational only; durable expiry comes from the session manager."""
        with self._mutex:
            return self._expires_at
