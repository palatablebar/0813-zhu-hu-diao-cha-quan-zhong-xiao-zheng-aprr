import json


def _ledger(cases):
    # 每个业务组有各自的普查框，台账按 (业务组, 分层) 保留，同号分层不合并。
    layers = {}
    for case in cases:
        for row in case.get("ledger", []):
            layers[(case["case"], row["stratum"])] = dict(row, case=case["case"])
        for row in case.get("measure", {}).get("strata", []):
            layers.setdefault(
                (case["case"], row["stratum"]),
                {
                    "stratum": row["stratum"],
                    "target": row["target"],
                    "before": row.get("before"),
                    "moved_out": row.get("moved_out", {}),
                    "moved_in": row.get("moved_in", {}),
                    "after": row.get("after", {}),
                    "balanced": row["balanced"],
                    "records": row["records"],
                    "case": case["case"],
                },
            )
    return [layers[key] for key in sorted(layers)]


def artifact(run):
    report = run["report"]
    packet = {
        "schema": "review-evidence/1",
        "manifest": report["manifest"],
        "balance": report["balance"],
        "ledger": _ledger(report.get("cases", [])),
        "cases": report["cases"],
        "intake": report["intake"],
        "review": {key: run[key] for key in ("status", "revision", "note", "reviewed")},
        "attempts": run.get("attempts", []),
    }
    return (
        json.dumps(packet, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode()
