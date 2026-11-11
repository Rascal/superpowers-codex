import json
from pathlib import Path
import shutil
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]


class NativeDiscoveryTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("codex"), "Codex CLI is not installed on this test host")
    def test_source_manifest_exposes_both_hooks_to_codex(self):
        result = subprocess.run([sys.executable, "-B", str(ROOT / "scripts/check_native_hooks.py")],
                                text=True, capture_output=True, timeout=55)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["declared_events"], ["sessionStart", "stop"])
