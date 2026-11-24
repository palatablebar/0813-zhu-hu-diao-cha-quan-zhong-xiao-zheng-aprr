import io

import pytest

from app.business import DomainIssue
from app.intake.service import inspect
from app.modules.pipeline import run
from app.review.service import blockers, execute, review
from conftest import ROOT, csv_data

HEAD = ["record", "case", "kind", "stratum", "households", "responded", "target", "note"]


def load(profile):
    return (ROOT / "sample_data" / f"{profile}.csv").read_bytes()


def case(report, code):
    return next(item for item in report["cases"] if item["case"] == code)


def moved_sample(records):
    return csv_data(records)


BASE = [
    ["000101", "0001", "census", "1", "0", "0", "75", "目标"],
    ["000102", "0001", "wave", "1", "50", "25", "0", "原层留存"],
    ["000103", "0001", "wave", "1", "30", "10", "0", "原层留存"],
    ["000104", "0001", "census", "2", "0", "0", "25", "目标"],
    ["000105", "0001", "wave", "2", "20", "5", "0", "新层样本"],
]


def move(record="000106", source="1", target="2", households="5", responded="2"):
    return [record, "0001", "move", source, households, responded, target, "迁户"]


def test_move_kind_is_accepted_by_schema():
    result = inspect(csv_data([*BASE, move()]))
    assert result["accepted"] == len(BASE) + 1 and not result["rejected"]


def test_move_rows_need_target_column_value():
    result = inspect(csv_data([*BASE, move(target="-")]))
    assert result["reasons"] == {"MISSING_NUMBER": 1}


def test_moved_sample_is_releasable():
    checks = run(load("moved"))["balance"]
    assert checks["releasable"] and not checks["blockers"]


def test_every_replayable_stratum_matches_latest_target():
    report = run(load("moved"))
    for item in case(report, "0001")["measure"]["strata"]:
        assert item["weighted"] == item["target"]


def test_respondent_order_is_counted_once_per_stratum():
    report = run(load("moved"))
    payload = case(report, "0001")
    strata = {item["stratum"]: item for item in payload["prep"]["ledger"]}
    # 层 1 迁出 5 户其中 2 户是回应户，层 2 迁入同一批，回应户总量守恒。
    assert strata["1"]["after"]["responded"] == 33
    assert strata["2"]["after"]["responded"] == 7
    assert sum(item["after"]["responded"] for item in strata.values()) == 40


def test_ledger_keeps_before_and_after_households_and_weights():
    report = run(load("moved"))
    ledger = {item["stratum"]: item for item in case(report, "0001")["prep"]["ledger"]}
    assert ledger["1"]["before"] == {"households": 80, "responded": 35, "weight": "16/7"}
    assert ledger["1"]["after"]["households"] == 75
    assert ledger["2"]["before"]["weight"] == "4"
    assert ledger["2"]["after"]["weight"] == "25/7"
    assert ledger["1"]["moved_out"] == {"households": 5, "responded": 2}
    assert ledger["2"]["moved_in"] == {"households": 5, "responded": 2}


def test_ledger_records_are_readable_per_stratum():
    report = run(load("moved"))
    ledger = {item["stratum"]: item for item in case(report, "0001")["prep"]["ledger"]}
    assert "000102" in ledger["1"]["records"]["wave"]
    assert "000106" in ledger["1"]["records"]["move"]
    assert "000106" in ledger["2"]["records"]["move"]
    assert "000101" in ledger["1"]["records"]["census"]


def test_migration_conflict_blocks_release_with_record_keys():
    report = run(load("move_conflict"))
    checks = report["balance"]
    assert not checks["releasable"]
    assert checks["blockers"]["MOVE_CONFLICT"]["records"] == ["000106", "000107"]
    assert case(report, "0001")["blocker"]["records"] == ["000106", "000107"]


def test_missing_target_blocks_release_with_record_keys():
    report = run(load("move_missing_target"))
    checks = report["balance"]
    assert not checks["releasable"]
    item = checks["blockers"]["MOVE_TARGET_MISSING"]
    assert item["records"] == ["000106"] and item["details"]["strata"] == ["3"]


def test_replayed_move_blocks_release_with_record_keys():
    report = run(load("move_replay"))
    checks = report["balance"]
    assert not checks["releasable"]
    assert checks["blockers"]["MOVE_REPLAY"]["records"] == ["000106", "000107"]


def test_same_record_repeated_is_isolated_and_blocks_release():
    # 完全相同的迁户更正重发，采信层按重复回放只留一条；重复本身仍进隔离表。
    sample = moved_sample([*BASE, move(), move()])
    result = inspect(sample)
    assert result["reasons"] == {"DUPLICATE_REPLAY": 1}
    report = run(sample)
    assert not report["balance"]["releasable"]
    assert report["intake"]["isolation"][0]["record"] == "000106"


def test_same_record_with_different_content_is_a_conflict():
    sample = moved_sample([*BASE, move(), move(households="6", responded="3")])
    result = inspect(sample)
    assert result["reasons"] == {"DUPLICATE_CONFLICT": 2}
    assert not run(sample)["balance"]["releasable"]


def test_replayed_move_with_new_record_cannot_double_shift():
    sample = moved_sample([*BASE, move(), move(record="000107")])
    report = run(sample)
    assert case(report, "0001")["status"] == "MOVE_REPLAY"
    assert case(report, "0001")["blocker"]["records"] == ["000106", "000107"]


def test_move_back_to_same_stratum_is_a_conflict():
    sample = moved_sample([*BASE, move(target="1")])
    report = run(sample)
    assert case(report, "0001")["status"] == "MOVE_CONFLICT"


def test_move_exceeding_source_households_is_an_overdraw():
    sample = moved_sample([*BASE, move(households="90", responded="30")])
    report = run(sample)
    assert case(report, "0001")["status"] == "MOVE_OVERDRAW"
    assert case(report, "0001")["blocker"]["records"] == ["000106"]


def test_source_records_survive_migration():
    report = run(load("moved"))
    records = case(report, "0001")["records"]
    assert {"000102", "000103", "000106"} <= set(records)


def test_total_value_equal_but_stratum_off_still_flagged():
    rows = [
        ["000101", "0001", "census", "1", "0", "0", "60", "目标"],
        ["000102", "0001", "wave", "1", "70", "35", "0", "波次"],
        ["000104", "0001", "census", "2", "0", "0", "40", "目标"],
        ["000105", "0001", "wave", "2", "30", "15", "0", "波次"],
    ]
    report = run(moved_sample(rows))
    item = case(report, "0001")
    assert item["measure"]["value"] == item["measure"]["expected"]
    assert item["status"] == "STRATUM_MISMATCH"
    assert item["blocker"]["code"] == "STRATUM_MISMATCH"
    assert item["blocker"]["records"]
    assert not report["balance"]["releasable"]


def test_moved_sample_keeps_existing_dirty_semantics(dirty):
    assert run(dirty)["balance"]["releasable"] is False


def test_approval_blocked_lists_record_keys(store):
    run_record = execute(store, load("move_conflict"))
    with pytest.raises(DomainIssue) as caught:
        review(
            store,
            run_record["id"],
            dict(revision=0, status="APPROVED", note="尝试签发迁户批次"),
        )
    error = caught.value
    assert error.code == "UNRESOLVED_ISSUES"
    assert {"000106", "000107"} <= set(error.records)
    assert error.details["blockers"][0]["code"] == "MOVE_CONFLICT"


def test_failed_release_keeps_old_version_and_evidence(store):
    run_record = execute(store, load("move_conflict"))
    before = store.load(run_record["id"])
    with pytest.raises(DomainIssue):
        review(
            store,
            run_record["id"],
            dict(revision=0, status="APPROVED", note="尝试发布"),
        )
    after = store.load(run_record["id"])
    assert after["status"] == before["status"]
    assert after["revision"] == before["revision"]
    assert after["note"] == before["note"]
    assert after["report"] == before["report"]
    assert after["attempts"][-1]["outcome"] == "BLOCKED"
    assert after["attempts"][-1]["blockers"][0]["code"] == "MOVE_CONFLICT"


def test_failed_release_keeps_record_evidence(store):
    import json

    from app.evidence.render import artifact

    run_record = execute(store, load("move_missing_target"))
    with pytest.raises(DomainIssue):
        review(store, run_record["id"], dict(revision=0, status="APPROVED", note="尝试发布"))
    packet = json.loads(artifact(store.load(run_record["id"])))
    assert packet["balance"]["blockers"]["MOVE_TARGET_MISSING"]["records"] == ["000106"]
    assert packet["attempts"][-1]["note"] == "尝试发布"


def test_failed_release_can_then_hold(store):
    run_record = execute(store, load("move_replay"))
    with pytest.raises(DomainIssue):
        review(store, run_record["id"], dict(revision=0, status="APPROVED", note="先试着签发"))
    held = review(
        store, run_record["id"], dict(revision=0, status="HELD", note="迁户更正待核对")
    )
    assert held["status"] == "HELD" and held["revision"] == 1
    assert [item["outcome"] for item in held["attempts"]] == ["BLOCKED", "COMMITTED"]


def test_clean_sample_still_releasable(store):
    run_record = execute(store, load("ready"))
    approved = review(
        store, run_record["id"], dict(revision=0, status="APPROVED", note="复核通过")
    )
    assert approved["status"] == "APPROVED"


def test_http_release_failure_returns_records(client):
    run_record = client.post("/api/runs", data={"sample": "moveconflict"}).json
    response = client.patch(
        f"/api/runs/{run_record['id']}",
        json=dict(revision=0, status="APPROVED", note="尝试签发"),
    )
    assert response.status_code == 409
    assert response.json["code"] == "UNRESOLVED_ISSUES"
    assert {"000106", "000107"} <= set(response.json["records"])


def test_http_history_retains_blocked_attempt(client):
    run_record = client.post("/api/runs", data={"sample": "movereplay"}).json
    client.patch(
        f"/api/runs/{run_record['id']}",
        json=dict(revision=0, status="APPROVED", note="尝试签发"),
    )
    loaded = client.get(f"/api/runs/{run_record['id']}").json
    assert loaded["status"] == "PENDING" and loaded["revision"] == 0
    assert loaded["attempts"][0]["outcome"] == "BLOCKED"
    assert loaded["attempts"][0]["blockers"][0]["records"] == ["000106", "000107"]


def test_evidence_includes_ledger_and_attempts(client):
    run_record = client.post("/api/runs", data={"sample": "moved"}).json
    packet = client.get(f"/api/runs/{run_record['id']}/evidence").json
    assert packet["schema"] == "review-evidence/1"
    assert {item["stratum"] for item in packet["ledger"]} == {"1", "2", "3"}
    assert packet["attempts"] == []


def test_blockers_helper_reports_every_blocking_reason():
    report = run(load("move_missing_target"))
    codes = {item["code"] for item in blockers(report)}
    assert "MOVE_TARGET_MISSING" in codes


def test_rerun_of_same_bytes_does_not_shift_again(store):
    first = execute(store, load("moved"))
    second = execute(store, load("moved"))
    assert first["id"] == second["id"]
    assert first["report"]["balance"]["strata"] == second["report"]["balance"]["strata"]
    assert len(store.list()) == 1


def test_rerun_with_repeated_correction_is_blocked(store):
    # 来源文件重跑时又带了一条同样的迁户更正，换记录键也算重复挪户。
    sample = moved_sample(
        [*BASE, move(), move(record="000107")]
    )
    run_record = execute(store, sample)
    with pytest.raises(DomainIssue) as caught:
        review(
            store,
            run_record["id"],
            dict(revision=0, status="APPROVED", note="尝试签发重跑结果"),
        )
    assert caught.value.code == "UNRESOLVED_ISSUES"
    assert {"000106", "000107"} <= set(caught.value.records)


def test_strata_do_not_merge_across_cases(dirty):
    report = run(dirty)
    keys = [(row["case"], row["stratum"]) for row in report["balance"]["strata"]]
    assert len(keys) == len(set(keys))
    assert ("0001", "1") in keys and ("0004", "1") in keys


def test_blocked_attempt_is_visible_in_history(client):
    run_record = client.post("/api/runs", data={"sample": "moveconflict"}).json
    client.patch(
        f"/api/runs/{run_record['id']}",
        json=dict(revision=0, status="APPROVED", note="尝试签发"),
    )
    listed = client.get("/api/runs").json["items"]
    assert listed[0]["id"] == run_record["id"]
    assert listed[0]["status"] == "PENDING" and listed[0]["revision"] == 0
    assert listed[0]["note"] == ""
