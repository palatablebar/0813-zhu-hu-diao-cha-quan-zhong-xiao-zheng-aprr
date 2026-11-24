from fractions import Fraction

from app.business import measured


def compute(data):
    census = data["census"]
    totals = data["totals"]
    ledger = {item["stratum"]: item for item in data["ledger"]}

    weights = {}
    rows = []
    for key in sorted(totals):
        households, responded = totals[key]
        weight = Fraction(households, responded)
        weights[str(key)] = str(weight)
        item = ledger[str(key)]
        rows.append(
            {
                "stratum": str(key),
                "target": census[key],
                "households": households,
                "responded": responded,
                "weight": str(weight),
                "weighted": households,
                "balanced": households == census[key],
                "records": item["records"],
                "before": item["before"],
                "moved_out": item["moved_out"],
                "moved_in": item["moved_in"],
                "after": item["after"],
            }
        )

    # 每层权重 × 该层回应户数即迁户后的在册户数，合计应等于各层目标之和。
    weighted = sum(Fraction(row["weight"]) * row["responded"] for row in rows)
    expected = sum(census.values())
    flags = sorted(row["stratum"] for row in rows if not row["balanced"])
    answer = measured(int(weighted), expected, "户", weights, flags)
    answer["strata"] = rows
    answer["weighted"] = int(weighted)
    answer["moves"] = data["moves"]
    return answer
