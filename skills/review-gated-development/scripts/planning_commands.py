"""Planning CLI commands and atomic handoff to execution tasks."""

import copy
import json
from pathlib import Path
import sys
import uuid

from gate_contract import identifier
from gate_review import apply_report
from gate_store import digest, fingerprint, nonempty, now, require
from planning_model import (approved_receipt, current_revision, fields, planning_status,
                            require_active, require_approval, strings, validate_plan, validate_spec)


ACTIONS = {'planning-create', 'planning-status', 'planning-block', 'planning-resume', 'planning-authorize',
           'planning-supersede', 'spec-submit', 'spec-packet', 'spec-review', 'plan-submit',
           'plan-packet', 'plan-review', 'start-execution', 'spike-finish'}


def read(path, json_value=False):
    value = sys.stdin.read() if path == '-' else Path(path).read_text(encoding='utf-8')
    return json.loads(value) if json_value else value


def history(record, action, **details):
    record['history'].append(dict(action=action, at=now(), **details))


def author_allowed(record, author):
    require(nonempty(author), 'Author ID is required')
    author = author.strip()
    reviewers = {rev['review']['reviewer'] for revisions in record['revisions'].values() for rev in revisions if rev['review']}
    require(author not in reviewers, 'A planning reviewer cannot become an author of the same record')
    return author


def register_author(record, author):
    if author not in record['authors']:
        record['authors'].append(author)


def packet(record, stage):
    require_active(record)
    require(record['path'] != 'spike', 'Spikes use findings, not implementation planning artifacts')
    revision = current_revision(record, stage)
    result = {'id': record['id'], 'stage': stage, 'revision': revision['id'], 'digest': revision['digest'],
              'brief': record['brief'], 'path': record['path'], 'classification_reason': record['classification_reason'],
              'authors': record['authors'], 'artifact': revision['content'], 'findings': record['findings'][stage],
              'review_verdict': revision['review']['verdict'] if revision['review'] else None}
    if stage == 'plan':
        spec = require_approval(record, 'spec')
        require(revision['spec_revision'] == spec['id'] and revision['spec_digest'] == spec['digest'], 'Plan refers to an older spec')
        result['approved_spec'] = {'revision': spec['id'], 'digest': spec['digest'], 'artifact': spec['content']}
    return result


def dispatch_planning(store, data, args, task_factory):
    records = data.get('planning', {})
    if args.action == 'planning-create':
        require(identifier(args.plan) and args.plan not in records, 'Planning ID is invalid or already exists')
        require(not any(task.get('contract', {}).get('plan') == args.plan for task in data['tasks'].values()),
                'Plan ID already belongs to execution history')
        require(nonempty(args.author) and nonempty(args.reason), 'Author and classification reason are required')
        require(args.execution_intent is None or nonempty(args.execution_intent), 'Execution intent must be nonempty when provided')
        require(args.path != 'spike' or args.execution_intent is None, 'A spike cannot authorize implementation')
        brief = read(args.brief)
        require(nonempty(brief), 'Original brief is required')
        record = {'id': args.plan, 'path': args.path, 'brief': brief, 'classification_reason': args.reason,
                  'authors': [args.author.strip()], 'revisions': {'spec': [], 'plan': []},
                  'current': {'spec': None, 'plan': None}, 'findings': {'spec': {}, 'plan': {}},
                  'blocked_reason': None, 'superseded_reason': None, 'spike_result': None,
                  'execution': None, 'execution_intent': args.execution_intent, 'created_at': now(), 'history': []}
        history(record, 'created', author=args.author.strip())
        data.setdefault('planning', {})[args.plan] = record
        data['version'] = 3
        return planning_status(record)
    require(args.plan in records, 'Unknown planning record: ' + args.plan)
    record = records[args.plan]
    if args.action == 'planning-status':
        return planning_status(record)
    if args.action in ('planning-block', 'planning-resume', 'planning-supersede'):
        require(nonempty(args.author) and nonempty(args.reason), 'Author and reason are required')
        require(not record['superseded_reason'], 'Planning record is already superseded')
        if args.action == 'planning-block':
            record['blocked_reason'] = args.reason
        elif args.action == 'planning-resume':
            record['blocked_reason'] = None
        else:
            record['superseded_reason'] = args.reason
        history(record, args.action, author=args.author.strip(), reason=args.reason)
        return planning_status(record)
    require_active(record)
    if args.action == 'spike-finish':
        require(record['path'] == 'spike' and not record['spike_result'], 'Only unfinished spikes accept findings')
        author = author_allowed(record, args.author)
        result = read(args.file, True)
        fields(result, ('findings', 'evidence', 'recommendation', 'limitations'), 'Spike result')
        require(nonempty(result['findings']) and nonempty(result['recommendation']), 'Findings and recommendation are required')
        strings(result['evidence'], 'Spike evidence', required=True)
        strings(result['limitations'], 'Spike limitations')
        register_author(record, author)
        record['spike_result'] = dict(result, author=author, recorded_at=now())
        history(record, 'spike_finished', author=author)
        return planning_status(record)
    require(record['path'] != 'spike', 'A spike cannot submit or execute an implementation plan')
    if args.action == 'planning-authorize':
        require(nonempty(args.author) and nonempty(args.reason), 'Author and user intent are required')
        if record['execution_intent'] is None:
            record['execution_intent'] = args.reason
            history(record, 'implementation_authorized', author=args.author.strip(), reason=args.reason)
        return planning_status(record)
    if args.action.endswith('-submit'):
        require(not record['execution'], 'Imported plans are frozen; supersede and create a replacement plan')
        stage = args.action.split('-')[0]
        author = author_allowed(record, args.author)
        content = read(args.file, True)
        parent = None
        if stage == 'spec':
            validate_spec(content)
        else:
            parent = require_approval(record, 'spec')
            validate_plan(content, record, parent['content'], data['tasks'])
        revision = {'id': str(uuid.uuid4()), 'number': len(record['revisions'][stage]) + 1,
                    'author': author, 'content': content, 'digest': digest(content), 'review': None, 'submitted_at': now()}
        if parent:
            revision.update(spec_revision=parent['id'], spec_digest=parent['digest'])
        register_author(record, author)
        record['revisions'][stage].append(revision)
        record['current'][stage] = revision['id']
        history(record, stage + '_submitted', revision=revision['id'], author=author)
        return packet(record, stage)
    if args.action.endswith('-packet'):
        return packet(record, args.action.split('-')[0])
    if args.action.endswith('-review'):
        stage = args.action.split('-')[0]
        packet(record, stage)
        revision = current_revision(record, stage)
        require(args.revision == revision['id'], 'Planning review revision is stale')
        report = read(args.report, True)
        require(not (isinstance(report, dict) and report.get('verdict') == 'approved' and revision['content']['open_questions']),
                'Resolve open questions before approval')
        adapter = {'implementers': record['authors'], 'findings': record['findings'][stage],
                   'contract_digest': revision['digest'], 'state': 'reviewing', 'active_attempt': revision['id']}
        attempt = {'id': revision['id'], 'snapshot': {'digest': revision['digest']}, 'review': revision['review']}
        review = apply_report(adapter, attempt, args.reviewer, report)
        record['findings'][stage] = adapter['findings']
        revision['review'] = review
        history(record, stage + '_reviewed', revision=revision['id'], reviewer=args.reviewer, verdict=review['verdict'])
        return review
    if args.action == 'start-execution':
        receipt = approved_receipt(record)
        require(nonempty(record['execution_intent']), 'Implementation intent is not recorded; this is planning-only')
        if record['execution']:
            require(record['execution']['receipt'] == receipt, 'Imported planning receipt is stale')
            return record['execution']
        spec = current_revision(record, 'spec')['content']
        content = current_revision(record, 'plan')['content']
        validate_plan(content, record, spec, data['tasks'])
        baseline = fingerprint(store.root)
        staged = {}
        for definition in content['tasks']:
            task = task_factory(definition['id'], copy.deepcopy(definition['contract']), copy.deepcopy(baseline))
            task['planning_receipt'] = dict(receipt)
            task['history'].append({'action': 'imported_from_plan', 'at': now(), 'receipt': dict(receipt)})
            staged[task['id']] = task
        execution = {'receipt': receipt, 'task_ids': list(staged), 'started_at': now()}
        data['tasks'].update(staged)
        record['execution'] = execution
        history(record, 'execution_started', task_ids=list(staged))
        return execution
    raise RuntimeError('Unsupported planning action')


def add_planning_parsers(actions):
    create = actions.add_parser('planning-create')
    create.add_argument('plan')
    create.add_argument('--path', choices=('spike', 'bounded', 'architectural'), required=True)
    create.add_argument('--reason', required=True)
    create.add_argument('--author', required=True)
    create.add_argument('--brief', required=True)
    create.add_argument('--execution-intent', metavar='REASON')
    for name in ('planning-status', 'spec-packet', 'plan-packet', 'start-execution'):
        actions.add_parser(name).add_argument('plan')
    for name in ('planning-block', 'planning-resume', 'planning-supersede', 'planning-authorize'):
        action = actions.add_parser(name)
        action.add_argument('plan')
        action.add_argument('--author', required=True)
        action.add_argument('--reason', required=True)
    for name in ('spec-submit', 'plan-submit', 'spike-finish'):
        action = actions.add_parser(name)
        action.add_argument('plan')
        action.add_argument('--author', required=True)
        action.add_argument('--file', required=True)
    for name in ('spec-review', 'plan-review'):
        action = actions.add_parser(name)
        action.add_argument('plan')
        action.add_argument('--revision', required=True)
        action.add_argument('--reviewer', required=True)
        action.add_argument('--report', required=True)
