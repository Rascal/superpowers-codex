#!/usr/bin/env python3
"""Check hook discovery through Codex's read-only app-server protocol."""

import argparse
import json
from pathlib import Path
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
import time


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = "superpowers-codex"
EXPECTED_EVENTS = {"sessionStart", "stop"}


def inspect(marketplace, cwd, require_installed=False):
    executable = shutil.which("codex")
    if not executable:
        raise RuntimeError("Codex CLI is required for native hook discovery checks")
    messages = queue.Queue()
    with tempfile.TemporaryFile(mode="w+t") as errors:
        process = subprocess.Popen([executable, "app-server", "--stdio"], stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE, stderr=errors, text=True, encoding="utf-8")

        def read_messages():
            try:
                for line in process.stdout:
                    messages.put(json.loads(line))
            except Exception as error:
                messages.put(error)
            finally:
                messages.put(EOFError("Codex app-server closed the connection"))

        reader = threading.Thread(target=read_messages, daemon=True)
        reader.start()

        def request(request_id, method, params):
            process.stdin.write(json.dumps({"id": request_id, "method": method, "params": params}) + "\n")
            process.stdin.flush()
            deadline = time.monotonic() + 20
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError("Codex metadata request timed out: " + method)
                try:
                    message = messages.get(timeout=remaining)
                except queue.Empty:
                    raise TimeoutError("Codex metadata request timed out: " + method)
                if isinstance(message, Exception):
                    raise message
                if message.get("id") == request_id:
                    if "error" in message:
                        raise RuntimeError(json.dumps(message["error"]))
                    return message["result"]

        try:
            request(0, "initialize", {"clientInfo": {"name": "superpowers-hook-check", "version": "1.0"},
                                     "capabilities": {"experimentalApi": True, "explicitGatewayOauth": True}})
            process.stdin.write(json.dumps({"method": "initialized", "params": {}}) + "\n")
            process.stdin.flush()
            plugin = request(1, "plugin/read", {"pluginName": PLUGIN, "marketplacePath": str(marketplace)})["plugin"]
            declared = plugin["hooks"]
            if len(declared) != 2 or {hook["eventName"] for hook in declared} != EXPECTED_EVENTS:
                raise RuntimeError("Codex did not discover both declared plugin hooks: " + json.dumps(declared))
            result = {"declared_events": sorted(EXPECTED_EVENTS)}
            if require_installed:
                entries = request(2, "hooks/list", {"cwds": [str(cwd)]})["data"]
                hooks = [hook for entry in entries for hook in entry["hooks"] if hook.get("pluginId") == PLUGIN + "@" + PLUGIN]
                if len(hooks) != 2 or {hook["eventName"] for hook in hooks} != EXPECTED_EVENTS:
                    raise RuntimeError("Installed hook listing is incomplete: " + json.dumps(hooks))
                result["installed_hooks"] = [{key: hook[key] for key in ("eventName", "enabled", "trustStatus", "sourcePath")} for hook in hooks]
            return result
        finally:
            if process.poll() is None:
                process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
            process.stdin.close()
            reader.join(timeout=1)
            process.stdout.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--marketplace", type=Path, default=ROOT / ".agents/plugins/marketplace.json")
    parser.add_argument("--cwd", type=Path, default=ROOT)
    parser.add_argument("--require-installed", action="store_true")
    args = parser.parse_args()
    try:
        print(json.dumps(inspect(args.marketplace.resolve(), args.cwd.resolve(), args.require_installed), indent=2))
    except (RuntimeError, OSError, ValueError, EOFError, KeyError) as error:
        print(json.dumps({"error": str(error)}), file=sys.stderr)
        sys.exit(1)
