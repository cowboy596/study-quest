from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Any, Callable

import requests
from dotenv import load_dotenv
from pydantic import BaseModel, Field, ValidationError, field_validator

SUPPORTED_QUESTION_TYPES = {
    "single_choice",
    "multiple_choice",
    "true_false",
    "short_answer",
}
SUPPORTED_DIFFICULTIES = {"easy", "medium", "hard"}
DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_OLLAMA_MODEL = "qwen3:8b"


class AIGenerationError(RuntimeError):
    """Base exception for user-facing AI generation failures."""


class AIServiceUnavailableError(AIGenerationError):
    """Raised when the local Ollama service cannot be reached."""


class AIModelMissingError(AIGenerationError):
    """Raised when the configured Ollama model is not available locally."""


class AIValidationError(AIGenerationError):
    """Raised when the model response is not usable as StudyQuest questions."""


@dataclass(frozen=True)
class AIConfig:
    base_url: str = DEFAULT_OLLAMA_BASE_URL
    model: str = DEFAULT_OLLAMA_MODEL


class GeneratedQuestion(BaseModel):
    subject: str = Field(min_length=1)
    type: str = Field(min_length=1)
    stem: str = Field(min_length=1)
    options: list[str] = Field(default_factory=list)
    answer: str = Field(min_length=1)
    explanation: str = Field(min_length=1)
    tags: str = Field(min_length=1)
    difficulty: str = Field(min_length=1)

    @field_validator("subject", "type", "stem", "answer", "explanation", "tags", "difficulty")
    @classmethod
    def clean_required_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("field cannot be blank")
        return cleaned

    @field_validator("options")
    @classmethod
    def clean_options(cls, value: list[str]) -> list[str]:
        return [item.strip() for item in value if item and item.strip()]


class QuestionBatch(BaseModel):
    questions: list[GeneratedQuestion]


def get_ai_config() -> AIConfig:
    load_dotenv()
    import os

    return AIConfig(
        base_url=os.getenv("OLLAMA_BASE_URL", DEFAULT_OLLAMA_BASE_URL).strip()
        or DEFAULT_OLLAMA_BASE_URL,
        model=os.getenv("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL).strip()
        or DEFAULT_OLLAMA_MODEL,
    )


def build_prompt(
    subject: str,
    question_type: str,
    question_count: int,
    difficulty: str,
) -> str:
    return f"""
Generate {question_count} StudyQuest questions.

Constraints:
- subject/topic: {subject}
- type: {question_type}
- difficulty: {difficulty}
- Return only strict JSON matching the provided schema.
- Each item must include subject, type, stem, options, answer, explanation, tags, difficulty.
- single_choice and multiple_choice options must use labels such as "A. ...".
- multiple_choice answer must be comma-separated labels such as "A,C".
- true_false answer must be True or False.
- short_answer must include a concise reference answer and explanation.
""".strip()


def parse_question_batch(
    raw_json: str,
    requested_type: str,
    requested_difficulty: str,
) -> list[dict[str, object]]:
    try:
        batch = QuestionBatch.model_validate_json(raw_json)
    except ValidationError as exc:
        raise AIValidationError(f"AI 返回内容不符合题目结构：{exc}") from exc
    except ValueError as exc:
        raise AIValidationError("AI 返回内容不是合法 JSON。") from exc

    if not batch.questions:
        raise AIValidationError("AI 返回内容中没有题目。")

    return [
        _normalize_question(question, index, requested_type, requested_difficulty)
        for index, question in enumerate(batch.questions, start=1)
    ]


def generate_questions(
    subject: str,
    question_type: str,
    question_count: int,
    difficulty: str,
    config: AIConfig | None = None,
    client_factory: Callable[[str], Any] | None = None,
) -> list[dict[str, object]]:
    config = config or get_ai_config()
    prompt = build_prompt(subject, question_type, question_count, difficulty)

    messages = [
        {
            "role": "system",
            "content": "You generate local StudyQuest question banks as strict JSON.",
        },
        {"role": "user", "content": prompt},
    ]

    if client_factory is not None:
        client = _create_client(config.base_url, client_factory)
        try:
            response = client.chat(
                model=config.model,
                messages=messages,
                format=QuestionBatch.model_json_schema(),
                options={"temperature": 0},
                stream=False,
            )
        except Exception as exc:
            _raise_mapped_ollama_error(exc, config.model)
        content = _extract_response_content(response)
    else:
        content = _chat_ollama_http(config, messages)

    questions = parse_question_batch(content, question_type, difficulty)
    return questions[: max(1, int(question_count))]


def _create_client(
    base_url: str,
    client_factory: Callable[[str], Any] | None,
) -> Any:
    if client_factory is not None:
        return client_factory(base_url)
    try:
        from ollama import Client
    except ImportError as exc:
        raise AIServiceUnavailableError(
            "未安装 ollama Python 依赖，请先执行 pip install -r requirements.txt。"
        ) from exc
    return Client(host=base_url)


def _chat_ollama_http(config: AIConfig, messages: list[dict[str, str]]) -> str:
    url = f"{config.base_url.rstrip('/')}/api/chat"
    payload = {
        "model": config.model,
        "messages": messages,
        "format": QuestionBatch.model_json_schema(),
        "options": {"temperature": 0},
        "stream": False,
    }
    try:
        response = requests.post(url, json=payload, timeout=180)
        response.raise_for_status()
        data = response.json()
    except Exception as exc:
        _raise_mapped_ollama_error(exc, config.model)
    return _extract_response_content(data)


def _normalize_question(
    question: GeneratedQuestion,
    index: int,
    requested_type: str,
    requested_difficulty: str,
) -> dict[str, object]:
    if question.type not in SUPPORTED_QUESTION_TYPES:
        raise AIValidationError(f"第 {index} 题题型不受支持：{question.type}")
    if question.type != requested_type:
        raise AIValidationError(
            f"第 {index} 题题型为 {question.type}，但请求题型为 {requested_type}。"
        )
    if question.difficulty not in SUPPORTED_DIFFICULTIES:
        raise AIValidationError(
            f"第 {index} 题难度不受支持：{question.difficulty}"
        )
    if question.difficulty != requested_difficulty:
        raise AIValidationError(
            f"第 {index} 题难度为 {question.difficulty}，但请求难度为 {requested_difficulty}。"
        )

    options = question.options
    answer = question.answer.strip()
    if question.type in {"single_choice", "multiple_choice"}:
        labels = _option_labels(options)
        if len(labels) < 2:
            raise AIValidationError(f"第 {index} 题至少需要两个选项。")
        if question.type == "single_choice":
            answer = _normalize_single_choice_answer(answer, labels, index)
        else:
            answer = _normalize_multiple_choice_answer(answer, labels, index)
    elif question.type == "true_false":
        options = []
        answer = _normalize_true_false_answer(answer, index)
    else:
        options = []

    return {
        "subject": question.subject,
        "type": question.type,
        "stem": question.stem,
        "options": options,
        "answer": answer,
        "explanation": question.explanation,
        "tags": question.tags,
        "difficulty": question.difficulty,
    }


def _option_labels(options: list[str]) -> set[str]:
    labels: set[str] = set()
    for option in options:
        match = re.match(r"^\s*([A-Za-z])(?:[.)、]\s+|$)", option)
        if match:
            labels.add(match.group(1).upper())
    return labels


def _answer_labels(answer: str) -> list[str]:
    try:
        parsed = json.loads(answer)
    except json.JSONDecodeError:
        parts = re.split(r"[,;，；\s]+", answer)
    else:
        parts = parsed if isinstance(parsed, list) else [parsed]
    labels = []
    for part in parts:
        text = str(part).strip()
        if not text:
            continue
        match = re.match(r"^([A-Za-z])(?:[.)、]\s*.*)?$", text)
        labels.append(match.group(1).upper() if match else text.upper())
    return labels


def _normalize_single_choice_answer(answer: str, labels: set[str], index: int) -> str:
    answer_labels = _answer_labels(answer)
    if len(answer_labels) != 1 or answer_labels[0] not in labels:
        raise AIValidationError(f"第 {index} 题答案必须匹配有效选项标签。")
    return answer_labels[0]


def _normalize_multiple_choice_answer(answer: str, labels: set[str], index: int) -> str:
    answer_labels = _answer_labels(answer)
    if not answer_labels:
        raise AIValidationError(f"第 {index} 题答案至少需要一个选项标签。")
    if len(set(answer_labels)) != len(answer_labels):
        raise AIValidationError(f"第 {index} 题答案包含重复选项标签。")
    invalid = [label for label in answer_labels if label not in labels]
    if invalid:
        raise AIValidationError(
            f"第 {index} 题答案包含无效选项标签：{', '.join(invalid)}"
        )
    return ",".join(sorted(answer_labels))


def _normalize_true_false_answer(answer: str, index: int) -> str:
    normalized = answer.strip().lower()
    truthy = {"true", "t", "yes", "y", "correct", "right", "正确", "对", "是"}
    falsy = {"false", "f", "no", "n", "incorrect", "wrong", "错误", "错", "否"}
    if normalized in truthy:
        return "True"
    if normalized in falsy:
        return "False"
    raise AIValidationError(f"第 {index} 题判断题答案必须是 True/False 或 正确/错误。")


def _extract_response_content(response: Any) -> str:
    if isinstance(response, dict):
        try:
            return str(response["message"]["content"])
        except KeyError as exc:
            raise AIValidationError("Ollama 返回内容缺少 message.content。") from exc
    message = getattr(response, "message", None)
    content = getattr(message, "content", None)
    if content is None and isinstance(message, dict):
        content = message.get("content")
    if content is None:
        raise AIValidationError("Ollama 返回内容缺少 message.content。")
    return str(content)


def _raise_mapped_ollama_error(exc: Exception, model: str) -> None:
    message = str(exc)
    lowered = message.lower()
    if "model" in lowered and (
        "not found" in lowered or "pull" in lowered or "does not exist" in lowered
    ):
        raise AIModelMissingError(
            f"Ollama 模型 {model} 不可用，请执行：ollama pull {model}"
        ) from exc
    unavailable_tokens = [
        "connection",
        "refused",
        "timeout",
        "unreachable",
        "winerror 10054",
        "winerror 10061",
        "status code: 502",
        "status code: 503",
        "status code: 504",
        "远程主机",
        "连接",
    ]
    if any(token in lowered for token in unavailable_tokens):
        raise AIServiceUnavailableError(
            "本地 Ollama 服务不可用，请确认已安装并启动 Ollama。"
        ) from exc
    raise AIGenerationError(f"AI 生成请求失败：{message}") from exc
