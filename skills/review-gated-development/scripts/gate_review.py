"""Finding identities and independent review records."""

import copy

from gate_contract import identifier
from gate_store import nonempty, now, require


def apply_report(task, attempt, reviewer, report):
    require(nonempty(reviewer) and reviewer.strip() not in task["implementers"], "Reviewer must differ from every implementer")
    require(attempt["review"] is None, "This round already has a verdict")
    fields = {"verdict", "spec_review", "quality_review", "findings", "resolutions"}
    require(isinstance(report, dict) and set(report) == fields, "Review requires exactly: " + ", ".join(sorted(fields)))
    require(report["verdict"] in ("approved", "changes_requested"), "Invalid review verdict")
    require(nonempty(report["spec_review"]) and nonempty(report["quality_review"]), "Both review assessments are required")
    require(isinstance(report["findings"], list) and isinstance(report["resolutions"], list), "Findings and resolutions must be arrays")
    findings = copy.deepcopy(task["findings"])
    seen = set()
    for finding in report["findings"]:
        require(isinstance(finding, dict) and set(finding) == {"id", "severity", "detail", "evidence"}, "Invalid finding fields")
        name = finding["id"]
        require(identifier(name) and name not in findings and name not in seen, "Finding ID already exists or is invalid")
        seen.add(name)
        require(finding["severity"] in ("blocking", "advisory"), "Invalid finding severity")
        require(nonempty(finding["detail"]) and nonempty(finding["evidence"]), "Finding needs detail and evidence")
        findings[name] = dict(finding, status="open", raised_in=attempt["id"], reviewer=reviewer)
    seen = set()
    for resolution in report["resolutions"]:
        require(isinstance(resolution, dict) and set(resolution) == {"id", "status", "evidence"}, "Invalid resolution fields")
        name = resolution["id"]
        require(identifier(name) and name in task["findings"] and name not in seen, "Resolution must refer to a unique existing finding")
        seen.add(name)
        require(findings[name]["status"] == "open", "Finding is already resolved")
        require(resolution["status"] in ("addressed", "not_addressed", "false_positive"), "Invalid resolution status")
        require(nonempty(resolution["evidence"]), "Resolution evidence is required")
        if resolution["status"] != "not_addressed":
            findings[name].update(status=resolution["status"], resolved_in=attempt["id"], resolution_evidence=resolution["evidence"], resolved_by=reviewer)
    expected = {name for name, finding in task["findings"].items() if finding["status"] == "open" and finding["severity"] == "blocking"}
    require(expected <= seen, "Re-review must explicitly address every open blocking finding")
    blocking = [name for name, finding in findings.items() if finding["status"] == "open" and finding["severity"] == "blocking"]
    require((report["verdict"] == "changes_requested") == bool(blocking), "Verdict must match unresolved blocking findings")
    record = dict(report, reviewer=reviewer.strip(), recorded_at=now(), snapshot=attempt["snapshot"]["digest"], contract_digest=task["contract_digest"])
    task["findings"] = findings
    attempt["review"] = record
    if blocking:
        task["state"] = "implementing"
        task["active_attempt"] = None
    return record
