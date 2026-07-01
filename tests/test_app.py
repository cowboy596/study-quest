from pathlib import Path

from streamlit.testing.v1 import AppTest

import app as studyquest_app


APP_PATH = Path(__file__).resolve().parent.parent / "app.py"


def _load_app() -> AppTest:
    return AppTest.from_file(str(APP_PATH)).run(timeout=10)


def test_navigation_includes_chinese_pages():
    app = _load_app()

    assert app.sidebar.radio[0].options == [
        "首页",
        "导入题库",
        "AI 出题",
        "刷题",
        "复习",
        "错题集",
        "管理",
        "Dashboard",
    ]


def test_home_displays_v07_status():
    app = _load_app()

    assert any("V0.7" in element.value for element in app.markdown)


def test_import_page_accepts_multi_format_uploads():
    app = _load_app()
    app.sidebar.radio[0].set_value("导入题库").run(timeout=10)

    assert app.file_uploader[0].label == "上传题库文件"
    assert studyquest_app.SUPPORTED_IMPORT_TYPES == ["csv", "xlsx", "json", "md", "txt"]


def test_ai_generate_page_renders_chinese_controls():
    app = _load_app()
    app.sidebar.radio[0].set_value("AI 出题").run(timeout=10)

    assert app.header[0].value == "AI 出题"
    assert app.text_input[0].label == "科目 / 主题"
    assert app.selectbox[0].label == "题型"
    assert app.number_input[0].label == "生成数量"
    assert app.selectbox[1].label == "难度"
    assert app.button[0].label == "生成题目"


def test_ai_generated_preview_hides_answer_and_explanation():
    question = {
        "subject": "API",
        "type": "single_choice",
        "difficulty": "medium",
        "stem": "Which method retrieves data?",
        "options": ["A. GET", "B. POST"],
        "answer": "A",
        "explanation": "GET retrieves data.",
        "tags": "api,http",
    }

    items = studyquest_app._generated_question_preview_items(question)
    labels = [label for label, _value in items]

    assert labels == ["科目", "题型", "难度", "题干", "选项", "标签"]


def test_quiz_result_collection_actions_include_mistakes_and_favorites():
    labels = studyquest_app._quiz_result_collection_action_labels()

    assert labels == ["加入错题集", "加入收藏夹"]


def test_frontend_value_labels_are_chinese():
    assert studyquest_app._display_question_type("single_choice") == "单选题"
    assert studyquest_app._display_question_type("multiple_choice") == "多选题"
    assert studyquest_app._display_question_type("true_false") == "判断题"
    assert studyquest_app._display_question_type("short_answer") == "简答题"
    assert studyquest_app._display_difficulty("easy") == "简单"
    assert studyquest_app._display_difficulty("medium") == "中等"
    assert studyquest_app._display_difficulty("hard") == "困难"
    assert studyquest_app._display_answer("True") == "正确"
    assert studyquest_app._display_answer("False") == "错误"


def test_quiz_page_renders_filters_and_start_action():
    app = _load_app()
    app.sidebar.radio[0].set_value("刷题").run(timeout=10)

    assert app.header[0].value == "刷题"
    assert len(app.selectbox) == 2
    assert app.number_input[0].value == 5
    assert app.button[0].label == "开始刷题"


def test_mistakes_page_renders_without_errors():
    app = _load_app()

    app.sidebar.radio[0].set_value("错题集").run(timeout=10)
    assert app.header[0].value == "错题集"
    assert not app.exception


def test_manage_page_renders_filters_and_summary():
    app = _load_app()
    app.sidebar.radio[0].set_value("管理").run(timeout=10)

    assert app.header[0].value == "题库管理"
    assert app.selectbox[0].label == "科目"
    assert app.selectbox[1].label == "题型"
    assert app.selectbox[2].label == "学习状态"
    assert app.text_input[0].label == "题干关键词"
    assert not app.exception


def test_review_page_renders_filters_and_start_action():
    app = _load_app()
    app.sidebar.radio[0].set_value("复习").run(timeout=10)

    assert app.header[0].value == "复习"
    assert app.selectbox[0].label == "复习模式"
    assert app.selectbox[1].label == "科目"
    assert app.selectbox[2].label == "题型"
    assert app.number_input[0].value == 5
    assert app.button[0].label == "开始复习"


def test_dashboard_page_renders_without_breaking_navigation_pages():
    app = _load_app()
    app.sidebar.radio[0].set_value("Dashboard").run(timeout=10)

    assert app.header[0].value == "Dashboard"
    assert not app.exception

    for page_name, header in [
        ("首页", "首页"),
        ("刷题", "刷题"),
        ("复习", "复习"),
        ("管理", "题库管理"),
        ("错题集", "错题集"),
    ]:
        app.sidebar.radio[0].set_value(page_name).run(timeout=10)
        assert app.header[0].value == header
        assert not app.exception
