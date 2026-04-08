# Eventzo — Smart Event Discovery

A full-stack event discovery platform built for two kinds of users — people looking for events worth attending, and organisers who want to run them without the hassle.

🔗 **Live Demo:** [eventzo-1.onrender.com](https://eventzo-1.onrender.com/#)

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | HTML5, CSS3, Vanilla JavaScript |
| Backend | Python · Flask |
| Database | PostgreSQL |
| Deployment | Render |

---

## Features

### Participants
- Browse all events with filters by city, mode, and type
- Register and cancel registrations from a personal dashboard
- View event details — rules, team size, participation type, and more

### Organisers
- Create and publish events with full configuration
- Dashboard with live registration counts and event status (Active / Upcoming / Closed)
- Analytics and heatmap views to track performance
- Per-event participant roster

---

## Getting Started

```bash
git clone https://github.com/asritha28007/eventzo.git
cd eventzo
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
flask run
```

Create a `.env` file with the following:

```env
DATABASE_URL=postgresql://user:password@localhost/eventzo
SECRET_KEY=your-secret-key
```

Database tables are created automatically on first run — no migrations needed.

---

## Project Structure

```
eventzo/
├── app.py              # All routes, DB logic, and session handling
├── requirements.txt
└── templates/
    ├── home.html
    ├── about.html
    ├── contact.html
    ├── signup_participant.html
    ├── signup_organizer.html
    ├── login_participant.html
    ├── login_organizer.html
    ├── participant_dashboard.html
    ├── organizer_dashboard.html
    ├── organizer_events.html
    ├── organizer_analytics.html
    ├── organizer_heatmap.html
    ├── organizer_participants.html
    └── create_event.html
```

---

## Authentication

The app uses Flask server-side sessions with a dual-user model. Participants and organisers have separate signup, login, and dashboard flows. Passwords are hashed with SHA-256 — swap in `werkzeug.security` or `bcrypt` before going to production.

---

## Deployment

Hosted on [Render](https://render.com). To deploy your own instance:

1. Push the repo to GitHub and connect it to a new Render Web Service
2. Add a PostgreSQL database on Render and copy the connection string to `DATABASE_URL`
3. Set `SECRET_KEY` to a strong random value
4. Use `gunicorn app:app` as the start command

---

