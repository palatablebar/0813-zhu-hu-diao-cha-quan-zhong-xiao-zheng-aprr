from datetime import datetime, timezone
from hashlib import sha256
from time import monotonic

from app.business import DomainIssue
from app.config import RULE_VERSION
from app.modules.pipeline import run


def now():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def execute(store, data):
    start = monotonic()
    fingerprint = sha256(data).hexdigest()
    run_id = sha256(f"{RULE_VERSION}:{fingerprint}".encode()).hexdigest()
    try:
        return store.load(run_id)
    except DomainIssue as error:
        if error.code != "RUN_NOT_FOUND":
            raise
    report = run(data)
    report["manifest"] = dict(
        sha256=fingerprint,
        version=RULE_VERSION,
        created=now(),
        duration_ms=round((monotonic() - start) * 1000, 3),
        bytes=len(data),
        run_id=run_id,
    )
    return store.register(run_id, report)


def blockers(report):
    """汇总挡住签发的全部原因，逐项带记录键。"""
    checks = report.get("balance") or {}
    items = []
    for code, item in sorted((checks.get("blockers") or {}).items()):
        entry = {"code": code, "records": list(item.get("records", []))}
        if item.get("details"):
            entry["details"] = dict(item["details"])
        items.append(entry)
    if not checks.get("balanced", False):
        items.append(
            {
                "code": "UNBALANCED_LINES",
                "records": [],
                "details": {
                    "input": checks.get("input", 0),
                    "accounted": checks.get("accounted", 0),
                    "accepted": checks.get("accepted", 0),
                },
            }
        )
    if checks.get("isolated"):
        items.append(
            {
                "code": "ISOLATED_ROWS",
                "records": sorted(
                    str(row.get("record"))
                    for row in (report.get("intake") or {}).get("isolation", [])
                ),
                "details": {"count": checks["isolated"]},
            }
        )
    if not items and not checks.get("releasable", False):
        items.append({"code": "UNRESOLVED_ISSUES", "records": []})
    return items


def _records(items):
    keys = set()
    for item in items:
        keys.update(item.get("records", []))
    return sorted(keys)


def review(store, run_id, values):
    if not isinstance(values, dict):
        raise DomainIssue("REVIEW_FIELDS")
    revision, status, note = (values.get(key) for key in ("revision", "status", "note"))
    if (
        type(revision) is not int
        or revision < 0
        or status not in ("APPROVED", "HELD")
        or not isinstance(note, str)
        or not (3 <= len(note.strip()) <= 200)
    ):
        raise DomainIssue("REVIEW_FIELDS")
    current = store.load(run_id)
    if revision != current["revision"]:
        raise DomainIssue("STALE_REVIEW")
    if current["status"] == "APPROVED":
        raise DomainIssue("RUN_FINALIZED")
    if status == "APPROVED" and not current["report"]["balance"]["releasable"]:
        pending = blockers(current["report"])
        # 发布失败仍保留旧版本与调整依据：先落一条失败尝试，再抛错。
        store.note_attempt(
            run_id,
            revision,
            status,
            "BLOCKED",
            note.strip(),
            pending,
            now(),
        )
        raise DomainIssue(
            "UNRESOLVED_ISSUES",
            _records(pending),
            {"blockers": pending},
        )
    return store.revise(run_id, revision, status, note.strip(), now())
