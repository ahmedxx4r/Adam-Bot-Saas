import pytest

from database import Base, engine
from task_store import TaskStore


def setup_function():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def test_task_is_created_and_owned_by_user():
    store = TaskStore()
    task = store.create(1, "Book a table for two", "reservation", {"party_size": 2})
    assert task["status"] == "awaiting_confirmation"
    assert task["extracted_data"]["party_size"] == 2
    assert store.get(2, task["id"]) is None


def test_task_lifecycle_requires_confirmation_and_tracks_result():
    store = TaskStore()
    task = store.create(1, "Call the restaurant")
    queued = store.transition(1, task["id"], "queued")
    assert queued["status"] == "queued"
    running = store.transition(1, task["id"], "running")
    assert running["status"] == "running"
    completed = store.transition(1, task["id"], "completed", result="Restaurant confirmed")
    assert completed["result"] == "Restaurant confirmed"
    with pytest.raises(ValueError):
        store.transition(1, task["id"], "queued")


def test_task_cannot_skip_confirmation_or_be_changed_by_another_user():
    store = TaskStore()
    task = store.create(1, "Make a reservation")
    with pytest.raises(ValueError):
        store.transition(1, task["id"], "running")
    assert store.transition(2, task["id"], "cancelled") is None


def test_missing_details_move_task_to_confirmation():
    store = TaskStore()
    task = store.create(1, "Book a table", extracted_data={"missing_fields": ["date"]}, initial_status="awaiting_user_input")
    with pytest.raises(ValueError):
        store.transition(1, task["id"], "awaiting_confirmation")
    updated = store.update_details(1, task["id"], {"date": "tomorrow"}, missing_fields=[])
    assert updated["status"] == "awaiting_confirmation"
    assert updated["extracted_data"]["date"] == "tomorrow"
    assert updated["extracted_data"]["clarification_question"] is None
