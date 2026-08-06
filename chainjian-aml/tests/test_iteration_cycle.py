from scripts.iteration_cycle import diagnose


def test_diagnose_requires_baseline_first_run():
    signals = diagnose({"data_quality": {}}, None)
    assert signals[0]["code"] == "BASELINE_NOT_AVAILABLE"


def test_diagnose_detects_alert_volume_red_line():
    previous = {"rules": {"total_alert_cases": 100, "hit_counts": {}}, "data_quality": {}, "distribution": {}, "review": {}}
    current = {"rules": {"total_alert_cases": 160, "hit_counts": {}}, "data_quality": {}, "distribution": {}, "review": {}}
    signals = diagnose(current, previous)
    assert any(item["code"] == "ALERT_VOLUME_DRIFT" and item["level"] == "RED" for item in signals)


def test_diagnose_surfaces_evaluation_dependency_failure():
    signals = diagnose(
        {"data_quality": {}},
        {"data_quality": {}, "distribution": {}, "rules": {}, "review": {}},
        {"warning": "Neo4j unavailable"},
    )
    assert any(item["code"] == "OFFLINE_EVALUATION_UNAVAILABLE" and item["level"] == "RED" for item in signals)
