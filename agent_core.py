"""LLM-backed task understanding and safe execution planning for Adam."""

import json

from openai import OpenAI

from config import settings


SYSTEM_PROMPT = """You are Adam, an Egyptian-Arabic-first autonomous assistant task planner.
Convert the user request into a compact, safe, structured execution plan.
Return JSON only with these keys:
- task_type: one of reservation, business_call, reminder, information, general
- summary: short summary in the user language
- extracted_data: object containing only facts explicitly stated or safely inferred
- missing_fields: array of required details that must be asked before execution
- clarification_question: one concise question in the user language, or null
- proposed_steps: array of short steps
- requires_confirmation: boolean, true for any external side effect
- safe_to_execute: always false in this planning stage
For restaurant reservations, consider restaurant_name, date, time, party_size, and location.
Do not invent missing details, availability, successful calls, or confirmations.
Do not claim to have contacted anyone or executed an action.
If details are missing, ask only the most useful next question.
Keep the response concise and use Egyptian Arabic when the user writes in Arabic."""


def normalize_plan(data: dict, original_instruction: str) -> dict:
    allowed_types = {"reservation", "business_call", "reminder", "information", "general"}
    task_type = data.get("task_type")
    if task_type not in allowed_types:
        task_type = "general"
    extracted = data.get("extracted_data")
    if not isinstance(extracted, dict):
        extracted = {}
    missing = data.get("missing_fields")
    if not isinstance(missing, list):
        missing = []
    steps = data.get("proposed_steps")
    if not isinstance(steps, list):
        steps = []
    summary = data.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        summary = original_instruction
    question = data.get("clarification_question")
    if not isinstance(question, str) or not question.strip():
        question = None
    return {
        "task_type": task_type,
        "summary": summary.strip()[:2000],
        "extracted_data": extracted,
        "missing_fields": [str(item)[:120] for item in missing[:20]],
        "clarification_question": question[:1000] if question else None,
        "proposed_steps": [str(item)[:500] for item in steps[:20]],
        "requires_confirmation": bool(data.get("requires_confirmation", True)),
        "safe_to_execute": False,
    }


class AgentPlanner:
    """Uses the configured chat model to understand intent without executing it."""

    def __init__(self):
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is missing")
        self.client = OpenAI(api_key=settings.openai_api_key)

    def plan(self, instruction: str, history: list[dict] | None = None) -> dict:
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        if history:
            messages.extend(history[-8:])
        messages.append({"role": "user", "content": instruction})
        response = self.client.chat.completions.create(
            model=settings.openai_chat_model,
            messages=messages,
            temperature=0.2,
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content or "{}"
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            raise ValueError("The AI planner returned invalid structured output") from exc
        if not isinstance(parsed, dict):
            raise ValueError("The AI planner returned an invalid plan")
        return normalize_plan(parsed, instruction)
