from pathlib import Path

import pandas as pd

from modules.db import clear_all_questions, count_mistakes, count_questions, get_connection, initialize_database
from modules.importer import import_questions_csv
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
