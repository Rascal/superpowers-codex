#!/usr/bin/env python3
"""Optional Codex lifecycle adapter; no transcript parsing or state mutation."""

import json
from pathlib import Path
import sys

from gate_store import GateError, Store
from review_gate import plan_status


def respond(payload):
    event = payload.get("hook_event_name")
    if event not in ("SessionStart", "Stop"):
        return {}
    directory = Path(payload["cwd"]).resolve(strict=True)
    root = next((path for path in (directory, *directory.parents) if (path / ".review-gate" / "state.json").is_file()), None)
    if root is None:
        return {}
    store = Store(root, create=False)
    with store.locked():
        data = store.load()
        session = payload.get("session_id")
        plan = data.get("bindings", {}).get(session)
        if not plan:
            if event == "SessionStart":
                return {"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext":
                        "Review gate is installed but this session is not bound to a plan. "
                        "Use the review-gated-development skill to bind explicitly when adopting the workflow. "
                        "The current session ID is " + str(session)}}
            return {}
        status = plan_status(data, plan, root)
    if event == "SessionStart":
        return {"hookSpecificOutput": {"hookEventName": event, "additionalContext":
                "Resume from the review-gate task store, not chat recollection. " + json.dumps(status)}}
    if status["complete"]:
        return {}
    reason = "Review-gate plan " + plan + " is incomplete: " + "; ".join(status["issues"])
    if status["blocked"] or payload.get("stop_hook_active"):
        return {"systemMessage": reason + ". Report the remaining work; do not claim completion."}
    return {"decision": "block", "reason": reason + ". Continue the recorded workflow or record a concrete blocker."}


def main():
    try:
        payload = json.load(sys.stdin)
        if not isinstance(payload, dict):
            raise ValueError("Expected hook JSON object")
        result = respond(payload)
    except (GateError, OSError, ValueError, KeyError, TypeError) as error:
        result = {"systemMessage": "Review-gate hook could not assess completion: " + str(error) + ". This is not approval."}
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
