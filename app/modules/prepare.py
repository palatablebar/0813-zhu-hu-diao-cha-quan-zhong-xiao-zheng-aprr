from app.business import DomainIssue, by_kind, prepared


def prepare(rows):
    from collections import defaultdict

    census = {}
    for row in by_kind(rows, "census"):
        k = row["stratum"]
        if k in census:
            raise DomainIssue("FRAME_DUPLICATE")
        census[k] = row["target"]
    waves = defaultdict(list)
    for r in by_kind(rows, "wave"):
        if r["responded"] > r["households"]:
            raise DomainIssue("EXCESS_RESPONSE")
        waves[r["stratum"]].append((r["households"], r["responded"]))
    if set(census) != set(waves) or not census:
        raise DomainIssue("FRAME_STRATUM_MISMATCH")
    totals = {
        k: (sum(a for a, _ in pairs), sum(b for _, b in pairs))
        for k, pairs in sorted(waves.items())
    }
    if any(not b for _, b in totals.values()):
        raise DomainIssue("NO_RESPONDENTS")
    return prepared(
        len(totals),
        {"respondents": sum(b for _, b in totals.values())},
        (census, totals),
    )
