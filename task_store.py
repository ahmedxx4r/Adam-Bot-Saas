"""Persistent, account-scoped task lifecycle storage."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select

from database import SessionLocal
from database_models import AgentTask

TASK_STATUSES = {"draft", "awaiting_confirmation", "queued", "running", "completed", "failed", "cancelled", "needs_human"}
TERMINAL_STATUSES = {"completed", "failed", "cancelled"}


class TaskStore:
    def create(self, user_id: int, input_text: str, task_type: str = "general", extracted_data: dict | None = None, initial_status: str = "awaiting_confirmation"):
        task = AgentTask(
            id=str(uuid4()), user_id=user_id, task_type=task_type,
            status=initial_status, input_text=input_text,
            extracted_data=json.dumps(extracted_data or {}, ensure_ascii=False),
        )
        with SessionLocal() as db:
            db.add(task)
            db.commit()
            db.refresh(task)
            return self._serialize(task)

    def get(self, user_id: int, task_id: str):
        with SessionLocal() as db:
            task = db.scalar(select(AgentTask).where(AgentTask.id == task_id, AgentTask.user_id == user_id))
            return self._serialize(task) if task else None

    def list(self, user_id: int, limit: int = 50):
        with SessionLocal() as db:
            tasks = db.scalars(
                select(AgentTask).where(AgentTask.user_id == user_id)
                .order_by(AgentTask.created_at.desc()).limit(limit)
            ).all()
            return [self._serialize(task) for task in tasks]

    def update_details(self, user_id: int, task_id: str, details: dict, missing_fields: list[str] | None = None):
        with SessionLocal() as db:
            task = db.scalar(select(AgentTask).where(AgentTask.id == task_id, AgentTask.user_id == user_id))
            if task is None:
                return None
            if task.status != "awaiting_user_input":
                raise ValueError("Task is not waiting for user input")
            current = json.loads(task.extracted_data or "{}")
            current.update(details)
            if missing_fields is not None:
                current["missing_fields"] = [str(item)[:120] for item in missing_fields[:20]]
            if not current.get("missing_fields"):
                current["clarification_question"] = None
                task.status = "awaiting_confirmation"
            task.extracted_data = json.dumps(current, ensure_ascii=False)
            task.updated_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(task)
            return self._serialize(task)
    def transition(self, user_id: int, task_id: str, new_status: str, result: str | None = None, error: str | None = None):
        if new_status not in TASK_STATUSES:
            raise ValueError("Invalid task status")
        with SessionLocal() as db:
            task = db.scalar(select(AgentTask).where(AgentTask.id == task_id, AgentTask.user_id == user_id))
            if task is None:
                return None
            if task.status in TERMINAL_STATUSES:
                raise ValueError("Terminal tasks cannot be changed")
            allowed = {
                "awaiting_user_input": {"cancelled"},
                "awaiting_confirmation": {"queued", "cancelled"},
                "queued": {"running", "cancelled"},
                "running": {"completed", "failed", "needs_human", "cancelled"},
                "needs_human": {"queued", "cancelled"},
            }
            if new_status not in allowed.get(task.status, set()):
                raise ValueError(f"Cannot transition task from {task.status} to {new_status}")
            task.status = new_status
            task.result = result if result is not None else task.result
            task.error = error if error is not None else task.error
            task.updated_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(task)
            return self._serialize(task)

    @staticmethod
    def _serialize(task):
        if task is None:
            return None
        return {
            "id": task.id, "task_type": task.task_type, "status": task.status,
            "input_text": task.input_text,
            "extracted_data": json.loads(task.extracted_data or "{}"),
            "result": task.result, "error": task.error,
            "created_at": task.created_at.isoformat() if task.created_at else None,
            "updated_at": task.updated_at.isoformat() if task.updated_at else None,
        }
