import json
from types import SimpleNamespace

import pytest

import modules.ai_generator as ai_generator
from modules.ai_generator import (
    AIModelMissingError,
    AIServiceUnavailableError,
    AIValidationError,
    build_prompt,
    generate_questions,
    get_ai_config,
    parse_question_batch,
)


def test_parse_valid_structured_response_normalizes_questions():
    payload = {
        "questions": [
            {
                "subject": "Computer Networks",
                "type": "multiple_choice",
                "stem": "Which protocols are transport-layer protocols?",
                "options": ["A. TCP", "B. UDP", "C. IP", "D. Ethernet"],
                "answer": "C,A",
                "explanation": "TCP and UDP are transport-layer protocols.",
                "tags": "network,protocol",
                "difficulty": "medium",
            }
        ]
    }

    questions = parse_question_batch(
        json.dumps(payload),
        requested_type="multiple_choice",
        requested_difficulty="medium",
    )

    assert questions == [
        {
            "subject": "Computer Networks",
            "type": "multiple_choice",
            "stem": "Which protocols are transport-layer protocols?",
            "options": ["A. TCP", "B. UDP", "C. IP", "D. Ethernet"],
            "answer": "A,C",
            "explanation": "TCP and UDP are transport-layer protocols.",
            "tags": "network,protocol",
            "difficulty": "medium",
        }
    ]


def test_missing_required_field_raises_validation_error():
    payload = {
        "questions": [
            {
                "subject": "Computer Networks",
                "type": "single_choice",
                "stem": "Which protocol is connection-oriented?",
                "options": ["A. TCP", "B. UDP"],
                "answer": "A",
                "tags": "network",
                "difficulty": "easy",
            }
        ]
    }

    with pytest.raises(AIValidationError, match="explanation"):
        parse_question_batch(
            json.dumps(payload),
            requested_type="single_choice",
            requested_difficulty="easy",
        )


def test_invalid_choice_answer_raises_validation_error():
    payload = {
        "questions": [
            {
                "subject": "Computer Networks",
                "type": "single_choice",
                "stem": "Which protocol is connection-oriented?",
                "options": ["A. TCP", "B. UDP"],
                "answer": "C",
                "explanation": "TCP is connection-oriented.",
                "tags": "network",
                "difficulty": "easy",
            }
        ]
    }

    with pytest.raises(AIValidationError, match="有效选项"):
        parse_question_batch(
            json.dumps(payload),
            requested_type="single_choice",
            requested_difficulty="easy",
        )


def test_true_false_answers_are_normalized():
    payload = {
        "questions": [
            {
                "subject": "Computer Networks",
                "type": "true_false",
                "stem": "TCP is connection-oriented.",
                "options": [],
                "answer": "正确",
                "explanation": "TCP establishes a connection before data transfer.",
                "tags": "network",
                "difficulty": "easy",
            }
        ]
    }

    questions = parse_question_batch(
        json.dumps(payload),
        requested_type="true_false",
        requested_difficulty="easy",
    )

    assert questions[0]["options"] == []
    assert questions[0]["answer"] == "True"


def test_build_prompt_contains_requested_constraints():
    prompt = build_prompt(
        subject="JavaScript closures",
        question_type="short_answer",
        question_count=3,
        difficulty="hard",
    )

    assert "JavaScript closures" in prompt
    assert "short_answer" in prompt
    assert "3" in prompt
    assert "hard" in prompt


def test_get_ai_config_does_not_require_api_key(monkeypatch):
    monkeypatch.delenv("AI_API_KEY", raising=False)
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
    monkeypatch.delenv("OLLAMA_MODEL", raising=False)

    config = get_ai_config()

    assert config.base_url == "http://localhost:11434"
    assert config.model == "qwen3:8b"


def test_generate_questions_maps_unavailable_service():
    class FailingClient:
        def chat(self, **kwargs):
            raise ConnectionError("connection refused")

    with pytest.raises(AIServiceUnavailableError):
        generate_questions(
            subject="Networking",
            question_type="single_choice",
            question_count=1,
            difficulty="easy",
            client_factory=lambda base_url: FailingClient(),
        )


def test_generate_questions_maps_windows_connection_reset():
    class FailingClient:
        def chat(self, **kwargs):
            raise RuntimeError("[WinError 10054] 远程主机强迫关闭了一个现有的连接。")

    with pytest.raises(AIServiceUnavailableError):
        generate_questions(
            subject="Networking",
            question_type="single_choice",
            question_count=1,
            difficulty="easy",
            client_factory=lambda base_url: FailingClient(),
        )


def test_generate_questions_maps_bad_gateway_from_local_service():
    class FailingClient:
        def chat(self, **kwargs):
            raise RuntimeError("(status code: 502)")

    with pytest.raises(AIServiceUnavailableError):
        generate_questions(
            subject="Networking",
            question_type="single_choice",
            question_count=1,
            difficulty="easy",
            client_factory=lambda base_url: FailingClient(),
        )


def test_generate_questions_maps_missing_model():
    class FailingClient:
        def chat(self, **kwargs):
            raise RuntimeError("model 'qwen3:8b' not found, try pulling it first")

    with pytest.raises(AIModelMissingError, match="qwen3:8b"):
        generate_questions(
            subject="Networking",
            question_type="single_choice",
            question_count=1,
            difficulty="easy",
            client_factory=lambda base_url: FailingClient(),
        )


def test_generate_questions_uses_raw_ollama_http_by_default(monkeypatch):
    payload = {
        "questions": [
            {
                "subject": "Networking",
                "type": "single_choice",
                "stem": "Which protocol is connection-oriented?",
                "options": ["A. TCP", "B. UDP"],
                "answer": "A",
                "explanation": "TCP establishes a connection before data transfer.",
                "tags": "network,protocol",
                "difficulty": "easy",
            }
        ]
    }
    calls = []

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"message": {"content": json.dumps(payload)}}

    def fake_post(url, json=None, timeout=None):
        calls.append((url, json, timeout))
        return FakeResponse()

    monkeypatch.setattr(
        ai_generator,
        "requests",
        SimpleNamespace(post=fake_post),
        raising=False,
    )

    questions = generate_questions(
        subject="Networking",
        question_type="single_choice",
        question_count=1,
        difficulty="easy",
    )

    assert calls[0][0] == "http://localhost:11434/api/chat"
    assert calls[0][1]["model"] == "qwen3:8b"
    assert calls[0][1]["stream"] is False
    assert questions[0]["answer"] == "A"
