# ACC Consultation System

Flask + SQLite web app for booking and managing student-to-medical-expert consultations.

## Setup

```bash
python -m venv venv
# Windows:  venv\Scripts\activate        macOS/Linux:  source venv/bin/activate
pip install -r requirements.txt
python seed.py            # creates instance/acc_consultation.db with roles, demo users and sample data
python app.py             # or: flask --app app run --debug
```

Open http://127.0.0.1:5000

For anything beyond local testing: `export SECRET_KEY="long-random-value"` (Windows: `set SECRET_KEY=...`)
and change the demo passwords.

## Demo logins

| Role           | Email             | Password      |
|----------------|-------------------|---------------|
| Super Admin    | admin@acc.edu     | Admin@12345   |
| Medical Expert | expert1@acc.edu   | Expert@12345  |
| Medical Expert | expert2@acc.edu   | Expert@12345  |
| Student        | student1@acc.edu  | Student@12345 |
| Student        | student2@acc.edu  | Student@12345 |

## Layout

| Path | Purpose |
|------|---------|
| `app.py` | App factory, blueprint registration, error pages, security headers, deactivated-session check |
| `config.py` | Secret key, SQLite path, session settings |
| `extensions.py` | Shared `db`, `login_manager`, `csrf` objects |
| `models.py` | Tables: roles, users, availabilities, consultations, notifications, activity_logs, settings |
| `decorators.py` | `role_required(...)` backend RBAC guard (401 to login, 403 for wrong role) |
| `utils.py` | `log_action()` audit trail, `notify()` in-app notifications |
| `seed.py` | Creates tables and demo data (`--reset` wipes first) |
| `blueprints/auth.py` | Login, logout, student registration |
| `blueprints/main.py` | Role-based redirect, notifications, profile and password change |
| `blueprints/student.py` | Student dashboard, booking, history, cancel |
| `blueprints/expert.py` | Expert dashboard, schedule slots, approve/decline, notes/outcomes, student records |
| `blueprints/admin.py` | User management, all consultations, activity logs, system settings |
| `templates/` | Jinja pages, one folder per role plus `base.html` and `_macros.html` |
| `static/css/style.css` | Auburn / Police Blue / Vanilla theme on top of Bootstrap 5 |
| `static/js/main.js` | Confirm dialogs, alert auto-dismiss, password match, role-based form fields |
