from pathlib import Path

from streamlit.testing.v1 import AppTest


APP_PATH = Path(__file__).resolve().parent.parent / "app.py"


def _load_app() -> AppTest:
    return AppTest.from_file(str(APP_PATH)).run(timeout=10)


def test_navigation_includes_v02_pages():
    app = _load_app()

    assert app.sidebar.radio[0].options == [
        "Home",
        "Import CSV",
        "AI Generate",
        "Quiz",
        "Mistakes",
        "Favorites",
    ]


def test_home_displays_v02_status():
    app = _load_app()

    assert any("V0.2" in element.value for element in app.markdown)


def test_quiz_page_renders_filters_and_start_action():
    app = _load_app()
    app.sidebar.radio[0].set_value("Quiz").run(timeout=10)

    assert app.header[0].value == "Quiz"
    assert len(app.selectbox) == 2
    assert app.number_input[0].value == 5
    assert app.button[0].label == "Start Quiz"


def test_collection_pages_render_without_errors():
    app = _load_app()

    app.sidebar.radio[0].set_value("Mistakes").run(timeout=10)
    assert app.header[0].value == "Mistakes"
    assert not app.exception

    app.sidebar.radio[0].set_value("Favorites").run(timeout=10)
    assert app.header[0].value == "Favorites"
    assert not app.exception
