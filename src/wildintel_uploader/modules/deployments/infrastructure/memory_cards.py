"""A memory card on this computer — its files read, and the removable drive it is on ejected with what the system has (PowerShell, diskutil,
udisks) — and the folder of the copies, inside the temporary folder of the system."""
from __future__ import annotations

import logging
import platform
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from wildintel_uploader.modules.deployments.domain import cards as rules
from wildintel_uploader.modules.deployments.domain.ports import CardCopies, MemoryCard
from wildintel_uploader.modules.deployments.infrastructure import disk_space

logger = logging.getLogger(__name__)


def base_dir() -> Path:
    """The folder of the copies — asked each time, as the temporary folder of the system says."""
    return Path(tempfile.gettempdir()) / rules.BASE_NAME


class CopiesInTemp(CardCopies):
    def base(self) -> Path:
        return base_dir().resolve()

    def resolve(self, path: str) -> Path:
        return Path(path).expanduser().resolve()

    def holders(self) -> list[tuple[Path, float]]:
        base = base_dir()
        if not base.is_dir():
            return []
        kept = []
        for entry in base.iterdir():
            try:
                if entry.is_dir():
                    kept.append((entry, entry.stat().st_mtime))
            except OSError as exc:
                logger.warning("Could not read the old copy of a card %s: %s", entry, exc)
        return kept

    def shortfall(self, needed: int) -> str | None:
        return disk_space.shortfall(base_dir(), needed, rules.WHAT, rules.WHERE)

    def new_holder(self) -> Path:
        base_dir().mkdir(parents=True, exist_ok=True)
        return Path(tempfile.mkdtemp(prefix="card-", dir=base_dir()))

    def copy(self, card: Path, file: Path, to: Path) -> None:
        target = to / file
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(card / file, target)
        except OSError as exc:
            raise rules.not_copied(exc) from exc

    def remove(self, holder: Path) -> bool:
        if not holder.is_dir():
            return False
        try:
            shutil.rmtree(holder)
        except OSError as exc:
            logger.warning("Could not remove the copy of a card %s: %s", holder, exc)
            return False
        return True


def _run(command: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(command, capture_output=True, text=True, check=False)


def _eject_windows(path: Path) -> dict:
    drive = path.drive  # "E:"
    if not drive:
        return {"ejected": False, "message": "The card is not on a drive of its own."}
    import ctypes
    if ctypes.windll.kernel32.GetDriveTypeW(f"{drive}\\") != 2:  # DRIVE_REMOVABLE
        return {"ejected": False, "message": f"{drive} is not a removable drive: nothing ejected."}
    script = f"(New-Object -ComObject Shell.Application).Namespace(17).ParseName('{drive}').InvokeVerb('Eject')"
    result = _run(["powershell", "-NoProfile", "-STA", "-Command", script])
    if result.returncode != 0:
        return {"ejected": False, "message": f"Could not eject {drive}: {result.stderr.strip()}"}
    return {"ejected": True, "message": f"{drive} ejected: you can take the card out."}


def _eject_macos(path: Path) -> dict:
    parts = path.resolve().parts
    if len(parts) < 3 or parts[1] != "Volumes":
        return {"ejected": False, "message": "The card is not a mounted volume."}
    volume = Path("/", parts[1], parts[2])
    result = _run(["diskutil", "eject", str(volume)])
    if result.returncode != 0:
        return {"ejected": False, "message": f"Could not eject {volume.name}: {result.stderr.strip()}"}
    return {"ejected": True, "message": f"{volume.name} ejected: you can take the card out."}


def _udisks_removable(disk: str) -> bool:
    """Whether udisks does not take the drive for a system one — the reader of a laptop (an mmcblk) is neither removable nor hotplug for lsblk, yet it holds cards."""
    info = _run(["udisksctl", "info", "-b", disk]).stdout.lower()
    hint = re.search(r"hintsystem:\s*(\w+)", info)
    removable = re.search(r"\bremovable:\s*(\w+)", info)
    return bool((hint and hint.group(1) == "false") or (removable and removable.group(1) == "true"))


def _eject_linux(path: Path) -> dict:
    """Unmounts the partition the folder is on and powers the drive off, with udisks — only when the system says the drive is removable."""
    mount = _run(["findmnt", "-n", "-o", "SOURCE,TARGET", "--target", str(path.resolve())])
    fields = mount.stdout.strip().split(maxsplit=1)
    if mount.returncode != 0 or len(fields) != 2 or not fields[0].startswith("/dev/"):
        return {"ejected": False, "message": "The card is not a mounted volume."}
    device, target = fields
    parent = _run(["lsblk", "-no", "PKNAME", device]).stdout.strip().splitlines()
    disk = f"/dev/{parent[0].strip()}" if parent and parent[0].strip() else device
    flags = _run(["lsblk", "-dno", "RM,HOTPLUG", disk]).stdout.split()
    if "1" not in flags and not _udisks_removable(disk):
        return {"ejected": False, "message": f"{target} is not on a removable drive: nothing ejected."}
    unmounted = _run(["udisksctl", "unmount", "-b", device])
    if unmounted.returncode != 0:
        return {"ejected": False, "message": f"Could not eject {target}: {(unmounted.stderr or unmounted.stdout).strip()}"}
    _run(["udisksctl", "power-off", "-b", disk])  # not every reader can be powered off: unmounted is enough to take the card out
    return {"ejected": True, "message": f"{target} ejected: you can take the card out."}


class CardOnDisk(MemoryCard):
    def files(self, card: str) -> tuple[Path, list[tuple[Path, int]]]:
        source = Path(card).expanduser()
        if not source.is_dir():
            raise rules.not_a_folder(card)
        try:
            return source, [(p.relative_to(source), p.stat().st_size) for p in sorted(source.rglob("*")) if p.is_file()]
        except OSError as exc:
            raise rules.unreadable(card, exc) from exc

    def eject(self, card: str) -> dict:
        path = Path(card).expanduser()
        system = platform.system()
        try:
            if system == "Windows":
                return _eject_windows(path)
            if system == "Darwin":
                return _eject_macos(path)
            if system == "Linux":
                return _eject_linux(path)
        except (OSError, subprocess.SubprocessError) as exc:
            return {"ejected": False, "message": f"Could not eject the card: {exc}"}
        return {"ejected": False, "message": "Eject the card from the system before taking it out."}
