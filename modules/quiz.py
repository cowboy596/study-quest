from __future__ import annotations

import json
import re


def parse_options(value: str) -> list[str]:
    try:
        parsed = json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return []
    if not isinstance(parsed, list):
        return []
    return [str(option) for option in parsed]


def _option_label(value: object) -> str:
    match = re.match(r"^\s*([A-Za-z])(?:[.、:)\s]|$)", str(value))
    return match.group(1).upper() if match else str(value).strip().upper()


def format_answer_with_options(answer: object, options: list[str]) -> str:
    if answer is None or answer == "":
        return "No answer"

    values: list[object]
    if isinstance(answer, list):
        values = answer
    elif isinstance(answer, str):
        try:
            parsed = json.loads(answer)
        except json.JSONDecodeError:
            values = re.split(r"[,;，；]", answer) if re.search(r"[,;，；]", answer) else [answer]
        else:
            values = parsed if isinstance(parsed, list) else [parsed]
    else:
        values = [answer]

    option_lookup = {_option_label(option): option for option in options}
    displayed = [
        option_lookup.get(_option_label(value), str(value).strip())
        for value in values
    ]
    return ", ".join(displayed)


def get_display_options(question_type: str, options: list[str]) -> list[str]:
    if question_type in {"single_choice", "multiple_choice"}:
        return options
    if question_type == "true_false":
        return ["True", "False"]
    return []


def build_quiz_stats(results: list[dict[str, object]]) -> dict[str, int | float]:
    correct = sum(result.get("status") == "correct" for result in results)
    incorrect = sum(result.get("status") == "incorrect" for result in results)
    self_check = sum(result.get("status") == "self_check" for result in results)
    auto_graded = correct + incorrect
    accuracy = round(correct / auto_graded * 100, 2) if auto_graded else 0.0
    return {
        "total": len(results),
        "auto_graded": auto_graded,
        "correct": correct,
        "incorrect": incorrect,
        "accuracy": accuracy,
        "self_check": self_check,
    }
