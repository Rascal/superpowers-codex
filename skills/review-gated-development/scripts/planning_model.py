"""Planning artifact schemas, approval receipts, and lifecycle status."""

from pathlib import PurePosixPath, PureWindowsPath
import unicodedata

from gate_contract import identifier, validate_contract, validate_dependency_declarations
from gate_store import digest, nonempty, require


STAGES = ('spec', 'plan')
RESERVED_NAMES = {'CON', 'PRN', 'AUX', 'NUL'} | {
    prefix + suffix for prefix in ('COM', 'LPT') for suffix in '123456789¹²³'
}


def fields(value, expected, label):
    require(isinstance(value, dict) and set(value) == set(expected), label + ' requires exactly: ' + ', '.join(sorted(expected)))


def strings(value, label, required=False):
    require(isinstance(value, list) and all(nonempty(item) for item in value), label + ' must be nonempty strings')
    require(not required or bool(value), label + ' cannot be empty')


def validate_spec(content):
    fields(content, ('goal', 'non_goals', 'requirements', 'constraints', 'user_decisions', 'approach',
                     'alternatives', 'risks', 'open_questions'), 'Spec')
    require(nonempty(content['goal']) and nonempty(content['approach']), 'Spec goal and approach are required')
    for name in ('non_goals', 'constraints', 'user_decisions', 'alternatives', 'risks', 'open_questions'):
        strings(content[name], name)
    require(isinstance(content['requirements'], list) and content['requirements'], 'Spec requires observable requirements')
    seen = set()
    for item in content['requirements']:
        fields(item, ('id', 'description'), 'Requirement')
        require(identifier(item['id']) and item['id'] not in seen, 'Requirement IDs must be valid and unique')
        require(nonempty(item['description']), 'Requirement description is required')
        seen.add(item['id'])


def validate_file_path(path):
    require(not PurePosixPath(path).is_absolute() and not PureWindowsPath(path).drive
            and not any(char in '<>:"\\|?*' or unicodedata.category(char) in ('Cc', 'Cs') for char in path),
            'Use portable relative file paths: ' + repr(path))
    for part in path.split('/'):
        require(part not in ('', '.', '..') and part == part.strip(' ') and not part.endswith('.')
                and part.split('.', 1)[0].rstrip(' ').upper() not in RESERVED_NAMES,
                'Invalid or reserved path component: ' + repr(part))


def validate_plan(content, record, spec, existing_tasks):
    fields(content, ('summary', 'tasks', 'coverage', 'open_questions'), 'Plan')
    require(nonempty(content['summary']), 'Plan summary is required')
    strings(content['open_questions'], 'open_questions')
    require(isinstance(content['tasks'], list) and content['tasks'], 'Plan requires tasks')
    staged = dict(existing_tasks)
    definitions = {}
    for item in content['tasks']:
        fields(item, ('id', 'files', 'steps', 'contract'), 'Plan task')
        name = item['id']
        require(identifier(name) and name not in staged, 'Task ID is invalid or already exists: ' + str(name))
        validate_contract(item['contract'])
        require(item['contract']['plan'] == record['id'], 'Task contract uses another plan ID')
        strings(item['files'], 'Task files', required=item['contract']['kind'] == 'implementation')
        require(len(set(item['files'])) == len(item['files']), 'Task file paths must be unique')
        for path in item['files']:
            validate_file_path(path)
        strings(item['steps'], 'Task steps', required=True)
        require(set(spec['constraints']) <= set(item['contract']['constraints']), 'Task omits spec constraints')
        require(set(spec['user_decisions']) <= set(item['contract']['user_decisions']), 'Task omits user decisions')
        validate_dependency_declarations(item['contract'], staged)
        staged[name] = {'id': name, 'version': 2, 'contract': item['contract']}
        definitions[name] = item
    integrations = [item for item in content['tasks'] if item['contract']['kind'] == 'integration']
    require(len(integrations) == 1 and content['tasks'][-1] is integrations[0], 'Plan needs exactly one final integration task')
    requirement_ids = {item['id'] for item in spec['requirements']}
    covered_requirements, covered_tasks, seen = set(), set(), set()
    require(isinstance(content['coverage'], list), 'Coverage must be an array')
    for link in content['coverage']:
        fields(link, ('requirement', 'task', 'criteria'), 'Coverage link')
        require(link['requirement'] in requirement_ids and link['task'] in definitions, 'Unknown requirement or task in coverage')
        strings(link['criteria'], 'Coverage criteria', required=True)
        require(len(set(link['criteria'])) == len(link['criteria']), 'Duplicate criteria in coverage')
        task = definitions[link['task']]['contract']
        require(set(link['criteria']) <= {item['id'] for item in task['criteria']}, 'Unknown criterion in coverage')
        key = (link['requirement'], link['task'])
        require(key not in seen, 'Duplicate requirement/task coverage link')
        seen.add(key)
        if task['kind'] == 'implementation':
            covered_requirements.add(link['requirement'])
            covered_tasks.add(link['task'])
    require(covered_requirements == requirement_ids, 'Every requirement needs implementation criterion coverage')
    require(covered_tasks == {name for name, item in definitions.items() if item['contract']['kind'] == 'implementation'},
            'Every implementation task must trace to a requirement')


def current_revision(record, stage, required=True):
    name = record['current'][stage]
    revision = next((item for item in record['revisions'][stage] if item['id'] == name), None)
    require(not required or revision is not None, 'No current ' + stage + ' revision')
    if revision:
        require(digest(revision['content']) == revision['digest'], 'Stored ' + stage + ' revision changed')
    return revision


def require_active(record):
    require(not record['superseded_reason'], 'Planning record was superseded: ' + str(record['superseded_reason']))
    require(not record['blocked_reason'], 'Planning is blocked: ' + str(record['blocked_reason']))


def require_approval(record, stage):
    revision = current_revision(record, stage)
    review = revision['review']
    require(not revision['content']['open_questions'], 'Resolve open questions before approval')
    require(review and review['verdict'] == 'approved', 'Current ' + stage + ' needs independent approval')
    require(review['reviewer'] not in record['authors'], 'Planning author cannot approve their own artifacts')
    require(review['snapshot'] == revision['digest'] and review['contract_digest'] == revision['digest'], 'Planning approval is stale')
    require(not any(item['severity'] == 'blocking' and item['status'] == 'open' for item in record['findings'][stage].values()),
            'Blocking ' + stage + ' findings remain open')
    return revision


def approved_receipt(record):
    require_active(record)
    require(record['path'] != 'spike', 'A spike cannot start implementation')
    spec = require_approval(record, 'spec')
    plan = require_approval(record, 'plan')
    require(plan['spec_revision'] == spec['id'] and plan['spec_digest'] == spec['digest'], 'Plan was reviewed against an older spec revision')
    return {'spec_revision': spec['id'], 'spec_digest': spec['digest'], 'plan_revision': plan['id'], 'plan_digest': plan['digest']}


def require_task_planning(data, task):
    record = data.get('planning', {}).get(task['contract']['plan'])
    if record is None:
        require(not task.get('planning_receipt'), 'Task planning record is missing')
        return
    receipt = approved_receipt(record)
    require(nonempty(record['execution_intent']), 'Implementation intent is not recorded')
    require(record['execution'] and task['id'] in record['execution']['task_ids'], 'Task was not imported from the approved plan')
    require(task.get('planning_receipt') == receipt == record['execution']['receipt'], 'Task planning receipt is stale')


def planning_context(data, task):
    record = data.get('planning', {}).get(task['contract']['plan'])
    if record is None:
        return None
    require_task_planning(data, task)
    spec = current_revision(record, 'spec')
    plan = current_revision(record, 'plan')
    return {'brief': record['brief'], 'path': record['path'], 'spec': spec['content'],
            'receipt': task['planning_receipt'],
            'task_definition': next(item for item in plan['content']['tasks'] if item['id'] == task['id'])}


def planning_status(record):
    if record['superseded_reason']:
        phase = 'superseded'
    elif record['blocked_reason']:
        phase = 'blocked'
    elif record['path'] == 'spike':
        phase = 'spike_complete' if record['spike_result'] else 'investigating'
    else:
        spec = current_revision(record, 'spec', required=False)
        plan = current_revision(record, 'plan', required=False)
        if spec is None:
            phase = 'drafting_spec'
        elif not spec['review'] or spec['review']['verdict'] != 'approved':
            phase = 'spec_review'
        elif plan is None or plan['spec_revision'] != spec['id']:
            phase = 'drafting_plan'
        elif not plan['review'] or plan['review']['verdict'] != 'approved':
            phase = 'plan_review'
        else:
            approved_receipt(record)
            phase = 'executing' if record['execution'] else 'ready'
    verdicts = {}
    for stage in STAGES:
        revision = current_revision(record, stage, required=False)
        verdicts[stage] = revision['review']['verdict'] if revision and revision['review'] else None
    return {'id': record['id'], 'path': record['path'], 'phase': phase, 'review_verdicts': verdicts,
            'execution_intent': record['execution_intent'],
            'current': record['current'], 'blocked_reason': record['blocked_reason'],
            'superseded_reason': record['superseded_reason'], 'authors': record['authors']}
