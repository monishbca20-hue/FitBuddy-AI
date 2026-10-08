# FitBuddy — AI Fitness Plan Generator

FitBuddy is a complete FastAPI application based on the supplied project brief. It includes a responsive Jinja2 website, SQLite persistence, seven-day workout plans, nutrition and recovery tips, feedback-based revisions, a coach dashboard, and JSON API endpoints.

The PDF describes the retired Gemini 1.5 Pro / Flash models and the older `google-generativeai` SDK. This implementation uses Google's current `google-genai` Python SDK and configurable model names. It starts in local demo mode with no API key, so you can explore the application before connecting Gemini. With no key, the plan and tip come from built-in deterministic examples; with a key, generation goes to Gemini.

> FitBuddy offers general fitness information, not medical advice. The generated suggestions are not a substitute for a clinician or qualified fitness professional. Users should stop for pain or concerning symptoms.

## Requirements

- Python 3.10 or newer (Python 3.11 or 3.12 recommended)
- Visual Studio Code
- Internet access only to install Python packages and, optionally, call Gemini
- A Gemini API key is optional; obtain one from [Google AI Studio](https://aistudio.google.com/app/apikey)

## Open in VS Code

1. Extract or copy the `FitBuddy` folder to a convenient location.
2. In VS Code, choose **File → Open Folder…** and select `FitBuddy`.
3. Open **Terminal → New Terminal**. Check Python with `python --version`.

Run the following in the VS Code terminal (PowerShell on Windows):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

If PowerShell blocks environment activation, run this once in that terminal and activate again:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

On macOS/Linux, use `source .venv/bin/activate` in place of the Windows activation line.

### Enable live Gemini generation (optional)

The Streamlit interface and FastAPI website both use the Gemini API when a key is configured. Open `.env` and set your key:

```dotenv
GEMINI_API_KEY=your_google_ai_studio_key
GEMINI_WORKOUT_MODEL=gemini-3-flash-preview
```

Get an API key from [Google AI Studio](https://aistudio.google.com/app/apikey). The key stays in `.env`, which is excluded from Git. If the configured model is unavailable for your account, change the model variables to IDs enabled for your Gemini API project. The Streamlit app also lets you enter an API key in its sidebar for the current session without saving it.

If the selected Streamlit model returns a temporary 503 overload error, FitBuddy automatically retries once with `gemini-3.1-flash-lite` and shows which model generated the plan.

### Run the Streamlit interface

The project includes a standalone Streamlit interface in `app.py`. With the virtual environment active and dependencies installed, start it with:

```powershell
streamlit run app.py
```

Open the local URL shown in the terminal (usually <http://localhost:8501>). Configure Gemini either in the sidebar or in `.env` as described above. Without a key, the interface explains how to configure Gemini and does not claim to generate an AI plan.

## Run the app

With the virtual environment active, start from the `FitBuddy` project folder:

```powershell
uvicorn app.main:app --reload
```

Open:

- Website: <http://127.0.0.1:8000>
- Interactive API reference: <http://127.0.0.1:8000/docs>
- Health and mode: <http://127.0.0.1:8000/api/health>

Stop the local server with **Ctrl+C**. The SQLite database (`fitbuddy.db`) is created automatically in the project folder on first run.

VS Code also includes a **FitBuddy (Uvicorn)** debug launch configuration under **Run and Debug**.

## Try the application

1. On the home page, enter a name, an ID such as `alex_01`, age, weight in kg, a goal, and intensity. Submit the form to see a seven-day plan and nutrition/recovery tip.
2. On the result page, enter feedback such as “make the cardio lower impact” and submit it. The revised plan is saved separately from the original.
3. To view the coach dashboard, set `ADMIN_TOKEN` to a private local value in `.env`, restart the app, and visit `http://127.0.0.1:8000/view-all-users?token=YOUR_TOKEN`. Replace `YOUR_TOKEN` with the value you set. The API admin routes accept the same value in the `X-Admin-Token` request header.
4. In `/docs`, try `GET /api/health`, `POST /api/plans`, `POST /api/plans/{user_id}/feedback`, and `GET /api/plans/{user_id}`. For `POST /api/plans`, use a body like:

```json
{
  "username": "Alex Morgan",
  "user_id": "alex_01",
  "age": 28,
  "weight_kg": 68,
  "goal": "general_wellness",
  "intensity": "medium"
}
```

Valid goals: `weight_loss`, `muscle_gain`, `general_wellness`, `flexibility`. Valid intensities: `low`, `medium`, `high`. API errors use standard HTTP error responses and FastAPI validation messages.

## Routes and project layout

| Route | Purpose |
|---|---|
| `GET /` | Profile form |
| `POST /generate-workout` | Generate/save a plan and tip; render results |
| `POST /submit-feedback` | Revise the latest plan for a user ID |
| `GET /view-all-users?token=...` | Token-protected coach dashboard, including user deletion |
| `GET /api/health` | Health status and active AI mode |
| `POST /api/plans` | JSON plan generation |
| `POST /api/plans/{user_id}/feedback` | JSON plan revision |
| `GET /api/plans/{user_id}` | Read a user's plan history |
| `GET /api/admin/users` | Token-protected JSON coach view |
| `DELETE /api/admin/users/{user_id}` | Token-protected deletion |

```text
FitBuddy/
├── .env.example
├── .gitignore
├── README.md
├── requirements.txt
├── .vscode/
│   ├── launch.json
│   └── settings.json
└── app/
    ├── main.py                 # FastAPI application and startup
    ├── routes.py               # Website and JSON API routes
    ├── config.py               # Environment settings
    ├── database.py             # SQLite engine and sessions
    ├── models.py               # SQLAlchemy user and plan models
    ├── schemas.py              # Validated request models
    ├── services/ai.py          # Gemini integration and demo responses
    ├── templates/              # Jinja2 pages
    └── static/styles.css       # Responsive UI styles
```

## Notes

- The app is intended for local development. Before any public deployment, use a proper authentication system, secure secrets, HTTPS, request limits, and a managed database. The coach token query parameter is convenient for local use; avoid putting real secrets in URLs in a deployed application.
- `ALLOW_DEMO_AI=true` falls back to a deterministic demo response if Gemini is not configured or temporarily errors. Set it to `false` when you want generation failures to be shown instead of demo content.
- Weight is used as profile context only; FitBuddy does not calculate BMI, calories, or target weight.
- Existing profiles are updated when the same user ID is submitted again. Each new generation creates a separate plan record, preserving the previous plan history.
