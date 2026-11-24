from app.business import decision


def policy(result):
    return decision(
        result,
        (
            "STRATUM_MISMATCH"
            if result["flag"] and result["value"] == result["expected"]
            else None
        ),
    )
