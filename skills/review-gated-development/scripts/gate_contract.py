"""Immutable verification contracts and captured command evidence."""

import math
import os
import re
import signal
import subprocess
import sys
import tempfile

from gate_store import digest, nonempty, now, require


def identifier(value):
    return isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}", value) is not None


def validate_contract(contract):
    fields = {"objective", "plan", "kind", "depends_on", "constraints", "user_decisions", "criteria", "checks"}
    require(isinstance(contract, dict) and set(contract) == fields, "Contract requires exactly: " + ", ".join(sorted(fields)))
    require(nonempty(contract["objective"]) and identifier(contract["plan"]), "Objective and plan ID are required")
    require(contract["kind"] in ("implementation", "integration"), "Kind must be implementation or integration")
    for name in ("constraints", "user_decisions", "depends_on"):
        require(isinstance(contract[name], list) and all(nonempty(item) for item in contract[name]), "Invalid " + name)
    require(len(set(contract["depends_on"])) == len(contract["depends_on"]), "Duplicate dependencies")
    require(isinstance(contract["checks"], list) and contract["checks"], "At least one verification check is required")
    checks = set()
    for check in contract["checks"]:
        require(isinstance(check, dict) and set(check) == {"id", "argv", "timeout", "assertions"}, "Invalid check fields")
        require(identifier(check["id"]) and check["id"] not in checks, "Check IDs must be unique")
        checks.add(check["id"])
        require(isinstance(check["argv"], list) and check["argv"] and all(nonempty(arg) for arg in check["argv"]), "Check argv must be nonempty strings")
        timeout = check["timeout"]
        require(type(timeout) in (int, float) and math.isfinite(timeout) and 0 < timeout <= 300, "Timeout must be between 0 and 300 seconds")
        require(isinstance(check["assertions"], list) and check["assertions"], "Each check needs positive output assertions")
        for assertion in check["assertions"]:
            require(isinstance(assertion, dict) and set(assertion) == {"stream", "contains"}, "Assertions require stream and contains")
            require(assertion["stream"] in ("stdout", "stderr") and nonempty(assertion["contains"]), "Invalid output assertion")
    require(isinstance(contract["criteria"], list) and contract["criteria"], "At least one criterion is required")
    criteria, referenced = set(), set()
    for criterion in contract["criteria"]:
        require(isinstance(criterion, dict) and set(criterion) == {"id", "description", "checks"}, "Invalid criterion fields")
        require(identifier(criterion["id"]) and criterion["id"] not in criteria, "Criterion IDs must be unique")
        criteria.add(criterion["id"])
        require(nonempty(criterion["description"]), "Criterion description is required")
        names = criterion["checks"]
        require(isinstance(names, list) and names and all(isinstance(name, str) for name in names), "Each criterion must reference checks")
        require(len(set(names)) == len(names) and set(names) <= checks, "Unknown or duplicate criterion checks")
        referenced.update(names)
    require(referenced == checks, "Every check must map to a criterion")


def validate_dependency_declarations(contract, tasks):
    for name in contract["depends_on"]:
        require(name in tasks and tasks[name].get("version") == 2, "Dependency must already exist as a v2 task: " + name)
        require(tasks[name]["contract"]["plan"] == contract["plan"], "Dependencies must be in the same plan")
        require(tasks[name]["contract"]["kind"] == "implementation", "Cannot depend on integration tasks")
    siblings = [task for task in tasks.values() if task.get("version") == 2 and task["contract"]["plan"] == contract["plan"]]
    require(not any(task["contract"]["kind"] == "integration" for task in siblings), "Plan is sealed by its integration task; use a new plan for new work")
    if contract["kind"] == "integration":
        required = {task["id"] for task in siblings}
        require(required and set(contract["depends_on"]) == required, "Integration must depend on every implementation task in the plan")


def stop_process(process):
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, timeout=10, check=False)
        if process.poll() is None:
            process.kill()
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    process.wait(timeout=10)


def run_check(root, check):
    command = [sys.executable if index == 0 and arg == "{python}" else arg for index, arg in enumerate(check["argv"])]
    result = {"id": check["id"], "command": command, "timeout_seconds": check["timeout"], "started_at": now()}
    options = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {"start_new_session": True}
    with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
        try:
            process = subprocess.Popen(command, cwd=root, stdout=stdout, stderr=stderr, **options)
        except OSError as error:
            return dict(result, status="failed", error=str(error), finished_at=now(), assertions=[])
        try:
            code = process.wait(timeout=check["timeout"])
            result.update(status="passed" if code == 0 else "failed", exit_code=code)
        except subprocess.TimeoutExpired:
            result["status"] = "timed_out"
        finally:
            stop_process(process)
        for label, stream in (("stdout", stdout), ("stderr", stderr)):
            length = stream.tell()
            stream.seek(max(0, length - 32768))
            result[label] = stream.read().decode("utf-8", errors="replace").replace("\r\n", "\n")
            result[label + "_truncated"] = length > 32768
    result["assertions"] = [dict(assertion, passed=assertion["contains"] in result[assertion["stream"]]) for assertion in check["assertions"]]
    if result["status"] == "passed" and not all(item["passed"] for item in result["assertions"]):
        result["status"] = "failed"
        result["error"] = "Command exited zero but required output assertions were missing"
    return dict(result, finished_at=now())


def verify_contract(root, contract):
    evidence = [run_check(root, check) for check in contract["checks"]]
    by_id = {item["id"]: item for item in evidence}
    criteria = {item["id"]: {"checks": item["checks"], "passed": all(by_id[name]["status"] == "passed" for name in item["checks"])} for item in contract["criteria"]}
    return {"status": "passed" if all(item["passed"] for item in criteria.values()) else "failed",
            "contract_digest": digest(contract), "checks": evidence, "criteria": criteria}
