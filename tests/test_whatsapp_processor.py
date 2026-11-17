import asyncio

from integrations import whatsapp_processor as processor


class FakeEvents:
    def __init__(self, event):
        self.event = event
        self.status = event["status"]

    def get(self, event_id):
        return self.event

    def set_status(self, event_id, status):
        self.status = status
        self.event["status"] = status


class FakePlanner:
    def plan(self, instruction):
        return {
            "task_type": "general",
            "summary": "نفذ طلب المستخدم",
            "extracted_data": {"intent": "test"},
            "missing_fields": ["date"],
            "clarification_question": "تقصد أنهي يوم؟",
            "proposed_steps": ["استكمال التفاصيل"],
            "requires_confirmation": True,
            "safe_to_execute": False,
        }


class FakeTasks:
    def __init__(self):
        self.created = None

    def create(self, **kwargs):
        self.created = kwargs
        return {"id": "task-1"}


def test_linked_whatsapp_text_becomes_task_draft_without_external_action(monkeypatch):
    event = {
        "id": 7,
        "user_id": 42,
        "sender": "201000000000",
        "event_type": "text",
        "status": "received",
        "payload": {"text": "احجزلي مطعم"},
    }
    fake_events = FakeEvents(event)
    fake_tasks = FakeTasks()
    monkeypatch.setattr(processor, "events", fake_events)
    monkeypatch.setattr(processor, "tasks", fake_tasks)
    monkeypatch.setattr(processor, "AgentPlanner", FakePlanner)
    monkeypatch.setattr(processor.settings, "whatsapp_access_token", "")
    monkeypatch.setattr(processor.settings, "whatsapp_phone_number_id", "")

    asyncio.run(processor.process_whatsapp_event(7))

    assert fake_events.status == "processed"
    assert fake_tasks.created["user_id"] == 42
    assert fake_tasks.created["initial_status"] == "awaiting_user_input"
    assert fake_tasks.created["extracted_data"]["safe_to_execute"] is False


def test_unlinked_whatsapp_event_is_ignored(monkeypatch):
    event = {
        "id": 8,
        "user_id": None,
        "sender": "201000000000",
        "event_type": "text",
        "status": "received",
        "payload": {"text": "hello"},
    }
    fake_events = FakeEvents(event)
    monkeypatch.setattr(processor, "events", fake_events)

    asyncio.run(processor.process_whatsapp_event(8))

    assert fake_events.status == "ignored"
