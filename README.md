# StudyQuest

StudyQuest is a local personal question-practice web tool. V0.2 supports duplicate-safe CSV import, filtered random quizzes, objective-question grading, explanations, automatic mistake collection, and manual favorites.

## Install

```powershell
cd C:\Users\Admin\Documents\Codex\2026-06-26\studyquest-v0-1-web-ai-api\outputs\study-quest
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## Start

```powershell
python -m streamlit run app.py
```

## Verify CSV Import

1. Start the app.
2. Open the `Import CSV` page.
3. Upload `examples/sample_questions.csv`.
4. Click `Import`.
5. Return to `Home` and confirm the question count is `5`.
6. Import the same file again and confirm `Duplicate questions skipped` is `5` and the total stays `5`.

Command-line verification:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
python -m pytest
```

## Verify Quiz and Collections

1. Import `examples/sample_questions.csv` if the question bank is empty.
2. Open `Quiz`, choose filters and a question count, then click `Start Quiz`.
3. Answer and submit. Confirm objective results, reference answers, explanations, and summary statistics appear.
4. Answer an objective question incorrectly and confirm it appears under `Mistakes` only once.
5. Click `Add to Favorites` on any submitted result and confirm it appears under `Favorites` only once.
6. Filter either collection by subject and test its remove action.

## V0.2 Scope

Included:

- SQLite database initialization.
- `questions`, `mistakes`, and `favorites` tables.
- Streamlit Home, Import CSV, AI Generate, Quiz, Mistakes, and Favorites pages.
- Sample CSV with 5 questions.
- Duplicate-question skipping based on subject, type, stem, and answer.
- Clear all questions button with explicit confirmation checkbox.
- Random quiz filtering by subject and type.
- Single-choice, multiple-choice, and true/false automatic grading.
- Short-answer self-check mode, excluded from accuracy.
- Incorrect objective questions automatically added to Mistakes.
- Manual question saving to Favorites.

Not included:

- Login.
- Real AI API calls.
- Automatic short-answer grading.
- PDF, Word, or OCR import.
- Learning-history charts.
