# Decision Log

## 2026-06-26

- Use SQLite directly through `sqlite3` for V0.1 to keep setup local and simple.
- Use Streamlit sidebar navigation instead of a full routing framework.
- Store `options` as a JSON string in the database for simple CSV compatibility.
- Reserve python-dotenv without loading real API credentials in V0.1.
- For V0.1.1, skip duplicate questions using `subject + type + stem + answer` instead of comparing every field, so explanations and tags can be corrected later without multiplying the same question.

## 2026-06-27

- Keep grading rules in a pure module so objective-question behavior is testable without Streamlit.
- Store active quizzes and submitted results in Streamlit session state.
- Automatically add only incorrect objective questions to Mistakes; short answers remain self-check in V0.2.
- Send all manual save actions to a separate Favorites collection so mistakes retain their diagnostic meaning.
- Enforce one Mistakes and one Favorites row per question with unique SQLite indexes.
