from app.business import decision


def _records(rows):
    keys = set()
    for row in rows:
        for kind in row.get("records", {}).values():
            keys.update(kind)
    return sorted(keys)


def policy(result):
    """每层权重总和必须等于该层最新普查目标。

    总覆盖相等但逐层此消彼长时仍视为差异，避免迁户把缺口挪到别层
    而被整体合计掩盖。
    """
    strata = result.get("strata", [])
    unbalanced = [row for row in strata if not row["balanced"]]
    reason = None
    if unbalanced:
        reason = (
            "MISMATCH"
            if result["value"] != result["expected"]
            else "STRATUM_MISMATCH"
        )
    answer = decision(result, reason)
    answer["strata"] = [
        {
            "stratum": row["stratum"],
            "target": row["target"],
            "weighted": row["weighted"],
            "weight": row["weight"],
            "balanced": row["balanced"],
            "records": row["records"],
        }
        for row in strata
    ]
    answer["unbalanced"] = [row["stratum"] for row in unbalanced]
    if unbalanced:
        answer["blocker"] = {
            "code": reason,
            "records": _records(unbalanced),
            "details": {
                "strata": [row["stratum"] for row in unbalanced],
                "targets": {row["stratum"]: row["target"] for row in unbalanced},
                "weighted": {
                    row["stratum"]: row["weighted"] for row in unbalanced
                },
            },
        }
    return answer
