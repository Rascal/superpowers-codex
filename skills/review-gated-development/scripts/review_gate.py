#!/usr/bin/env python3
"""Review-gated tasks with immutable verification contracts."""

import argparse
import copy
import json
from pathlib import Path
import sys
import uuid

from gate_contract import identifier, validate_contract, validate_dependency_declarations, verify_contract
from gate_review import apply_report
from gate_store import GateError, Store, digest, fingerprint, nonempty, now, require


def read_json(path):
    return json.loads(sys.stdin.read() if path == "-" else Path(path).read_text(encoding="utf-8"))


def event(task, action, **fields):
    task["history"].append(dict(action=action, at=now(), **fields))


def active_attempt(task):
    require(task.get("active_attempt") is not None, "Task has no current verification evidence")
    attempt = next((item for item in task["attempts"] if item["id"] == task["active_attempt"]), None)
    require(attempt is not None, "Invalid active attempt")
    return attempt


def check_contract(task):
    require(task.get("version") == 2, "Legacy task is read-only; adopt it with a fixed contract before continuing")
    require(digest(task["contract"]) == task["contract_digest"], "Stored contract changed; create a new task for changed requirements")


def require_owner(task, owner):
    require(nonempty(owner) and task["owner"] == owner.strip(), "Only the recorded owner may perform this action")


def dependency_receipts(task, tasks, visiting=None):
    visiting = set() if visiting is None else set(visiting)
    require(task["id"] not in visiting, "Dependency cycle detected")
    visiting.add(task["id"])
    receipts = {}
    for name in task["contract"]["depends_on"]:
        require(name in tasks, "Missing dependency: " + name)
        dependency = tasks[name]
        check_contract(dependency)
        require(dependency["state"] == "completed", "Dependency is incomplete: " + name)
        attempt = active_attempt(dependency)
        require(attempt["dependencies"] == dependency_receipts(dependency, tasks, visiting), "Dependency approval is stale: " + name)
        require(attempt["review"] and attempt["review"]["verdict"] == "approved", "Dependency has no approval: " + name)
        require(attempt["verification"]["status"] == "passed", "Dependency verification did not pass: " + name)
        receipts[name] = {"generation": dependency["generation"], "round": attempt["id"], "snapshot": attempt["snapshot"]["digest"]}
    return receipts


def invalidate(task, reason):
    if task["state"] == "completed":
        task["owner"] = None
        task["generation"] += 1
    task["active_attempt"] = None
    task["state"] = "implementing" if task["owner"] else "pending"
    event(task, "evidence_invalidated", reason=reason)


def require_current(task, attempt, store, tasks):
    try:
        require(attempt["contract_digest"] == task["contract_digest"], "Contract evidence is stale")
        require(fingerprint(store.root)["digest"] == attempt["snapshot"]["digest"], "Workspace changed; approval and verification are stale")
        require(attempt["dependencies"] == dependency_receipts(task, tasks), "Dependency evidence is stale")
    except GateError as error:
        invalidate(task, str(error))
        raise


def new_task(task_id, contract, baseline):
    return {"id": task_id, "version": 2, "contract": contract, "contract_digest": digest(contract),
            "owner": None, "implementers": [], "state": "pending", "created_at": now(), "generation": 1,
            "baseline": baseline, "attempts": [], "active_attempt": None, "findings": {}, "history": []}


def review_packet(task, attempt, store, tasks):
    previous = next((item for item in reversed(task["attempts"]) if item["id"] != attempt["id"] and item["review"]), None)
    before = (previous["snapshot"] if previous else task["baseline"])["files"]
    after = attempt["snapshot"]["files"]
    changed = sorted(name for name in before.keys() | after.keys() if before.get(name) != after.get(name))
    dependency_findings = {name: tasks[name]["findings"] for name in task["contract"]["depends_on"]}
    return {"task_id": task["id"], "workspace": str(store.root), "contract": task["contract"],
            "contract_digest": task["contract_digest"], "round": attempt["id"], "owner": task["owner"],
            "implementers": task["implementers"], "snapshot": attempt["snapshot"], "verification": attempt["verification"],
            "review_scope": "integration" if task["contract"]["kind"] == "integration" else ("fix" if previous else "task"),
            "previous_review_snapshot": previous["snapshot"]["digest"] if previous else None,
            "changed_since_review": changed, "findings": task["findings"],
            "dependencies": attempt["dependencies"], "dependency_findings": dependency_findings}


def plan_status(data, plan, root):
    tasks = [task for task in data["tasks"].values() if task.get("version") == 2 and task["contract"]["plan"] == plan]
    require(tasks, "Unknown plan: " + plan)
    issues = []
    integration = [task for task in tasks if task["contract"]["kind"] == "integration"]
    if not integration:
        issues.append("Final integration task has not been created")
    for task in tasks:
        check_contract(task)
        if task["state"] != "completed":
            issues.append(task["id"] + ": " + task["state"])
            continue
        attempt = active_attempt(task)
        try:
            require(attempt["dependencies"] == dependency_receipts(task, data["tasks"]), "Dependency evidence is stale")
            require(attempt["review"] and attempt["review"]["verdict"] == "approved", "Missing approval")
            require(attempt["verification"]["status"] == "passed", "Missing passing verification")
            if task["contract"]["kind"] == "integration":
                require(fingerprint(root)["digest"] == attempt["snapshot"]["digest"], "Final workspace changed after integration review")
        except GateError as error:
            issues.append(task["id"] + ": " + str(error))
    return {"plan": plan, "complete": not issues, "issues": issues,
            "blocked": [task["id"] for task in tasks if task["state"] == "blocked"],
            "tasks": [{"id": task["id"], "state": task["state"], "owner": task["owner"]} for task in tasks]}


def dispatch(store, data, args):
    tasks = data["tasks"]
    if args.action in ("create", "adopt"):
        require(identifier(args.id), "Invalid task ID")
        contract = read_json(args.contract)
        validate_contract(contract)
        legacy = None
        if args.action == "adopt":
            require(args.id in tasks and tasks[args.id].get("version") == 1, "Only legacy tasks can be adopted")
            legacy = tasks[args.id]
            require(legacy["objective"] == contract["objective"] and legacy["criteria"] == [item["description"] for item in contract["criteria"]], "Adoption must preserve the original objective and criteria")
        else:
            require(args.id not in tasks, "Task already exists")
        validate_dependency_declarations(contract, tasks)
        task = new_task(args.id, contract, legacy["baseline"] if legacy else fingerprint(store.root))
        if legacy:
            task["legacy_record"] = legacy
            task["implementers"].append(legacy["implementer"].strip())
        event(task, args.action)
        tasks[args.id] = task
        return task
    if args.action == "list":
        return [{"id": task["id"], "state": task["state"], "version": task.get("version", 1), "owner": task.get("owner")} for task in tasks.values()]
    if args.action == "plan-status":
        return plan_status(data, args.plan, store.root)
    if args.action == "bind":
        require(nonempty(args.session), "Session ID is required")
        plan_status(data, args.plan, store.root)
        require(args.session not in data["bindings"] or data["bindings"][args.session] == args.plan, "Session already bound; unbind explicitly first")
        data["bindings"][args.session] = args.plan
        return {"session": args.session, "plan": args.plan}
    if args.action == "unbind":
        require(args.session in data["bindings"], "Session is not bound")
        return {"session": args.session, "plan": data["bindings"].pop(args.session)}
    require(args.id in tasks, "Unknown task: " + args.id)
    task = tasks[args.id]
    if args.action == "show":
        return task
    check_contract(task)
    if args.action == "claim":
        require(nonempty(args.owner), "Owner is required")
        if task["owner"]:
            require_owner(task, args.owner)
            return task
        require(task["state"] == "pending", "Task cannot be claimed in this state")
        dependency_receipts(task, tasks)
        others = [other["id"] for other in tasks.values() if other.get("version") == 2 and other["owner"] and other["state"] != "completed"]
        require(not others, "Workspace is already owned by: " + ", ".join(others))
        task["owner"] = args.owner.strip()
        if task["owner"] not in task["implementers"]:
            task["implementers"].append(task["owner"])
        task["state"] = "implementing"
        event(task, "claimed", owner=task["owner"])
        return task
    if args.action in ("release", "recover", "block", "reopen"):
        require_owner(task, args.owner)
        require(nonempty(args.reason), "Reason is required")
        if args.action == "recover":
            require(nonempty(args.new_owner) and args.new_owner.strip() != task["owner"], "Recovery needs a different owner")
            require(task["state"] != "completed", "Reopen a completed task before recovery")
        if args.action == "block":
            require(task["state"] != "completed", "Reopen a completed task first")
            task["state"] = "blocked"
        else:
            task["generation"] += 1
            task["active_attempt"] = None
            task["state"] = "pending"
            task["owner"] = None
            if args.action == "recover":
                task["owner"] = args.new_owner.strip()
                if task["owner"] not in task["implementers"]:
                    task["implementers"].append(task["owner"])
                task["state"] = "implementing"
        event(task, args.action, owner=args.owner, reason=args.reason, new_owner=task["owner"])
        return task
    if args.action == "verify":
        require_owner(task, args.owner)
        require(task["state"] in ("implementing", "verifying", "reviewing"), "Task is not ready for verification")
        dependencies = dependency_receipts(task, tasks)
        attempt = {"id": str(uuid.uuid4()), "snapshot": fingerprint(store.root), "contract_digest": task["contract_digest"],
                   "dependencies": dependencies, "verification": {"status": "running"}, "review": None}
        task["attempts"].append(attempt)
        task["active_attempt"] = attempt["id"]
        task["state"] = "verifying"
        event(task, "verification_started", round=attempt["id"])
        store.save(data)
        attempt["verification"] = verify_contract(store.root, task["contract"])
        require_current(task, attempt, store, tasks)
        event(task, "verification_finished", round=attempt["id"], status=attempt["verification"]["status"])
        if attempt["verification"]["status"] != "passed":
            task["state"] = "implementing"
            raise GateError("Verification did not pass; inspect show for criterion evidence")
        return attempt
    if args.action == "request-review":
        require_owner(task, args.owner)
        require(task["state"] == "verifying", "Review requires successful verification")
        attempt = active_attempt(task)
        require(attempt["verification"]["status"] == "passed", "Verification did not pass")
        require_current(task, attempt, store, tasks)
        task["state"] = "reviewing"
        event(task, "review_requested", round=attempt["id"])
    if args.action in ("request-review", "packet"):
        require(task["state"] == "reviewing", "Task is not awaiting review")
        attempt = active_attempt(task)
        require_current(task, attempt, store, tasks)
        return review_packet(task, attempt, store, tasks)
    if args.action == "review":
        require(task["state"] == "reviewing", "Task is not awaiting review")
        attempt = active_attempt(task)
        require(args.round == attempt["id"], "Review round is stale or belongs to another task")
        require_current(task, attempt, store, tasks)
        result = apply_report(task, attempt, args.reviewer, read_json(args.report))
        event(task, "review_recorded", round=attempt["id"], reviewer=args.reviewer, verdict=result["verdict"])
        return result
    if args.action == "complete":
        require_owner(task, args.owner)
        require(task["state"] in ("reviewing", "completed"), "Completion requires independent approval")
        attempt = active_attempt(task)
        require_current(task, attempt, store, tasks)
        require(attempt["verification"]["status"] == "passed", "Verification did not pass")
        review = attempt["review"]
        require(review and review["verdict"] == "approved", "Completion requires independent approval")
        require(review["reviewer"] not in task["implementers"], "Self-review cannot complete a task")
        require(review["snapshot"] == attempt["snapshot"]["digest"] and review["contract_digest"] == task["contract_digest"], "Approval is stale")
        require(not any(item["severity"] == "blocking" and item["status"] == "open" for item in task["findings"].values()), "Blocking findings remain open")
        task["state"] = "completed"
        task["completed_at"] = now()
        event(task, "completed", round=attempt["id"])
        return {"id": task["id"], "state": task["state"], "snapshot": review["snapshot"], "reviewer": review["reviewer"]}
    raise GateError("Unsupported action")


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--workspace", default=".")
    actions = result.add_subparsers(dest="action", required=True)
    for name in ("create", "adopt"):
        action = actions.add_parser(name)
        action.add_argument("id")
        action.add_argument("--contract", required=True)
    for name in ("show", "packet"):
        actions.add_parser(name).add_argument("id")
    actions.add_parser("list")
    actions.add_parser("plan-status").add_argument("plan")
    for name in ("claim", "verify", "request-review", "complete", "release", "recover", "block", "reopen"):
        action = actions.add_parser(name)
        action.add_argument("id")
        action.add_argument("--owner", required=True)
        if name in ("release", "recover", "block", "reopen"):
            action.add_argument("--reason", required=True)
        if name == "recover":
            action.add_argument("--new-owner", required=True)
    review = actions.add_parser("review")
    review.add_argument("id")
    review.add_argument("--round", required=True)
    review.add_argument("--reviewer", required=True)
    review.add_argument("--report", required=True)
    bind = actions.add_parser("bind")
    bind.add_argument("--session", required=True)
    bind.add_argument("--plan", required=True)
    actions.add_parser("unbind").add_argument("--session", required=True)
    return result


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        store = Store(args.workspace)
        with store.locked():
            data = store.load()
            original = copy.deepcopy(data)
            try:
                result = dispatch(store, data, args)
            finally:
                if data != original:
                    store.save(data)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except (GateError, OSError, ValueError, KeyError, TypeError) as error:
        print(json.dumps({"error": str(error)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
