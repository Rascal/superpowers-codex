import json
from pathlib import Path
import subprocess
import sys
import unittest

from test_review_gate import GateCase, SCRIPTS, contract, finding, report


PLAN = 'planned-feature'
LEGACY = Path.home() / '.codex/plugins/cache/superpowers-codex/superpowers-codex/0.2.2/skills/review-gated-development/scripts/review_gate.py'


def spec_document():
    return {'goal': 'Return the answer', 'non_goals': ['No unrelated refactor'],
            'requirements': [{'id': 'R1', 'description': 'The answer is 42'}],
            'constraints': ['Do not mutate unrelated files'], 'user_decisions': ['Independent review is required'],
            'approach': 'Preserve the existing app module and verify its result.',
            'alternatives': [], 'risks': ['Avoid altering unrelated behavior'], 'open_questions': []}


def plan_document():
    return {'summary': 'Implement the answer and review the combined result.',
            'tasks': [{'id': 'build', 'files': ['app.py'], 'steps': ['Implement the required answer and its regression.'],
                       'contract': contract(plan=PLAN)},
                      {'id': 'integrate', 'files': [], 'steps': ['Verify and independently review the whole change.'],
                       'contract': contract(plan=PLAN, kind='integration', depends_on=['build'])}],
            'coverage': [{'requirement': 'R1', 'task': 'build', 'criteria': ['C1']}], 'open_questions': []}


class PlanningTests(GateCase):
    def register(self, path='bounded', name=PLAN, success=True, execute=True):
        brief = self.root / '.review-gate/brief.md'
        brief.write_text('Plan an existing answer module change. The result must be 42.', encoding='utf-8')
        args = ['planning-create', name, '--path', path, '--reason', 'Existing small behavior change',
                '--author', 'planner', '--brief', str(brief)]
        if execute and path != 'spike':
            args += ['--execution-intent', 'User requested implementation']
        return self.call(*args, success=success)

    def submit(self, stage, value=None, author='planner', success=True):
        value = value if value is not None else (spec_document() if stage == 'spec' else plan_document())
        return self.call(stage + '-submit', PLAN, '--author', author, '--file', '-', payload=value, success=success)

    def review_artifact(self, stage, packet, value=None, reviewer=None, success=True):
        return self.call(stage + '-review', PLAN, '--revision', packet['revision'],
                         '--reviewer', reviewer or stage + '-reviewer', '--report', '-',
                         payload=value if value is not None else report(), success=success)

    def spec_ready(self):
        packet = self.submit('spec')
        self.review_artifact('spec', packet)
        return packet

    def planning_ready(self):
        self.register()
        self.spec_ready()
        packet = self.submit('plan')
        self.review_artifact('plan', packet)
        return packet

    def test_full_pipeline_and_integration_completion(self):
        self.planning_ready()
        self.assertEqual(self.call('planning-status', PLAN)['phase'], 'ready')
        execution = self.call('start-execution', PLAN)
        self.assertEqual(execution['task_ids'], ['build', 'integrate'])
        self.assertEqual(self.state('build')['execution_mode'], 'planned')
        self.call('claim', 'build', '--owner', 'implementer-1')
        packet = self.ready('build')
        self.assertEqual(packet['planning']['spec']['requirements'][0]['id'], 'R1')
        self.review(packet)
        self.call('complete', 'build', '--owner', 'implementer-1')
        self.call('claim', 'integrate', '--owner', 'implementer-1')
        self.finish('integrate')
        self.assertTrue(self.call('plan-status', PLAN)['complete'])

    def test_plan_cannot_precede_spec_review(self):
        self.register()
        self.submit('plan', success=False)
        self.submit('spec')
        self.submit('plan', success=False)
        self.call('start-execution', PLAN, success=False)
        self.assertEqual(self.call('list'), [])

    def test_execution_cannot_precede_plan_review(self):
        self.register(); self.spec_ready(); self.submit('plan')
        self.call('start-execution', PLAN, success=False)
        self.assertEqual(self.call('list'), [])

    def test_planning_only_can_finish_without_execution_or_stop_continuation(self):
        self.register(execute=False); self.spec_ready()
        packet = self.submit('plan'); self.review_artifact('plan', packet)
        status = self.call('plan-status', PLAN)
        self.assertTrue(status['complete'])
        self.assertEqual(status['completion_scope'], 'planning')
        self.call('start-execution', PLAN, success=False)
        self.call('bind', '--session', 'planning-session', '--plan', PLAN)
        payload = {'hook_event_name': 'Stop', 'session_id': 'planning-session', 'cwd': str(self.root)}
        result = subprocess.run([sys.executable, '-B', str(SCRIPTS / 'codex_hook.py')], input=json.dumps(payload),
                                text=True, capture_output=True, timeout=10)
        self.assertEqual(json.loads(result.stdout), {})
        self.assertEqual(self.call('list'), [])
        self.call('planning-authorize', PLAN, '--author', 'planner', '--reason', 'User now requested implementation')
        self.assertFalse(self.call('plan-status', PLAN)['complete'])
        self.assertEqual(self.call('list'), [])
        self.call('start-execution', PLAN)

    def test_authorization_cannot_bypass_block_or_supersession(self):
        self.register(execute=False)
        self.call('planning-block', PLAN, '--author', 'planner', '--reason', 'Need decision')
        self.call('planning-authorize', PLAN, '--author', 'planner', '--reason', 'Implement', success=False)
        self.call('planning-resume', PLAN, '--author', 'planner', '--reason', 'Decision received')
        self.call('planning-supersede', PLAN, '--author', 'planner', '--reason', 'Use a replacement')
        self.call('planning-authorize', PLAN, '--author', 'planner', '--reason', 'Implement', success=False)

    def test_spike_rejects_implementation_intent(self):
        self.register(path='spike')
        self.call('planning-authorize', PLAN, '--author', 'planner', '--reason', 'Implement', success=False)
        self.call('planning-create', 'bad-spike', '--path', 'spike', '--reason', 'Probe', '--author', 'planner',
                  '--brief', str(self.root / '.review-gate/brief.md'), '--execution-intent', 'Implement', success=False)

    def test_both_artifact_types_reject_self_review(self):
        self.register(); spec = self.submit('spec')
        self.review_artifact('spec', spec, reviewer='planner', success=False)
        self.review_artifact('spec', spec)
        plan = self.submit('plan', author='second-planner')
        self.review_artifact('plan', plan, reviewer='planner', success=False)
        self.review_artifact('plan', plan, reviewer='second-planner', success=False)

    def test_reviewer_cannot_later_author_same_record(self):
        self.register(); self.spec_ready()
        self.submit('plan', author='spec-reviewer', success=False)

    def test_duplicate_report_rejected(self):
        self.register(); packet = self.spec_ready()
        self.review_artifact('spec', packet, success=False)

    def test_byte_identical_spec_revision_invalidates_downstream_plan(self):
        old_plan = self.planning_ready()
        old_spec_id = old_plan['approved_spec']['revision']
        fresh_spec = self.submit('spec')
        self.assertNotEqual(fresh_spec['revision'], old_spec_id)
        self.assertEqual(fresh_spec['digest'], old_plan['approved_spec']['digest'])
        self.review_artifact('spec', dict(fresh_spec, revision=old_spec_id), success=False)
        self.call('start-execution', PLAN, success=False)
        self.review_artifact('spec', fresh_spec)
        self.assertEqual(self.call('planning-status', PLAN)['phase'], 'drafting_plan')
        self.call('plan-packet', PLAN, success=False)
        self.call('start-execution', PLAN, success=False)
        fresh_plan = self.submit('plan')
        self.review_artifact('plan', old_plan, success=False)
        self.review_artifact('plan', fresh_plan)
        self.call('start-execution', PLAN)

    def test_plan_resubmission_requires_fresh_review(self):
        old = self.planning_ready()
        current = self.submit('plan')
        self.review_artifact('plan', old, success=False)
        self.call('start-execution', PLAN, success=False)
        self.review_artifact('plan', current)
        self.call('start-execution', PLAN)

    def test_spec_findings_must_be_resolved(self):
        self.register(); packet = self.submit('spec')
        self.review_artifact('spec', packet, report('changes_requested', [finding()]))
        self.assertEqual(self.call('planning-status', PLAN)['review_verdicts']['spec'], 'changes_requested')
        self.submit('plan', success=False)
        fresh = self.submit('spec')
        self.review_artifact('spec', fresh, success=False)
        self.review_artifact('spec', fresh, report(resolutions=[{'id': 'F1', 'status': 'addressed', 'evidence': 'Requirement R1 clarified'}]))
        self.submit('plan')

    def test_plan_findings_must_be_resolved(self):
        self.register(); self.spec_ready(); packet = self.submit('plan')
        self.review_artifact('plan', packet, report('changes_requested', [finding()]))
        self.call('start-execution', PLAN, success=False)
        fresh = self.submit('plan')
        self.review_artifact('plan', fresh, success=False)
        self.review_artifact('plan', fresh, report(resolutions=[{'id': 'F1', 'status': 'false_positive', 'evidence': 'Existing check already covers the boundary'}]))
        self.call('start-execution', PLAN)

    def test_open_spec_questions_block_approval(self):
        self.register()
        value = spec_document(); value['open_questions'] = ['Which result is correct?']
        packet = self.submit('spec', value)
        self.review_artifact('spec', packet, success=False)

    def test_open_plan_questions_block_approval(self):
        self.register(); self.spec_ready()
        value = plan_document(); value['open_questions'] = ['Which verification fixture should be used?']
        packet = self.submit('plan', value)
        self.review_artifact('plan', packet, success=False)
        self.call('start-execution', PLAN, success=False)

    def test_coverage_gaps_and_wrong_criterion_rejected(self):
        self.register(); self.spec_ready()
        variants = []
        value = plan_document(); value['coverage'] = []; variants.append(value)
        value = plan_document(); value['coverage'][0]['criteria'] = ['missing']; variants.append(value)
        value = plan_document(); value['coverage'][0]['requirement'] = 'R2'; variants.append(value)
        value = plan_document(); value['coverage'][0]['task'] = 'integrate'; variants.append(value)
        for value in variants:
            with self.subTest(value=value): self.submit('plan', value, success=False)
        self.assertEqual(self.call('planning-status', PLAN)['phase'], 'drafting_plan')

    def test_every_implementation_task_traces_to_requirement(self):
        self.register(); self.spec_ready()
        value = plan_document()
        value['tasks'].insert(1, {'id': 'extra', 'files': ['extra.py'], 'steps': ['Add extra behavior'], 'contract': contract(plan=PLAN)})
        value['tasks'][-1]['contract']['depends_on'].append('extra')
        self.submit('plan', value, success=False)

    def test_constraints_and_decisions_must_be_inherited(self):
        self.register(); self.spec_ready()
        for name in ('constraints', 'user_decisions'):
            value = plan_document(); value['tasks'][0]['contract'][name] = []
            self.submit('plan', value, success=False)

    def test_invalid_graph_and_integration_scope_rejected(self):
        self.register(); self.spec_ready()
        variants = []
        value = plan_document(); value['tasks'].reverse(); variants.append(value)
        value = plan_document(); value['tasks'][0]['contract']['depends_on'] = ['build']; variants.append(value)
        value = plan_document(); value['tasks'][-1]['contract']['depends_on'] = []; variants.append(value)
        value = plan_document(); value['tasks'].pop(); variants.append(value)
        for value in variants:
            with self.subTest(value=value): self.submit('plan', value, success=False)

    def test_plans_need_explicit_relative_files_and_actionable_steps(self):
        self.register(); self.spec_ready()
        for files in ([], ['/tmp/app.py'], ['../app.py'], ['C:/app.py'], ['src/*.py'], ['src/../app.py']):
            value = plan_document(); value['tasks'][0]['files'] = files
            self.submit('plan', value, success=False)
        value = plan_document(); value['tasks'][0]['steps'] = []
        self.submit('plan', value, success=False)

    def test_portable_paths_reject_control_characters_and_windows_devices(self):
        self.register(); self.spec_ready()
        invalid = ['src/a\x00b.py', 'src/line\nbreak.py', 'src/control\x7f.py',
                   'src/result:stream.py', 'src/a<b.py', 'src/a>b.py', 'src/a"b.py',
                   'src/a|b.py', 'src/NUL.py', 'src/con', 'src/PRN.txt', 'src/AUX',
                   'src/COM1.py', 'src/lpt9.log', 'src/COM¹.py', 'src/LPT²',
                   'src/result.', 'src/result. ', 'src/name /file.py', 'src/NUL .py']
        for path in invalid:
            with self.subTest(path=path):
                value = plan_document(); value['tasks'][0]['files'] = [path]
                self.submit('plan', value, success=False)

    def test_portable_paths_allow_unicode_and_literal_route_brackets(self):
        self.register(); self.spec_ready()
        value = plan_document(); value['tasks'][0]['files'] = ['src/[slug]/route.py', 'src/привет.py']
        self.submit('plan', value)

    def test_direct_creation_requires_explicit_escape_and_records_it(self):
        self.call('create', 'external', '--contract', '-', payload=contract(), success=False)
        self.create(name='external', claim=False)
        task = self.state('external')
        self.assertEqual(task['execution_mode'], 'execution-only')
        self.assertEqual(task['history'][0]['execution_only_reason'], 'Isolated execution test')

    def test_direct_creation_cannot_bypass_managed_planning(self):
        self.register()
        self.create(contract(plan=PLAN), name='bypass', claim=False, success=False)
        self.assertEqual(self.call('list'), [])

    def test_planning_id_cannot_take_over_execution_history(self):
        self.create(claim=False)
        self.register(name='example-plan', success=False)

    def test_start_is_atomic_on_task_id_collision(self):
        self.planning_ready()
        self.create(name='integrate', claim=False)
        self.call('start-execution', PLAN, success=False)
        self.assertEqual([task['id'] for task in self.call('list')], ['integrate'])

    def test_repeated_start_is_idempotent(self):
        self.planning_ready()
        first = self.call('start-execution', PLAN)
        second = self.call('start-execution', PLAN)
        self.assertEqual(first, second)
        self.assertEqual(len(self.call('list')), 2)

    def test_imported_artifacts_are_frozen(self):
        self.planning_ready(); self.call('start-execution', PLAN)
        self.submit('spec', success=False)
        self.submit('plan', success=False)

    def test_supersession_rejects_execution_and_same_owner_claim(self):
        self.planning_ready(); self.call('start-execution', PLAN)
        self.call('claim', 'build', '--owner', 'implementer-1')
        self.call('planning-supersede', PLAN, '--author', 'planner', '--reason', 'Requirements changed')
        for action in ('claim', 'verify', 'request-review', 'complete'):
            error = self.call(action, 'build', '--owner', 'implementer-1', success=False)
            self.assertIn('superseded', error['error'])
        self.call('packet', 'build', success=False)
        self.call('review', 'build', '--round', 'stale', '--reviewer', 'reviewer', '--report', '-', payload=report(), success=False)
        self.call('start-execution', PLAN, success=False)
        self.assertFalse(self.call('plan-status', PLAN)['complete'])

    def test_recovery_and_release_do_not_restore_superseded_eligibility(self):
        self.planning_ready(); self.call('start-execution', PLAN)
        self.call('claim', 'build', '--owner', 'implementer-1')
        self.call('planning-supersede', PLAN, '--author', 'planner', '--reason', 'Replace plan')
        self.call('recover', 'build', '--owner', 'implementer-1', '--new-owner', 'replacement', '--reason', 'Original agent unavailable')
        self.verify('build', owner='replacement', success=False)
        self.call('release', 'build', '--owner', 'replacement', '--reason', 'Free workspace')
        self.call('claim', 'build', '--owner', 'replacement', success=False)
        self.assertIsNone(self.state('build')['owner'])

    def test_reopen_does_not_restore_superseded_eligibility(self):
        self.planning_ready(); self.call('start-execution', PLAN)
        self.call('claim', 'build', '--owner', 'implementer-1'); self.finish('build')
        self.call('planning-supersede', PLAN, '--author', 'planner', '--reason', 'Replace plan')
        self.call('reopen', 'build', '--owner', 'implementer-1', '--reason', 'Revisit implementation')
        self.call('claim', 'build', '--owner', 'implementer-1', success=False)

    def test_planning_block_resume_and_hooks_before_tasks_exist(self):
        self.register()
        self.call('bind', '--session', 'planning-session', '--plan', PLAN)
        self.call('planning-block', PLAN, '--author', 'planner', '--reason', 'Need a user decision')
        self.submit('spec', success=False)
        payload = {'hook_event_name': 'Stop', 'session_id': 'planning-session', 'cwd': str(self.root)}
        result = subprocess.run([sys.executable, '-B', str(SCRIPTS / 'codex_hook.py')], input=json.dumps(payload),
                                text=True, capture_output=True, timeout=10)
        response = json.loads(result.stdout)
        self.assertIn('systemMessage', response)
        self.assertNotIn('decision', response)
        self.call('planning-resume', PLAN, '--author', 'planner', '--reason', 'Decision received')
        self.spec_ready()

    def test_spike_completes_with_evidence_but_never_imports_tasks(self):
        self.register(path='spike')
        self.submit('spec', success=False)
        self.call('spike-finish', PLAN, '--author', 'planner', '--file', '-', payload={
            'findings': 'The current function returns 42.', 'evidence': ['python probe returned 42'],
            'recommendation': 'Keep the existing implementation.', 'limitations': []})
        self.assertTrue(self.call('plan-status', PLAN)['complete'])
        self.call('start-execution', PLAN, success=False)
        self.assertEqual(self.call('list'), [])

    def test_spike_requires_actual_report_fields(self):
        self.register(path='spike')
        self.call('spike-finish', PLAN, '--author', 'planner', '--file', '-', payload={
            'findings': 'It works', 'evidence': [], 'recommendation': 'Proceed', 'limitations': []}, success=False)

    def test_planning_upgrades_legacy_store_and_preserves_task_history(self):
        self.create(claim=False)
        path = self.root / '.review-gate/state.json'
        data = json.loads(path.read_text()); data['version'] = 2
        data['tasks']['example'].pop('execution_only_reason')
        path.write_text(json.dumps(data), encoding='utf-8')
        before = path.read_bytes()
        self.assertEqual(self.state()['execution_mode'], 'legacy')
        self.assertEqual(before, path.read_bytes())
        self.register()
        data = json.loads(path.read_text())
        self.assertEqual(data['version'], 3)
        self.assertIn('example', data['tasks'])

    @unittest.skipUnless(LEGACY.is_file(), 'Released v0.2.2 CLI is not installed on this host')
    def test_released_old_cli_rejects_planning_store(self):
        self.register()
        before = (self.root / '.review-gate/state.json').read_bytes()
        result = subprocess.run([sys.executable, '-B', str(LEGACY), '--workspace', str(self.root), 'list'],
                                text=True, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 1)
        self.assertIn('Unsupported task store', result.stderr)
        self.assertEqual(before, (self.root / '.review-gate/state.json').read_bytes())


if __name__ == '__main__':
    unittest.main()
