from agent_core import normalize_plan


def test_plan_normalization_keeps_only_supported_task_types_and_never_executes():
    plan = normalize_plan({
        "task_type": "run arbitrary code",
        "summary": "احجز ترابيزة",
        "extracted_data": {"party_size": 2},
        "missing_fields": ["restaurant_name", "date"],
        "clarification_question": "اسم المطعم وإمتى؟",
        "proposed_steps": ["اسأل عن التفاصيل"],
        "requires_confirmation": True,
        "safe_to_execute": True,
    }, "احجز ترابيزة")
    assert plan["task_type"] == "general"
    assert plan["missing_fields"] == ["restaurant_name", "date"]
    assert plan["safe_to_execute"] is False


def test_plan_normalization_handles_malformed_model_fields():
    plan = normalize_plan({"extracted_data": [], "missing_fields": "date", "proposed_steps": None}, "hello")
    assert plan["summary"] == "hello"
    assert plan["extracted_data"] == {}
    assert plan["missing_fields"] == []
    assert plan["proposed_steps"] == []
    assert plan["clarification_question"] is None
