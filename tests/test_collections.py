from modules.db import count_mistakes, get_connection, initialize_database
from modules.mistakes import (
    add_favorite,
    add_mistake,
    count_favorites,
    list_favorites,
    list_mistakes,
    remove_favorite,
    remove_mistake,
)


def test_initialize_database_creates_favorites_table(tmp_path):
    db_path = tmp_path / "study_quest.db"
    initialize_database(db_path)

    with get_connection(db_path) as conn:
        tables = {
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }

    assert "favorites" in tables


def test_mistake_is_added_once_and_can_be_removed(seeded_db):
    assert add_mistake(1, "B", "A", seeded_db) is True
    assert add_mistake(1, "C", "A", seeded_db) is False
    assert count_mistakes(seeded_db) == 1
    assert list_mistakes(seeded_db)[0]["user_answer"] == "C"

    remove_mistake(1, seeded_db)

    assert count_mistakes(seeded_db) == 0


def test_mistakes_can_be_filtered_by_subject(seeded_db):
    add_mistake(1, "B", "A", seeded_db)
    add_mistake(4, "False", "True", seeded_db)

    rows = list_mistakes(seeded_db, subject="Networking")

    assert len(rows) == 1
    assert rows[0]["subject"] == "Networking"


def test_favorite_is_added_once_and_can_be_removed(seeded_db):
    assert add_favorite(1, seeded_db) is True
    assert add_favorite(1, seeded_db) is False
    assert count_favorites(seeded_db) == 1
    assert list_favorites(seeded_db)[0]["question_id"] == 1

    remove_favorite(1, seeded_db)

    assert count_favorites(seeded_db) == 0


def test_favorites_can_be_filtered_by_subject(seeded_db):
    add_favorite(1, seeded_db)
    add_favorite(4, seeded_db)

    rows = list_favorites(seeded_db, subject="Python")

    assert len(rows) == 1
    assert rows[0]["subject"] == "Python"
