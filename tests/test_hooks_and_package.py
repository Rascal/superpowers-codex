import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import zipfile

from test_review_gate import GateCase, ROOT, SCRIPTS, contract


class HookTests(GateCase):
    def hook(self, event="Stop", session="session-1", **extra):
        payload = dict(hook_event_name=event, session_id=session, cwd=str(self.root), **extra)
        result = subprocess.run([sys.executable, "-B", str(SCRIPTS / "codex_hook.py")],
                                input=json.dumps(payload), text=True, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def bind(self):
        self.call("bind", "--session", "session-1", "--plan", "example-plan")

    def test_unbound_sessions_are_not_blocked(self):
        self.create()
        self.assertEqual(self.hook(), {})

    def test_binding_is_explicit_and_isolated(self):
        self.create(); self.bind()
        self.assertEqual(self.hook(session="unrelated"), {})
        self.assertEqual(self.hook()["decision"], "block")
        self.call("unbind", "--session", "session-1")
        self.assertEqual(self.hook(), {})

    def test_stop_reads_state_and_ignores_claimed_success(self):
        self.create(); self.bind()
        before = (self.root / ".review-gate/state.json").read_bytes()
        result = self.hook(last_assistant_message="AC: PROVEN BY all tests passed, plan complete")
        self.assertEqual(result["decision"], "block")
        self.assertEqual(before, (self.root / ".review-gate/state.json").read_bytes())

    def test_blocked_work_and_continuation_do_not_loop_forever(self):
        self.create(); self.bind()
        self.assertNotIn("decision", self.hook(stop_hook_active=True))
        self.call("block", "example", "--owner", "implementer-1", "--reason", "Needs user input")
        self.assertIn("systemMessage", self.hook())
        self.assertNotIn("decision", self.hook())

    def test_interrupt_is_never_blocked(self):
        self.create(); self.bind()
        self.assertEqual(self.hook("Interrupt"), {})

    def test_session_start_restores_plan_context(self):
        self.create(); self.bind()
        result = self.hook("SessionStart")
        self.assertIn("example-plan", result["hookSpecificOutput"]["additionalContext"])
        self.assertIn("implementer-1", result["hookSpecificOutput"]["additionalContext"])

    def test_complete_plan_allows_stop_but_later_edit_does_not(self):
        self.create(); self.finish()
        self.create(contract(kind="integration", depends_on=["example"]), name="integration")
        self.finish("integration"); self.bind()
        self.assertEqual(self.hook(), {})
        self.source.write_text("answer = 6 * 7\n", encoding="utf-8")
        self.assertEqual(self.hook()["decision"], "block")

    def test_corrupt_state_is_visible_and_not_approval(self):
        (self.root / ".review-gate/state.json").write_text("{invalid", encoding="utf-8")
        result = self.hook()
        self.assertIn("not approval", result["systemMessage"])

    def test_missing_state_is_noop(self):
        self.assertEqual(self.hook(), {})
        self.assertFalse((self.root / ".review-gate/state.json").exists())


class PackageTests(GateCase):
    def extracted_plugin(self):
        archive = self.build()
        destination = self.root / "installed plugin with spaces"
        with zipfile.ZipFile(archive) as bundle:
            bundle.extractall(destination)
        return next(destination.rglob("plugin.json")).parent

    def test_packaged_native_hook_commands_execute(self):
        plugin = self.extracted_plugin()
        hooks = json.loads((plugin / "hooks/hooks.json").read_text(encoding="utf-8"))["hooks"]
        environment = dict(os.environ, PLUGIN_ROOT=str(plugin))
        for event, groups in hooks.items():
            handler = groups[0]["hooks"][0]
            command = handler["commandWindows"] if os.name == "nt" else handler["command"]
            payload = {"hook_event_name": event, "session_id": "smoke", "cwd": str(self.root)}
            with self.subTest(event=event):
                result = subprocess.run(command, shell=True, cwd=self.root, env=environment,
                                        input=json.dumps(payload), text=True, capture_output=True, timeout=10)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(result.stdout), {})

    def test_windows_hook_override_imports_relocated_runtime(self):
        plugin = self.extracted_plugin()
        hooks = json.loads((plugin / "hooks/hooks.json").read_text(encoding="utf-8"))["hooks"]
        command = shlex.split(hooks["Stop"][0]["hooks"][0]["commandWindows"])
        self.assertEqual(command[0], "python")
        command[0] = sys.executable
        result = subprocess.run(command, cwd=self.root, env=dict(os.environ, PLUGIN_ROOT=str(plugin)),
                                input=json.dumps({"hook_event_name": "Stop", "session_id": "smoke", "cwd": str(self.root)}),
                                text=True, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {})

    def test_repository_catalog_resolves_plugin_at_repository_root(self):
        catalog = json.loads((ROOT / ".agents/plugins/marketplace.json").read_text(encoding="utf-8"))
        self.assertEqual(catalog["name"], "superpowers-codex")
        plugin = catalog["plugins"][0]
        plugin_path = (ROOT / plugin["source"]["path"]).resolve()
        self.assertEqual(plugin_path, ROOT)
        manifest = json.loads((plugin_path / "plugin.json").read_text(encoding="utf-8"))
        self.assertEqual(plugin["name"], manifest["name"])
        self.assertEqual(manifest["repository"], "https://github.com/Rascal/superpowers-codex")

    def build(self):
        result = subprocess.run([sys.executable, str(ROOT / "scripts/build_plugin.py"), "--output", str(self.root / "release")],
                                text=True, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        return Path(json.loads(result.stdout)["archive"])

    def test_archive_contains_only_distributable_plugin_files(self):
        archive = self.build()
        with zipfile.ZipFile(archive) as bundle:
            names = bundle.namelist()
            self.assertFalse(any(".review-gate/" in name or "__pycache__" in name or name.endswith(".pyc") for name in names))
            catalog_name = next(name for name in names if name.endswith(".agents/plugins/marketplace.json"))
            catalog = json.loads(bundle.read(catalog_name))
            self.assertEqual(catalog["name"], "superpowers-codex")
            plugin_root = catalog_name.split("/.agents/")[0] + "/" + catalog["plugins"][0]["source"]["path"][2:]
            manifest = json.loads(bundle.read(plugin_root + "/plugin.json"))
            self.assertEqual(manifest["name"], "superpowers-codex")
            self.assertIn(plugin_root + "/skills/review-gated-development/scripts/review_gate.py", names)
            self.assertIn(plugin_root + "/hooks/hooks.json", names)
            self.assertFalse(any(str(ROOT).encode() in bundle.read(name) for name in names))

    def test_relocated_plugin_runs_without_source_checkout(self):
        archive = self.build()
        destination = self.root / "installed plugin with spaces"
        with zipfile.ZipFile(archive) as bundle:
            bundle.extractall(destination)
        script = next(destination.rglob("review_gate.py"))
        workspace = self.root / "consumer project"
        workspace.mkdir()
        (workspace / "app.py").write_text("answer = 42\n", encoding="utf-8")
        def run(*args, payload=None):
            result = subprocess.run([sys.executable, "-B", str(script), "--workspace", str(workspace), *args],
                                    input=json.dumps(payload) if payload else None, text=True, capture_output=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            return json.loads(result.stdout)
        run("create", "portable", "--contract", "-", payload=contract())
        run("claim", "portable", "--owner", "worker")
        evidence = run("verify", "portable", "--owner", "worker")
        self.assertEqual(evidence["verification"]["status"], "passed")
        packet = run("request-review", "portable", "--owner", "worker")
        run("review", "portable", "--round", packet["round"], "--reviewer", "reviewer", "--report", "-",
            payload={"verdict": "approved", "spec_review": "Meets C1", "quality_review": "Checked", "findings": [], "resolutions": []})
        self.assertEqual(run("complete", "portable", "--owner", "worker")["state"], "completed")
