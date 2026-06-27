from __future__ import annotations

import json
import re
from collections.abc import Iterable


def _normalize_option(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    match = re.match(r"^([A-Za-z])(?:[.、:)\s]|$)", text)
    return match.group(1).upper() if match else text.upper()


def _as_option_set(value: object) -> set[str]:
    values: Iterable[object]
    if isinstance(value, str):
        text = value.strip()
        try:
            parsed = json.loads(text)
        except (json.JSONDecodeError, TypeError):
            values = re.split(r"[,;，；]", text) if text else []
        else:
            values = parsed if isinstance(parsed, list) else [parsed]
    elif isinstance(value, Iterable):
        values = value
    else:
        values = [value]
    return {normalized for item in values if (normalized := _normalize_option(item))}


def _normalize_boolean(value: object) -> str:
    normalized = str(value).strip().lower() if value is not None else ""
    if normalized in {"true", "t", "1", "yes", "正确", "对", "是"}:
        return "true"
    if normalized in {"false", "f", "0", "no", "错误", "错", "否"}:
        return "false"
    return normalized


def grade_answer(
    question_type: str,
    user_answer: object,
    correct_answer: object,
) -> str:
    if question_type == "short_answer":
        return "self_check"
    if question_type == "multiple_choice":
        return (
            "correct"
            if _as_option_set(user_answer) == _as_option_set(correct_answer)
            else "incorrect"
        )
    if question_type == "true_false":
        return (
            "correct"
            if _normalize_boolean(user_answer) == _normalize_boolean(correct_answer)
            and _normalize_boolean(user_answer) != ""
            else "incorrect"
        )
    if question_type == "single_choice":
        return (
            "correct"
            if _normalize_option(user_answer) == _normalize_option(correct_answer)
            and _normalize_option(user_answer) != ""
            else "incorrect"
        )
    raise ValueError(f"Unsupported question type: {question_type}")
