"""Durable local state and workspace fingerprints."""

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import stat
import tempfile
import time

if os.name == "nt":
    import msvcrt
else:
    import fcntl


class GateError(Exception):
    pass


def require(condition, message):
    if not condition:
        raise GateError(message)


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def fingerprint(root):
    files = {".": {"kind": "directory", "mode": stat.S_IMODE(root.stat().st_mode)}}

    def visit(directory):
        for path in sorted(directory.iterdir()):
            relative = path.relative_to(root).as_posix()
            if relative in (".git", ".review-gate"):
                continue
            info = path.lstat()
            require(not stat.S_ISLNK(info.st_mode), "Symlinks are unsupported: " + relative)
            if stat.S_ISDIR(info.st_mode):
                if path.name == "__pycache__":
                    continue
                files[relative] = {"kind": "directory", "mode": stat.S_IMODE(info.st_mode)}
                visit(path)
            else:
                require(stat.S_ISREG(info.st_mode), "Unsupported file type: " + relative)
                content = hashlib.sha256()
                with path.open("rb") as source:
                    for chunk in iter(lambda: source.read(1024 * 1024), b""):
                        content.update(chunk)
                files[relative] = {"kind": "file", "sha256": content.hexdigest(), "mode": stat.S_IMODE(info.st_mode)}

    visit(root)
    return {"digest": digest(files), "files": files}


class Store:
    def __init__(self, root, lock_timeout=5, create=True):
        self.root = Path(root).resolve(strict=True)
        require(self.root.is_dir(), "Workspace must be a directory")
        self.directory = self.root / ".review-gate"
        require(not self.directory.is_symlink(), "State directory cannot be a symlink")
        if create:
            self.directory.mkdir(exist_ok=True)
        self.path = self.directory / "state.json"
        self.lock_timeout = lock_timeout

    @contextmanager
    def locked(self):
        with (self.directory / "lock").open("a+b") as lock:
            lock.seek(0, os.SEEK_END)
            if lock.tell() == 0:
                lock.write(b"0")
                lock.flush()
            deadline = time.monotonic() + self.lock_timeout
            while True:
                try:
                    lock.seek(0)
                    if os.name == "nt":
                        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
                    else:
                        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except OSError:
                    require(time.monotonic() < deadline, "Task store is busy; lock timeout")
                    time.sleep(0.02)
            try:
                yield
            finally:
                lock.seek(0)
                if os.name == "nt":
                    msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(lock, fcntl.LOCK_UN)

    def load(self):
        if not self.path.exists():
            return {"version": 3, "workspace": str(self.root), "tasks": {}, "bindings": {}}
        data = json.loads(self.path.read_text(encoding="utf-8"))
        require(isinstance(data, dict) and data.get("version") in (1, 2, 3), "Unsupported task store")
        require(not data.get("planning") or data["version"] == 3, "Planning records require store format 3")
        require(data.get("workspace") == str(self.root), "Task store belongs to another workspace")
        require(isinstance(data.get("tasks"), dict), "Invalid task store")
        if data["version"] == 1:
            for task in data["tasks"].values():
                task["version"] = 1
            data["version"] = 2
            data["bindings"] = {}
        return data

    def save(self, data):
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.directory, delete=False) as output:
            temp = Path(output.name)
            try:
                json.dump(data, output, indent=2, sort_keys=True)
                output.write("\n")
                output.flush()
                os.fsync(output.fileno())
            except BaseException:
                temp.unlink(missing_ok=True)
                raise
        try:
            os.replace(temp, self.path)
        finally:
            temp.unlink(missing_ok=True)
