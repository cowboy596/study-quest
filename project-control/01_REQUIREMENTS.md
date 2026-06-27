# Requirements

## V0.2 In Scope

- Python Streamlit app shell.
- SQLite database initialization.
- `questions` table.
- `mistakes` and `favorites` tables with one row per question.
- Home navigation with version, question, mistake, and favorite counts.
- CSV upload/import page.
- Placeholder AI Generate page.
- Quiz filtering, random selection, session persistence, answering, grading, explanations, and statistics.
- Automatic mistake collection for incorrect objective questions.
- Filterable, removable Mistakes and Favorites pages.
- Duplicate-question skipping based on `subject + type + stem + answer`.
- Import summary showing total rows, inserted rows, skipped duplicates, and current total.
- Clear all questions button with explicit warning and confirmation checkbox.
- Sample CSV with at least 5 questions.
- Home page question count.

## Out of Scope

- Login and registration.
- Real AI API calls.
- Automatic short-answer grading.
- PDF, Word, or OCR import.
- Complex UI design.
- Learning-history charts.
