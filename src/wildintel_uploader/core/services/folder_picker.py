"""Opens the OS's native "choose a folder" dialog for the web UI's
"Browse…" button.

This is a local desktop app whose backend and frontend always run on the
same machine — the browser tab it shows itself in is just how the UI is
drawn (see web.app_entry) — so the backend can pop a native dialog on that
machine's own display. Rather than bundling a GUI toolkit (the PyInstaller
spec deliberately excludes tkinter, which is also awkward to bundle
cross-platform), this shells out to whatever dialog tool the platform
already ships with."""
from __future__ import annotations

import platform
import shutil
import subprocess


class FolderPickerUnavailable(RuntimeError):
    """No native folder dialog could be found or run on this machine."""


def _pick_linux(title: str) -> str | None:
    if shutil.which("zenity"):
        cmd = ["zenity", "--file-selection", "--directory", f"--title={title}"]
    elif shutil.which("kdialog"):
        cmd = ["kdialog", "--getexistingdirectory", ".", f"--title={title}"]
    else:
        raise FolderPickerUnavailable("No folder dialog tool found — install zenity (GNOME) or kdialog (KDE).")
    # A non-zero exit means the dialog was cancelled (also true if it
    # couldn't even open, e.g. no display — nothing to pick either way).
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    return result.stdout.strip() or None if result.returncode == 0 else None


def _pick_macos(title: str) -> str | None:
    script = f'POSIX path of (choose folder with prompt "{title}")'
    result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, check=False)
    return result.stdout.strip() or None if result.returncode == 0 else None


def _pick_windows(title: str) -> str | None:
    script = (
        "Add-Type -AssemblyName System.Windows.Forms | Out-Null; "
        "$f = New-Object System.Windows.Forms.FolderBrowserDialog; "
        f"$f.Description = '{title}'; "
        "if ($f.ShowDialog() -eq 'OK') { Write-Output $f.SelectedPath }"
    )
    result = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise FolderPickerUnavailable(result.stderr.strip() or "Could not open the folder dialog.")
    return result.stdout.strip() or None


def _pick_file_linux(title: str, extension: str) -> str | None:
    if shutil.which("zenity"):
        cmd = ["zenity", "--file-selection", f"--title={title}", f"--file-filter=*.{extension}"]
    elif shutil.which("kdialog"):
        cmd = ["kdialog", "--getopenfilename", ".", f"*.{extension}", f"--title={title}"]
    else:
        raise FolderPickerUnavailable("No file dialog tool found — install zenity (GNOME) or kdialog (KDE).")
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    return result.stdout.strip() or None if result.returncode == 0 else None


def _pick_file_macos(title: str, extension: str) -> str | None:
    script = f'POSIX path of (choose file with prompt "{title}" of type {{"{extension}"}})'
    result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, check=False)
    return result.stdout.strip() or None if result.returncode == 0 else None


def _pick_file_windows(title: str, extension: str) -> str | None:
    script = (
        "Add-Type -AssemblyName System.Windows.Forms | Out-Null; "
        "$f = New-Object System.Windows.Forms.OpenFileDialog; "
        f"$f.Title = '{title}'; $f.Filter = '*.{extension}|*.{extension}|All files|*.*'; "
        "if ($f.ShowDialog() -eq 'OK') { Write-Output $f.FileName }"
    )
    result = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise FolderPickerUnavailable(result.stderr.strip() or "Could not open the file dialog.")
    return result.stdout.strip() or None


def pick_file(title: str = "Select a file", extension: str = "zip") -> str | None:
    """The file the user picked (of this extension), or None if the dialog was cancelled.

    Raises:
        FolderPickerUnavailable: no native dialog tool is available — the caller should let the user type the path instead.
    """
    system = platform.system()
    if system == "Linux":
        return _pick_file_linux(title, extension)
    if system == "Darwin":
        return _pick_file_macos(title, extension)
    if system == "Windows":
        return _pick_file_windows(title, extension)
    raise FolderPickerUnavailable(f"No file dialog support for {system}.")


def pick_folder(title: str = "Select a folder") -> str | None:
    """The folder the user picked, or None if the dialog was cancelled.

    Raises:
        FolderPickerUnavailable: no native dialog tool is available on this
            platform/machine — the caller should let the user type the path
            instead.
    """
    system = platform.system()
    if system == "Linux":
        return _pick_linux(title)
    if system == "Darwin":
        return _pick_macos(title)
    if system == "Windows":
        return _pick_windows(title)
    raise FolderPickerUnavailable(f"No folder dialog support for {system}.")
