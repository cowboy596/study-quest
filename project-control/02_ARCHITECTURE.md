# Architecture

## Stack

- Python
- Streamlit
- SQLite
- pandas
- python-dotenv reserved for future API configuration

## Modules

- `app.py`: Streamlit UI and navigation.
- `modules/db.py`: schema initialization, compatible indexes, counts, filters, and random question queries.
- `modules/importer.py`: CSV validation, duplicate-safe database insertion, import summary result.
- `modules/quiz.py`: option parsing and aggregate quiz statistics.
- `modules/grading.py`: pure answer normalization and objective-question grading.
- `modules/mistakes.py`: mistake and favorite persistence, listing, filtering, and removal.

## Data Flow

1. User uploads a CSV in Streamlit.
2. pandas reads and validates required columns.
3. importer inserts only new rows into SQLite and skips duplicates by `subject + type + stem + answer`.
4. Import page displays total rows, inserted rows, duplicate rows, and current total.
5. Home page queries question and mistake counts from SQLite.

## Quiz Data Flow

1. Quiz filters are converted to parameterized SQLite conditions.
2. Random matching rows are stored in Streamlit session state.
3. Submitted answers are normalized and graded by question type.
4. Incorrect objective questions are inserted or updated in `mistakes` by `question_id`.
5. Manual save actions insert into `favorites` by `question_id`.
6. Collection pages join saved records to `questions` for display and filtering.
