import json

import pytest

from modules.db import get_connection, initialize_database


@pytest.fixture
def seeded_db(tmp_path):
    db_path = tmp_path / "study_quest.db"
    initialize_database(db_path)
    questions = [
        ("Python", "single_choice", "Python single 1?", ["A. One", "B. Two"], "A"),
        ("Python", "single_choice", "Python single 2?", ["A. One", "B. Two"], "B"),
        ("Python", "multiple_choice", "Python multiple?", ["A. One", "B. Two", "C. Three"], '["A", "C"]'),
        ("Networking", "true_false", "TCP is connection-oriented.", [], "True"),
        ("Networking", "short_answer", "Explain TCP.", [], "A transport protocol."),
    ]
    with get_connection(db_path) as conn:
        conn.executemany(
            """
            INSERT INTO questions (
                source, subject, type, stem, options, answer, explanation, tags, difficulty
            ) VALUES ('test', ?, ?, ?, ?, ?, 'Explanation', '', 'easy')
            """,
            [
                (subject, question_type, stem, json.dumps(options), answer)
                for subject, question_type, stem, options, answer in questions
            ],
        )
        conn.commit()
    return db_path
