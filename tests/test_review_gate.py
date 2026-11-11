import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'skills/review-gated-development/scripts'
SCRIPT = SCRIPTS / 'review_gate.py'
sys.path.insert(0, str(SCRIPTS))
import review_gate as gate


def contract(code='import app; assert app.answer == 42; print("VERIFIED")', **overrides):
    value = {'objective': 'Return the answer', 'plan': 'example-plan', 'kind': 'implementation',
             'depends_on': [], 'constraints': ['Do not mutate unrelated files'],
             'user_decisions': ['Independent review is required'],
             'criteria': [{'id': 'C1', 'description': 'The answer is 42', 'checks': ['check']}],
             'checks': [{'id': 'check', 'argv': ['{python}', '-B', '-c', code], 'timeout': 5,
                         'assertions': [{'stream': 'stdout', 'contains': 'VERIFIED'}]}]}
    value.update(overrides)
    return value


def report(verdict='approved', findings=None, resolutions=None):
    return {'verdict': verdict, 'spec_review': 'Acceptance criteria checked against source.',
            'quality_review': 'Behavior and failure paths reviewed.', 'findings': findings or [], 'resolutions': resolutions or []}


def finding(name='F1', severity='blocking'):
    return {'id': name, 'severity': severity, 'detail': 'Missing empty input handling.', 'evidence': 'app.py:1'}


class GateCase(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.source = self.root / 'app.py'
        self.source.write_text('answer = 42\n', encoding='utf-8')
        (self.root / '.review-gate').mkdir()

    def call(self, *args, success=True, payload=None):
        result = subprocess.run([sys.executable, '-B', str(SCRIPT), '--workspace', str(self.root), *args],
                                input=json.dumps(payload) if payload is not None else None,
                                text=True, capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0 if success else 1, result.stdout + result.stderr)
        return json.loads(result.stdout if success else result.stderr)

    def create(self, definition=None, name='example', claim=True, success=True):
        value = definition or contract()
        result = self.call('create', name, '--contract', '-', payload=value, success=success)
        if success and claim:
            self.call('claim', name, '--owner', 'implementer-1')
        return result

    def verify(self, name='example', owner='implementer-1', success=True):
        return self.call('verify', name, '--owner', owner, success=success)

    def ready(self, name='example', owner='implementer-1'):
        self.verify(name, owner)
        return self.call('request-review', name, '--owner', owner)

    def review(self, packet, value=None, reviewer='reviewer-1', success=True):
        return self.call('review', packet['task_id'], '--round', packet['round'], '--reviewer', reviewer,
                         '--report', '-', payload=value or report(), success=success)

    def finish(self, name='example', owner='implementer-1'):
        packet = self.ready(name, owner)
        self.review(packet)
        return self.call('complete', name, '--owner', owner)

    def state(self, name='example'):
        return self.call('show', name)


class LifecycleTests(GateCase):
    def test_success_survives_processes_and_preserves_decisions(self):
        self.create()
        self.finish()
        task = self.state()
        self.assertEqual(task['state'], 'completed')
        self.assertEqual(task['contract']['user_decisions'], ['Independent review is required'])
        self.assertEqual(task['history'][-1]['action'], 'completed')

    def test_cannot_skip_verification_or_review(self):
        self.create()
        self.call('request-review', 'example', '--owner', 'implementer-1', success=False)
        self.call('complete', 'example', '--owner', 'implementer-1', success=False)
        self.ready()
        self.call('complete', 'example', '--owner', 'implementer-1', success=False)

    def test_failed_command_retains_evidence(self):
        self.create(contract('import sys; print("VERIFIED"); sys.exit(3)'))
        self.verify(success=False)
        evidence = self.state()['attempts'][0]['verification']
        self.assertEqual(evidence['checks'][0]['exit_code'], 3)
        self.assertFalse(evidence['criteria']['C1']['passed'])

    def test_zero_exit_without_success_assertion_fails(self):
        self.create(contract('print("test runner did not start")'))
        self.verify(success=False)
        check = self.state()['attempts'][0]['verification']['checks'][0]
        self.assertEqual(check['exit_code'], 0)
        self.assertEqual(check['status'], 'failed')

    def test_each_criterion_maps_to_its_own_evidence(self):
        definition = contract()
        definition['checks'].append({'id': 'second', 'argv': ['{python}', '-c', 'print("missing")'], 'timeout': 5,
                                     'assertions': [{'stream': 'stdout', 'contains': 'EXPECTED'}]})
        definition['criteria'].append({'id': 'C2', 'description': 'Second outcome', 'checks': ['second']})
        self.create(definition)
        self.verify(success=False)
        criteria = self.state()['attempts'][0]['verification']['criteria']
        self.assertTrue(criteria['C1']['passed'])
        self.assertFalse(criteria['C2']['passed'])

    def test_no_verify_time_command_or_timeout_override(self):
        self.create()
        for extra in (['--', sys.executable, '-c', 'pass'], ['--timeout', '999']):
            result = subprocess.run([sys.executable, str(SCRIPT), '--workspace', str(self.root),
                                     'verify', 'example', '--owner', 'implementer-1', *extra], capture_output=True, timeout=10)
            self.assertEqual(result.returncode, 2)
        self.assertEqual(self.state()['attempts'], [])

    def test_contract_file_changes_do_not_change_stored_contract(self):
        path = self.root / '.review-gate/contract.json'
        path.write_text(json.dumps(contract()), encoding='utf-8')
        self.call('create', 'example', '--contract', str(path))
        path.write_text(json.dumps(contract('pass')), encoding='utf-8')
        self.call('claim', 'example', '--owner', 'implementer-1')
        self.finish()

    def test_invalid_contracts_rejected_without_creating_tasks(self):
        bad_values = []
        for timeout in (0, -1, float('nan'), float('inf'), 301, True):
            value = contract()
            value['checks'][0]['timeout'] = timeout
            bad_values.append(value)
        value = contract(); value['criteria'][0]['checks'] = ['unknown']; bad_values.append(value)
        value = contract(); value['checks'][0]['assertions'] = []; bad_values.append(value)
        value = contract(); value['criteria'] = []; bad_values.append(value)
        for value in bad_values:
            with self.subTest(value=value):
                self.create(value, success=False)
        self.assertEqual(self.call('list'), [])

    def test_timeout_records_failed_check(self):
        value = contract('import time; time.sleep(30)')
        value['checks'][0]['timeout'] = 0.1
        self.create(value)
        self.verify(success=False)
        self.assertEqual(self.state()['attempts'][0]['verification']['checks'][0]['status'], 'timed_out')

    def test_missing_executable_fails_closed(self):
        value = contract(); value['checks'][0]['argv'] = ['nonexistent-review-gate-executable']
        self.create(value)
        self.verify(success=False)
        self.assertEqual(self.state()['state'], 'implementing')

    def test_output_is_bounded_and_crlf_normalized(self):
        self.create(contract('import sys; sys.stdout.write("x" * 40000 + "VERIFIED\\r\\n")'))
        check = self.verify()['verification']['checks'][0]
        self.assertTrue(check['stdout_truncated'])
        self.assertLessEqual(len(check['stdout']), 32768)
        self.assertTrue(check['stdout'].endswith('VERIFIED\n'))

    def test_check_mutating_source_invalidates_evidence(self):
        self.create(contract('from pathlib import Path; Path("app.py").write_text("answer = 0"); print("VERIFIED")'))
        self.verify(success=False)
        self.assertIsNone(self.state()['active_attempt'])

    def test_changed_code_cannot_receive_review(self):
        self.create(); packet = self.ready()
        self.source.write_text('answer = 0\n', encoding='utf-8')
        self.review(packet, success=False)

    def test_changed_code_cannot_complete(self):
        self.create(); packet = self.ready(); self.review(packet)
        self.source.write_text('answer = 0\n', encoding='utf-8')
        self.call('complete', 'example', '--owner', 'implementer-1', success=False)
        self.assertIsNone(self.state()['active_attempt'])

    def test_added_deleted_and_cache_named_files_invalidate(self):
        for change in ('add', 'delete', 'pycache-file'):
            with self.subTest(change=change):
                task = 'task-' + change
                self.source.write_text('answer = 42\n', encoding='utf-8')
                self.create(name=task); packet = self.ready(task); self.review(packet)
                if change == 'delete':
                    self.source.unlink()
                else:
                    (self.root / ('__pycache__' if change == 'pycache-file' else 'new.py')).write_text('changed', encoding='utf-8')
                self.call('complete', task, '--owner', 'implementer-1', success=False)
                self.call('release', task, '--owner', 'implementer-1', '--reason', 'next scenario')

    @unittest.skipIf(os.name == 'nt', 'POSIX permission modes')
    def test_file_directory_and_root_modes_invalidate(self):
        directory = self.root / 'src'; directory.mkdir(); directory.chmod(0o755)
        self.root.chmod(0o755); self.source.chmod(0o644)
        for name, path, mode in [('file', self.source, 0o755), ('directory', directory, 0o700), ('root', self.root, 0o700)]:
            with self.subTest(name=name):
                self.create(name=name); packet = self.ready(name); self.review(packet)
                path.chmod(mode)
                self.call('complete', name, '--owner', 'implementer-1', success=False)
                self.call('release', name, '--owner', 'implementer-1', '--reason', 'next scenario')

    def test_empty_directory_addition_invalidates(self):
        self.create(); packet = self.ready(); self.review(packet)
        (self.root / 'new_directory').mkdir()
        self.call('complete', 'example', '--owner', 'implementer-1', success=False)

    def test_python_cache_directory_is_excluded(self):
        self.create(contract('import app; assert app.answer == 42; print("VERIFIED")'))
        directory = self.root / '__pycache__'; directory.mkdir(exist_ok=True)
        (directory / 'bytecode.pyc').write_bytes(b'cache')
        self.finish()

    def test_symlinks_are_rejected_even_when_named_pycache(self):
        self.create()
        try:
            (self.root / '__pycache__').symlink_to(self.source)
        except OSError:
            self.skipTest('Symlink creation unavailable for this account')
        self.verify(success=False)

    def test_owner_is_exclusive_and_recoverable(self):
        self.create()
        self.call('claim', 'example', '--owner', 'another', success=False)
        self.call('recover', 'example', '--owner', 'implementer-1', '--new-owner', 'another', '--reason', 'Confirmed prior agent unavailable')
        task = self.state()
        self.assertEqual(task['owner'], 'another')
        self.assertIn('implementer-1', task['implementers'])
        self.assertEqual(task['history'][-1]['action'], 'recover')
        self.verify(owner='implementer-1', success=False)
        packet = self.ready(owner='another')
        self.review(packet, reviewer='implementer-1', success=False)

    def test_workspace_serializes_owners_and_release_invalidates(self):
        self.create(); self.ready()
        self.create(name='next', claim=False)
        self.call('claim', 'next', '--owner', 'another', success=False)
        self.call('release', 'example', '--owner', 'implementer-1', '--reason', 'Pause work')
        self.assertIsNone(self.state()['active_attempt'])
        self.call('claim', 'next', '--owner', 'another')

    def test_blocked_work_does_not_complete(self):
        self.create()
        self.call('block', 'example', '--owner', 'implementer-1', '--reason', 'Missing required external fixture')
        self.verify(success=False)
        self.call('complete', 'example', '--owner', 'implementer-1', success=False)
        self.assertEqual(self.state()['history'][-1]['reason'], 'Missing required external fixture')

    def test_self_review_rejected(self):
        self.create(); packet = self.ready()
        self.review(packet, reviewer=' implementer-1 ', success=False)

    def test_findings_cannot_disappear_between_rounds(self):
        self.create(); packet = self.ready()
        self.review(packet, report('changes_requested', [finding()]))
        self.source.write_text('answer = 6 * 7\n', encoding='utf-8')
        fresh = self.ready()
        self.assertEqual(fresh['review_scope'], 'fix')
        self.assertIn('app.py', fresh['changed_since_review'])
        self.assertIn('F1', fresh['findings'])
        self.review(fresh, success=False)
        self.review(fresh, report(resolutions=[{'id': 'F1', 'status': 'addressed', 'evidence': 'app.py:1 and regression test'}]))
        self.call('complete', 'example', '--owner', 'implementer-1')
        self.assertEqual(self.state()['findings']['F1']['status'], 'addressed')

    def test_unaddressed_finding_stays_blocking(self):
        self.create(); packet = self.ready(); self.review(packet, report('changes_requested', [finding()]))
        fresh = self.ready()
        resolution = {'id': 'F1', 'status': 'not_addressed', 'evidence': 'Original failure still reproduced'}
        self.review(fresh, report(resolutions=[resolution]), success=False)
        self.review(fresh, report('changes_requested', resolutions=[resolution]))
        self.call('complete', 'example', '--owner', 'implementer-1', success=False)

    def test_advisory_findings_are_retained_without_blocking(self):
        self.create(); packet = self.ready(); self.review(packet, report(findings=[finding(severity='advisory')]))
        self.call('complete', 'example', '--owner', 'implementer-1')
        self.assertEqual(self.state()['findings']['F1']['status'], 'open')

    def test_reviewer_can_resolve_false_positive_with_evidence(self):
        self.create(); packet = self.ready(); self.review(packet, report('changes_requested', [finding()]))
        fresh = self.ready()
        self.review(fresh, report(resolutions=[{'id': 'F1', 'status': 'false_positive', 'evidence': 'Requirement excludes empty input; contract C1'}]))
        self.call('complete', 'example', '--owner', 'implementer-1')

    def test_old_round_and_duplicate_verdict_rejected(self):
        self.create(); packet = self.ready(); self.review(packet)
        self.review(packet, success=False)
        fresh = self.ready()
        self.review(packet, success=False)
        self.review(fresh)

    def test_invalid_review_preserves_state(self):
        self.create(); packet = self.ready(); before = self.state()
        bad = report(); bad['quality_review'] = ''
        self.review(packet, bad, success=False)
        self.assertEqual(before, self.state())

    def test_dependencies_block_claim_until_approved(self):
        self.create()
        self.create(contract(depends_on=['example']), name='dependent', claim=False)
        self.call('claim', 'dependent', '--owner', 'next', success=False)
        self.finish()
        self.call('claim', 'dependent', '--owner', 'next')
        self.finish('dependent', 'next')

    def test_missing_dependencies_and_wrong_plan_rejected(self):
        self.create(contract(depends_on=['missing']), success=False)
        self.create()
        self.create(contract(plan='other', depends_on=['example']), name='other', success=False)

    def test_reopened_dependency_invalidates_completed_dependents(self):
        self.create(); self.finish()
        self.create(contract(depends_on=['example']), name='dependent'); self.finish('dependent')
        self.call('reopen', 'example', '--owner', 'implementer-1', '--reason', 'New regression')
        self.call('complete', 'dependent', '--owner', 'implementer-1', success=False)
        self.assertEqual(self.state('dependent')['state'], 'pending')

    def test_plan_requires_current_integration_review(self):
        self.create(); self.finish()
        self.assertFalse(self.call('plan-status', 'example-plan')['complete'])
        self.create(contract(kind='integration', depends_on=['example']), name='integration')
        packet = self.ready('integration')
        self.assertEqual(packet['review_scope'], 'integration')
        self.review(packet)
        self.call('complete', 'integration', '--owner', 'implementer-1')
        self.assertTrue(self.call('plan-status', 'example-plan')['complete'])
        self.source.write_text('answer = 6 * 7\n', encoding='utf-8')
        self.assertFalse(self.call('plan-status', 'example-plan')['complete'])

    def test_integration_must_cover_every_task_and_seals_plan(self):
        self.create(); self.finish()
        self.create(name='second'); self.finish('second')
        self.create(contract(kind='integration', depends_on=['example']), name='bad-integration', success=False)
        self.create(contract(kind='integration', depends_on=['example', 'second']), name='integration')
        self.create(name='late', success=False)

    def test_reopened_ancestor_prevents_descendant_integration(self):
        self.create(); self.finish()
        self.create(contract(depends_on=['example']), name='dependent'); self.finish('dependent')
        self.create(contract(kind='integration', depends_on=['example', 'dependent']), name='integration', claim=False)
        self.call('reopen', 'example', '--owner', 'implementer-1', '--reason', 'Repair prerequisite')
        self.call('claim', 'integration', '--owner', 'integrator', success=False)

    def test_legacy_adoption_preserves_requirements_and_history(self):
        value = {'version': 1, 'workspace': str(self.root), 'tasks': {'legacy': {'id': 'legacy',
                 'objective': 'Return the answer', 'criteria': ['The answer is 42'], 'implementer': 'old-owner',
                 'state': 'completed', 'baseline': gate.fingerprint(self.root), 'attempts': [], 'active_attempt': None}}}
        (self.root / '.review-gate/state.json').write_text(json.dumps(value), encoding='utf-8')
        self.call('complete', 'legacy', '--owner', 'old-owner', success=False)
        self.call('adopt', 'legacy', '--contract', '-', payload=contract())
        task = self.state('legacy')
        self.assertEqual(task['state'], 'pending')
        self.assertEqual(task['legacy_record']['state'], 'completed')
        self.assertIn('old-owner', task['implementers'])

    def test_lock_contention_is_bounded(self):
        store = gate.Store(self.root, lock_timeout=0.05)
        with store.locked():
            with self.assertRaisesRegex(gate.GateError, 'lock timeout'):
                with store.locked():
                    self.fail('Concurrent writer acquired held lock')

    def test_timeout_terminates_descendants(self):
        marker = self.root / '.review-gate/descendant-finished'
        child = 'import time; from pathlib import Path; time.sleep(1.5); Path(%r).touch()' % str(marker)
        parent = 'import subprocess, sys, time; subprocess.Popen([sys.executable, "-c", %r]); time.sleep(30)' % child
        value = contract(parent); value['checks'][0]['timeout'] = 0.25
        self.create(value); self.verify(success=False)
        subprocess.run([sys.executable, '-c', 'import time; time.sleep(1.7)'], check=True, timeout=3)
        self.assertFalse(marker.exists())


if __name__ == '__main__':
    unittest.main()
