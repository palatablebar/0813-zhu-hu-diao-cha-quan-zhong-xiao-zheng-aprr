"""按最新分层口径编排迁户前后台账。

`kind=move` 的更正行沿用四个业务列：`stratum` 为原层，`target` 为新层，
`households` 为迁出户数，`responded` 为其中在原层已回应的户数。原层 wave
回应记录不删除，只在台账里记为迁出，以保留追责依据。

迁户只做净额搬运：回应户从原层减去、在新层加上，每个回应户在任一层最多
只计一次。所有挡住签发的情形都会带上记录键与已能算出的台账，供工作台逐条
回读；旧版本和调整依据在发布失败后保持不变。
"""

from collections import defaultdict
from fractions import Fraction

from app.business import DomainIssue, by_kind, prepared


def _keys(rows):
    return sorted({row["record"] for row in rows})


def _weight(households, responded):
    return str(Fraction(households, responded)) if responded else None


def _references(row, strata):
    if row["stratum"] in strata:
        return True
    return row["kind"] == "move" and row["target"] in strata


def _refs(rows, strata):
    return _keys(row for row in rows if _references(row, strata))


def _malformed(move_rows):
    """单条更正自身就不成立的情形。"""
    return sorted(
        (
            row
            for row in move_rows
            if row["stratum"] == row["target"]
            or row["households"] < 1
            or row["responded"] > row["households"]
        ),
        key=lambda row: row["record"],
    )


def _conflicts(move_rows):
    """同一原层、同一批迁出户数被指向不同新层，视为未解决的迁户冲突。"""
    claims = defaultdict(list)
    for row in move_rows:
        claims[(row["stratum"], row["households"], row["responded"])].append(row)
    return sorted(
        (
            row
            for rows in claims.values()
            if len({row["target"] for row in rows}) > 1
            for row in rows
        ),
        key=lambda row: row["record"],
    )


def _replays(move_rows):
    """同一迁户内容换了记录键再次到达：重跑时不得把住户挪两次。"""
    groups = defaultdict(list)
    for row in move_rows:
        groups[
            (row["stratum"], row["target"], row["households"], row["responded"])
        ].append(row)
    return sorted(
        (row for rows in groups.values() if len(rows) > 1 for row in rows),
        key=lambda row: row["record"],
    )


def _ledger(rows, census, involved, move_rows):
    """迁户前后逐层台账；缺目标层的层也保留，目标记为 None。"""
    before = {key: [0, 0] for key in involved}
    records = {key: defaultdict(list) for key in involved}
    for row in by_kind(rows, "wave"):
        key = row["stratum"]
        before[key][0] += row["households"]
        before[key][1] += row["responded"]
        records[key]["wave"].append(row["record"])
    for row in by_kind(rows, "census"):
        if row["stratum"] in records:
            records[row["stratum"]]["census"].append(row["record"])

    moved_out = {key: [0, 0] for key in involved}
    moved_in = {key: [0, 0] for key in involved}
    moves = []
    for row in sorted(move_rows, key=lambda r: r["record"]):
        source, target = row["stratum"], row["target"]
        moved_out[source][0] += row["households"]
        moved_out[source][1] += row["responded"]
        moved_in[target][0] += row["households"]
        moved_in[target][1] += row["responded"]
        records[source]["move"].append(row["record"])
        records[target]["move"].append(row["record"])
        moves.append(
            {
                "record": row["record"],
                "from": str(source),
                "to": str(target),
                "households": row["households"],
                "responded": row["responded"],
                "note": row["note"],
            }
        )

    after = {
        key: [
            before[key][0] - moved_out[key][0] + moved_in[key][0],
            before[key][1] - moved_out[key][1] + moved_in[key][1],
        ]
        for key in involved
    }
    layers = [
        {
            "stratum": str(key),
            "target": census.get(key),
            "before": {
                "households": before[key][0],
                "responded": before[key][1],
                "weight": _weight(*before[key]),
            },
            "moved_out": {
                "households": moved_out[key][0],
                "responded": moved_out[key][1],
            },
            "moved_in": {
                "households": moved_in[key][0],
                "responded": moved_in[key][1],
            },
            "after": {
                "households": after[key][0],
                "responded": after[key][1],
                "weight": _weight(*after[key]),
                "weighted": after[key][0],
            },
            "balanced": after[key][0] == census.get(key),
            "records": {kind: sorted(value) for kind, value in records[key].items()},
        }
        for key in sorted(involved)
    ]
    return layers, moves, before, after, moved_out, moved_in


def prepare(rows):
    census_rows = by_kind(rows, "census")
    wave_rows = by_kind(rows, "wave")
    move_rows = by_kind(rows, "move")

    census = {}
    for row in census_rows:
        key = row["stratum"]
        if key in census:
            raise DomainIssue(
                "FRAME_DUPLICATE",
                _keys(r for r in census_rows if r["stratum"] == key),
                {"stratum": str(key)},
            )
        census[key] = row["target"]

    excess = (
        [row for row in wave_rows if row["responded"] > row["households"]]
        + [row for row in move_rows if row["responded"] > row["households"]]
    )
    if excess:
        raise DomainIssue("EXCESS_RESPONSE", _keys(excess))

    involved = {row["stratum"] for row in wave_rows}
    involved |= {row["stratum"] for row in move_rows}
    involved |= {row["target"] for row in move_rows}
    ledger, moves, before, after, moved_out, moved_in = _ledger(
        rows, census, involved, move_rows
    )

    def fail(code, refs, **details):
        raise DomainIssue(code, refs, dict(details, ledger=ledger))

    malformed = _malformed(move_rows)
    if malformed:
        fail("MOVE_CONFLICT", _keys(malformed))
    conflict = _conflicts(move_rows)
    if conflict:
        fail("MOVE_CONFLICT", _keys(conflict))
    replay = _replays(move_rows)
    if replay:
        fail("MOVE_REPLAY", _keys(replay))

    if not involved:
        raise DomainIssue("FRAME_STRATUM_MISMATCH", _keys(rows))

    missing = sorted(involved - set(census))
    if missing:
        strata = set(missing)
        targets = {row["target"] for row in move_rows}
        code = (
            "MOVE_TARGET_MISSING"
            if any(key in targets for key in missing)
            else "FRAME_STRATUM_MISMATCH"
        )
        fail(code, _refs(rows, strata), strata=[str(key) for key in missing])
    unreferenced = sorted(set(census) - involved)
    if unreferenced:
        strata = set(unreferenced)
        fail(
            "FRAME_STRATUM_MISMATCH",
            _refs(rows, strata),
            strata=[str(key) for key in unreferenced],
        )

    # 迁出只能来自原层登记的在册样本。迁出量超过原层波次，源层在簿户数
    # 或回应户数会变成负数，等于把同一批住户挪了两次。
    overdraw = sorted(
        key
        for key in involved
        if moved_out[key][0] > before[key][0]
        or moved_out[key][1] > before[key][1]
        or after[key][0] < 0
        or after[key][1] < 0
    )
    if overdraw:
        strata = set(overdraw)
        fail(
            "MOVE_OVERDRAW",
            _keys(row for row in move_rows if row["stratum"] in strata),
            strata=[str(key) for key in overdraw],
        )

    # 原层波次已经等于最新普查目标，说明这一层按迁户后口径报过数；再叠加
    # 同一条迁出会把它压到目标之下，即重复挪户。净额恰好回到目标的分层
    # 属于正常互迁，不在此列。
    shifted = sorted(
        key
        for key in involved
        if before[key][0] == census[key]
        and moved_out[key][0] > 0
        and after[key][0] != census[key]
    )
    if shifted:
        strata = set(shifted)
        fail(
            "MOVE_REPLAY",
            _keys(
                row
                for row in move_rows
                if row["stratum"] in strata or row["target"] in strata
            ),
            strata=[str(key) for key in shifted],
        )

    # 迁入后原层已无人回应，权重无从计算。
    empty = sorted(key for key in involved if after[key][1] == 0)
    if empty:
        strata = set(empty)
        fail("NO_RESPONDENTS", _refs(rows, strata), strata=[str(key) for key in empty])

    totals = {key: (after[key][0], after[key][1]) for key in sorted(involved)}
    payload = dict(
        census=census,
        totals=totals,
        ledger=ledger,
        moves=moves,
        strata=sorted(involved),
    )
    summary = prepared(
        len(totals),
        {
            "respondents": sum(value[1] for value in totals.values()),
            "moved_households": sum(value[0] for value in moved_out.values()),
            "moved_respondents": sum(value[1] for value in moved_out.values()),
        },
        payload,
    )
    summary[0]["ledger"] = ledger
    summary[0]["moves"] = moves
    return summary
