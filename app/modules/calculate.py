from app.business import measured


def compute(data):
    from fractions import Fraction

    census, totals = data
    weights = {str(k): str(Fraction(a, b)) for k, (a, b) in totals.items()}
    weighted = sum(Fraction(a, b) * b for a, b in totals.values())
    return measured(
        int(weighted),
        sum(census.values()),
        "户",
        weights,
        sorted(k for k, (a, _) in totals.items() if a != census[k]),
    )
