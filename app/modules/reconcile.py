from collections import Counter


def _blockers(cases):
    items = {}
    for case in cases:
        blocker = case.get("blocker")
        if blocker:
            entry = items.setdefault(
                blocker["code"], {"code": blocker["code"], "records": [], "cases": []}
            )
            entry["records"] = sorted(set(entry["records"]) | set(blocker["records"]))
            entry["cases"] = sorted(set(entry["cases"]) | {case["case"]})
            if blocker.get("details"):
                entry.setdefault("details", {})
                for key, value in blocker["details"].items():
                    if key == "ledger":
                        continue
                    entry["details"][key] = value
    return items


def _strata(cases):
    # 每个业务组有各自的普查框，同号分层不能跨组合并。
    layers = {}
    for case in cases:
        for row in case.get("measure", {}).get("strata", []):
            layers[(case["case"], row["stratum"])] = {
                "case": case["case"],
                "stratum": row["stratum"],
                "target": row["target"],
                "weighted": row["weighted"],
                "balanced": row["balanced"],
                "records": row["records"],
            }
        for row in case.get("ledger", []):
            layers.setdefault(
                (case["case"], row["stratum"]),
                {
                    "case": case["case"],
                    "stratum": row["stratum"],
                    "target": row["target"],
                    "weighted": row["after"]["households"],
                    "balanced": row["balanced"],
                    "records": row["records"],
                },
            )
    return [layers[key] for key in sorted(layers)]


def balance(intake, cases):
    accounted = (
        intake["accepted"] + intake["rejected"] + intake["blank"] + intake["repeated"]
    )
    status = Counter(case["status"] for case in cases)
    ready = status.pop("READY", 0)
    observed = sum(len(case["records"]) for case in cases)
    blockers = _blockers(cases)
    layers = _strata(cases)
    unbalanced = [f'{row["case"]}/{row["stratum"]}' for row in layers if not row["balanced"]]
    return dict(
        input=intake["input"],
        accepted=intake["accepted"],
        isolated=intake["rejected"],
        ignored=intake["blank"] + intake["repeated"],
        accounted=accounted,
        balanced=accounted == intake["input"] and observed == intake["accepted"],
        ready=ready,
        pending=len(cases) - ready,
        issues=dict(sorted(status.items())),
        blockers=blockers,
        strata=layers,
        unbalanced=unbalanced,
        releasable=bool(cases)
        and ready == len(cases)
        and not intake["rejected"]
        and accounted == intake["input"]
        and observed == intake["accepted"]
        and not blockers
        and not unbalanced,
    )
