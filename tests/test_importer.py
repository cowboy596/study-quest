import json
from pathlib import Path

import pandas as pd
import pytest

from modules.db import (
    clear_all_questions,
    count_mistakes,
    count_questions,
    get_connection,
    get_random_questions,
    initialize_database,
)
from modules.importer import ImportValidationError, import_questions_csv, parse_questions_file, save_questions
from modules.mistakes import add_favorite, count_favorites


def test_initialize_database_creates_required_tables(tmp_path):
    db_path = tmp_path / "study_quest.db"

    initialize_database(db_path)

    import sqlite3

    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()

    assert ("questions",) in rows
    assert ("mistakes",) in rows


def test_import_questions_csv_persists_rows(tmp_path):
    db_path = tmp_path / "study_quest.db"
    csv_path = tmp_path / "questions.csv"
    pd.DataFrame(
        [
            {
                "subject": "Networking",
                "type": "single_choice",
                "stem": "Which protocol is connection-oriented?",
                "options": '["A. TCP","B. UDP","C. IP","D. ICMP"]',
                "answer": "A",
                "explanation": "TCP establishes a connection before transferring data.",
                "tags": "network,protocol",
                "difficulty": "easy",
            }
        ]
    ).to_csv(csv_path, index=False)

    initialize_database(db_path)
    result = import_questions_csv(csv_path, db_path, source="unit-test.csv")

    assert result.total_rows == 1
    assert result.inserted_rows == 1
    assert result.skipped_duplicates == 0
    assert count_questions(db_path) == 1


def test_import_questions_csv_skips_duplicate_questions(tmp_path):
    db_path = tmp_path / "study_quest.db"
    csv_path = tmp_path / "questions.csv"
    pd.DataFrame(
        [
            {
                "subject": "Networking",
                "type": "single_choice",
                "stem": "Which protocol is connection-oriented?",
                "options": '["A. TCP","B. UDP","C. IP","D. ICMP"]',
                "answer": "A",
                "explanation": "TCP establishes a connection before transferring data.",
                "tags": "network,protocol",
                "difficulty": "easy",
            }
        ]
    ).to_csv(csv_path, index=False)

    initialize_database(db_path)
    first = import_questions_csv(csv_path, db_path, source="unit-test.csv")
    second = import_questions_csv(csv_path, db_path, source="unit-test.csv")

    assert first.inserted_rows == 1
    assert second.total_rows == 1
    assert second.inserted_rows == 0
    assert second.skipped_duplicates == 1
    assert count_questions(db_path) == 1


def test_clear_all_questions_removes_questions_and_mistakes(tmp_path):
    db_path = tmp_path / "study_quest.db"
    initialize_database(db_path)

    with get_connection(db_path) as conn:
        conn.execute(
            """
            INSERT INTO questions (
                source, subject, type, stem, options, answer, explanation, tags, difficulty
            )
            VALUES ('test', 'Python', 'single_choice', 'Stem?', '[]', 'A', '', '', 'easy')
            """
        )
        question_id = conn.execute("SELECT id FROM questions").fetchone()["id"]
        conn.execute(
            """
            INSERT INTO mistakes (question_id, user_answer, correct_answer)
            VALUES (?, 'B', 'A')
            """,
            (question_id,),
        )
        conn.commit()

    add_favorite(question_id, db_path)

    clear_all_questions(db_path)

    assert count_questions(db_path) == 0
    assert count_mistakes(db_path) == 0
    assert count_favorites(db_path) == 0


def test_save_questions_persists_ai_source_and_serializes_options(tmp_path):
    db_path = tmp_path / "study_quest.db"

    result = save_questions(
        [
            {
                "subject": "JavaScript",
                "type": "single_choice",
                "stem": "Which keyword creates a block-scoped variable?",
                "options": ["A. var", "B. let", "C. function", "D. this"],
                "answer": "B",
                "explanation": "let creates a block-scoped variable.",
                "tags": "javascript,scope",
                "difficulty": "easy",
            }
        ],
        db_path=db_path,
        source="ai",
    )

    assert result.total_rows == 1
    assert result.inserted_rows == 1
    assert result.skipped_duplicates == 0
    with get_connection(db_path) as conn:
        row = conn.execute("SELECT * FROM questions").fetchone()
    assert row["source"] == "ai"
    assert row["options"] == '["A. var", "B. let", "C. function", "D. this"]'


def test_save_questions_skips_duplicate_ai_questions(tmp_path):
    db_path = tmp_path / "study_quest.db"
    question = {
        "subject": "JavaScript",
        "type": "single_choice",
        "stem": "Which keyword creates a block-scoped variable?",
        "options": ["A. var", "B. let", "C. function", "D. this"],
        "answer": "B",
        "explanation": "let creates a block-scoped variable.",
        "tags": "javascript,scope",
        "difficulty": "easy",
    }

    first = save_questions([question], db_path=db_path, source="ai")
    second = save_questions([question], db_path=db_path, source="ai")

    assert first.inserted_rows == 1
    assert second.total_rows == 1
    assert second.inserted_rows == 0
    assert second.skipped_duplicates == 1
    assert count_questions(db_path) == 1


def test_saved_ai_questions_are_available_to_quiz_queries(tmp_path):
    db_path = tmp_path / "study_quest.db"
    save_questions(
        [
            {
                "subject": "JavaScript",
                "type": "true_false",
                "stem": "Closures can access variables from outer scopes.",
                "options": [],
                "answer": "True",
                "explanation": "Closures retain access to lexical scope.",
                "tags": "javascript,closure",
                "difficulty": "medium",
            }
        ],
        db_path=db_path,
        source="ai",
    )

    rows = get_random_questions(
        db_path,
        subject="JavaScript",
        question_type="true_false",
        count=1,
    )

    assert len(rows) == 1
    assert rows[0]["source"] == "ai"


def _question_row(**overrides):
    row = {
        "subject": "Networking",
        "type": "single_choice",
        "stem": "Which protocol is connection-oriented?",
        "options": ["A. TCP", "B. UDP", "C. IP", "D. HTTP"],
        "answer": "A",
        "explanation": "TCP establishes a connection before data transfer.",
        "tags": "network,protocol",
        "difficulty": "easy",
    }
    row.update(overrides)
    return row


def test_parse_csv_file_returns_preview_questions(tmp_path):
    path = tmp_path / "questions.csv"
    pd.DataFrame([{**_question_row(), "options": json.dumps(_question_row()["options"])}]).to_csv(path, index=False)

    result = parse_questions_file(path)

    assert result.total_rows == 1
    assert result.failed_rows == 0
    assert result.questions[0]["answer"] == "A"


def test_parse_xlsx_file_returns_preview_questions(tmp_path):
    path = tmp_path / "questions.xlsx"
    pd.DataFrame([{**_question_row(), "options": json.dumps(_question_row()["options"])}]).to_excel(path, index=False)

    result = parse_questions_file(path)

    assert result.total_rows == 1
    assert result.failed_rows == 0
    assert result.questions[0]["subject"] == "Networking"


def test_parse_json_object_format_returns_questions(tmp_path):
    path = tmp_path / "questions.json"
    path.write_text(json.dumps({"questions": [_question_row()]}), encoding="utf-8")

    result = parse_questions_file(path)

    assert result.total_rows == 1
    assert result.failed_rows == 0
    assert result.questions[0]["options"] == ["A. TCP", "B. UDP", "C. IP", "D. HTTP"]


def test_parse_json_list_format_returns_questions(tmp_path):
    path = tmp_path / "questions.json"
    path.write_text(json.dumps([_question_row(type="true_false", options=[], answer="True")]), encoding="utf-8")

    result = parse_questions_file(path)

    assert result.total_rows == 1
    assert result.failed_rows == 0
    assert result.questions[0]["type"] == "true_false"


def test_parse_markdown_template_returns_questions(tmp_path):
    path = tmp_path / "questions.md"
    path.write_text(
        """---
subject: 计算机网络
type: single_choice
difficulty: medium
tags: TCP/IP
stem: TCP 协议属于哪一层？
options:
A. 应用层
B. 传输层
C. 网络层
D. 数据链路层
answer: B
explanation: TCP 是传输层协议，负责端到端可靠传输。
---""",
        encoding="utf-8",
    )

    result = parse_questions_file(path)

    assert result.total_rows == 1
    assert result.failed_rows == 0
    assert result.questions[0]["answer"] == "B"
    assert result.questions[0]["options"] == ["A. 应用层", "B. 传输层", "C. 网络层", "D. 数据链路层"]


def test_parse_txt_template_returns_questions(tmp_path):
    path = tmp_path / "questions.txt"
    path.write_text(
        """---
subject: Python
type: short_answer
difficulty: easy
tags: function
stem: 什么是 Python 函数？
options:
answer: 可复用的代码块。
explanation: 函数用于封装可重复调用的逻辑。
---""",
        encoding="utf-8",
    )

    result = parse_questions_file(path)

    assert result.total_rows == 1
    assert result.failed_rows == 0
    assert result.questions[0]["options"] == []


def test_parse_markdown_partial_template_error_keeps_valid_questions(tmp_path):
    path = tmp_path / "mixed.md"
    path.write_text(
        """---
subject: Networking
type: single_choice
difficulty: easy
tags: network
stem: Which protocol is connection-oriented?
options:
A. TCP
B. UDP
answer: A
explanation: TCP establishes a connection.
---
this line does not match the template
---""",
        encoding="utf-8",
    )

    result = parse_questions_file(path)

    assert result.total_rows == 2
    assert len(result.questions) == 1
    assert result.failed_rows == 1
    assert "template" in result.errors[0]


def test_parse_missing_required_field_reports_error(tmp_path):
    path = tmp_path / "bad.json"
    row = _question_row()
    del row["stem"]
    path.write_text(json.dumps({"questions": [row]}), encoding="utf-8")

    result = parse_questions_file(path)

    assert result.total_rows == 1
    assert result.failed_rows == 1
    assert result.questions == []
    assert "stem" in result.errors[0]


def test_parse_invalid_options_reports_error_without_crashing(tmp_path):
    path = tmp_path / "bad.csv"
    pd.DataFrame([{**_question_row(), "options": "not-json"}]).to_csv(path, index=False)

    result = parse_questions_file(path)

    assert result.total_rows == 1
    assert result.failed_rows == 1
    assert result.questions == []
    assert "options" in result.errors[0]


def test_parse_unsupported_format_raises_validation_error(tmp_path):
    path = tmp_path / "questions.pdf"
    path.write_text("not supported", encoding="utf-8")

    with pytest.raises(ImportValidationError, match="不支持的文件格式"):
        parse_questions_file(path)


def test_multi_format_save_skips_duplicates_and_quiz_can_read(tmp_path):
    db_path = tmp_path / "study_quest.db"
    path = tmp_path / "questions.json"
    path.write_text(json.dumps({"questions": [_question_row()]}), encoding="utf-8")
    parsed = parse_questions_file(path)

    first = save_questions(parsed.questions, db_path=db_path, source=path.name)
    second = save_questions(parsed.questions, db_path=db_path, source=path.name)
    rows = get_random_questions(db_path, subject="Networking", question_type="single_choice", count=1)

    assert first.inserted_rows == 1
    assert second.skipped_duplicates == 1
    assert len(rows) == 1
