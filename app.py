from flask import Flask, render_template, request, redirect, session, flash, jsonify
import psycopg2
import psycopg2.extras
import os
import hashlib
from datetime import date

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "eventzo_secret_key_change_in_production")

# ── DATABASE URL (set DATABASE_URL in your environment / Render config vars) ──
DATABASE_URL = os.environ.get("DATABASE_URL", "")
# Render gives postgres:// but psycopg2 needs postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)


def get_db():
    return psycopg2.connect(DATABASE_URL)


def hash_password(password):
    """Simple SHA-256 hash. Use bcrypt/werkzeug in production."""
    return hashlib.sha256(password.encode()).hexdigest()


def init_db():
    db = get_db()
    cursor = db.cursor()

    # NOTE: PostgreSQL uses SERIAL for auto-increment, not INTEGER AUTOINCREMENT
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS participants (
            id              SERIAL PRIMARY KEY,
            first_name      TEXT NOT NULL,
            last_name       TEXT NOT NULL,
            email           TEXT UNIQUE NOT NULL,
            phone           TEXT NOT NULL,
            password        TEXT NOT NULL,
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS organizers (
            id              SERIAL PRIMARY KEY,
            first_name      TEXT NOT NULL,
            last_name       TEXT NOT NULL,
            email           TEXT UNIQUE NOT NULL,
            phone           TEXT NOT NULL,
            organization    TEXT NOT NULL,
            org_type        TEXT NOT NULL,
            city            TEXT NOT NULL,
            password        TEXT NOT NULL,
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id                  SERIAL PRIMARY KEY,
            organizer_id        INTEGER NOT NULL,
            title               TEXT NOT NULL,
            description         TEXT,
            event_type          TEXT NOT NULL,
            website_url         TEXT,
            event_mode          TEXT NOT NULL DEFAULT 'Online',
            location            TEXT,
            keywords            TEXT,
            rules               TEXT,
            participation_type  TEXT NOT NULL DEFAULT 'Individual',
            min_team_size       INTEGER,
            max_team_size       INTEGER,
            reg_start           DATE NOT NULL,
            reg_end             DATE NOT NULL,
            max_registrations   INTEGER NOT NULL,
            created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (organizer_id) REFERENCES organizers(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS registrations (
            id              SERIAL PRIMARY KEY,
            event_id        INTEGER NOT NULL,
            participant_id  INTEGER NOT NULL,
            registered_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (event_id) REFERENCES events(id),
            FOREIGN KEY (participant_id) REFERENCES participants(id),
            UNIQUE(event_id, participant_id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS contact_messages (
            id           SERIAL PRIMARY KEY,
            first_name   TEXT NOT NULL,
            last_name    TEXT NOT NULL,
            email        TEXT NOT NULL,
            role         TEXT,
            message      TEXT NOT NULL,
            submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    db.commit()
    cursor.close()
    db.close()


# ── Init DB on startup ──────────────────────────────────────────────────────
init_db()


# ── HOME ────────────────────────────────────────────────────────────────────
@app.route("/")
def home():
    return render_template("home.html")


@app.route('/about')
def about():
    return render_template('about.html')


@app.route('/contact', methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        first_name = request.form.get("first_name", "").strip()
        last_name  = request.form.get("last_name", "").strip()
        email      = request.form.get("email", "").strip().lower()
        role       = request.form.get("role", "").strip()
        message    = request.form.get("message", "").strip()

        if not email or not message:
            flash("Email and message are required.", "error")
            return render_template("contact.html")

        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            """INSERT INTO contact_messages (first_name, last_name, email, role, message)
               VALUES (%s, %s, %s, %s, %s)""",
            (first_name, last_name, email, role, message)
        )
        db.commit()
        cursor.close()
        db.close()

        return redirect("/contact?submitted=true")

    submitted = request.args.get("submitted") == "true"
    return render_template("contact.html", submitted=submitted)


@app.route("/admin/messages")
def admin_messages():
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM contact_messages ORDER BY submitted_at DESC")
    messages = cursor.fetchall()
    cursor.close()
    db.close()
    return jsonify(messages)


# ── PARTICIPANT SIGNUP / LOGIN ───────────────────────────────────────────────
@app.route("/signup/participant", methods=["GET", "POST"])
def signup_participant():
    if request.method == "POST":
        first_name       = request.form.get("first_name", "").strip()
        last_name        = request.form.get("last_name", "").strip()
        email            = request.form.get("email", "").strip().lower()
        phone            = request.form.get("phone", "").strip()
        password         = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if password != confirm_password:
            flash("Passwords do not match.", "error")
            return render_template("signup_participant.html")

        if len(password) < 8:
            flash("Password must be at least 8 characters.", "error")
            return render_template("signup_participant.html")

        db = get_db()
        cursor = db.cursor()
        try:
            cursor.execute(
                """INSERT INTO participants
                   (first_name, last_name, email, phone, password)
                   VALUES (%s, %s, %s, %s, %s)""",
                (first_name, last_name, email, phone, hash_password(password))
            )
            db.commit()
        except psycopg2.IntegrityError:
            db.rollback()
            flash("An account with this email already exists.", "error")
            cursor.close()
            db.close()
            return render_template("signup_participant.html")
        finally:
            cursor.close()
            db.close()

        return redirect("/login/participant")

    return render_template("signup_participant.html")


@app.route("/login/participant", methods=["GET", "POST"])
def login_participant():
    if request.method == "POST":
        email    = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            "SELECT * FROM participants WHERE email = %s AND password = %s",
            (email, hash_password(password))
        )
        user = cursor.fetchone()
        cursor.close()
        db.close()

        if user:
            session["user_id"]   = user[0]
            session["user_type"] = "participant"
            session["user_name"] = user[1]
            return redirect("/dashboard/participant")
        else:
            flash("Invalid email or password.", "error")

    return render_template("login_participant.html")


# ── ORGANIZER SIGNUP / LOGIN ─────────────────────────────────────────────────
@app.route("/signup/organizer", methods=["GET", "POST"])
def signup_organizer():
    if request.method == "POST":
        first_name       = request.form.get("first_name", "").strip()
        last_name        = request.form.get("last_name", "").strip()
        email            = request.form.get("email", "").strip().lower()
        phone            = request.form.get("phone", "").strip()
        organization     = request.form.get("organization", "").strip()
        org_type         = request.form.get("org_type", "").strip()
        city             = request.form.get("city", "").strip()
        password         = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if password != confirm_password:
            flash("Passwords do not match.", "error")
            return render_template("signup_organizer.html")

        if len(password) < 8:
            flash("Password must be at least 8 characters.", "error")
            return render_template("signup_organizer.html")

        db = get_db()
        cursor = db.cursor()
        try:
            cursor.execute(
                """INSERT INTO organizers
                   (first_name, last_name, email, phone, organization, org_type, city, password)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                (first_name, last_name, email, phone,
                 organization, org_type, city, hash_password(password))
            )
            db.commit()
        except psycopg2.IntegrityError:
            db.rollback()
            flash("An account with this email already exists.", "error")
            cursor.close()
            db.close()
            return render_template("signup_organizer.html")
        finally:
            cursor.close()
            db.close()

        return redirect("/login/organizer")

    return render_template("signup_organizer.html")


@app.route("/login/organizer", methods=["GET", "POST"])
def login_organizer():
    if request.method == "POST":
        email    = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            "SELECT * FROM organizers WHERE email = %s AND password = %s",
            (email, hash_password(password))
        )
        user = cursor.fetchone()
        cursor.close()
        db.close()

        if user:
            session["user_id"]   = user[0]
            session["user_type"] = "organizer"
            session["user_name"] = user[1]
            return redirect("/dashboard/organizer")
        else:
            flash("Invalid email or password.", "error")

    return render_template("login_organizer.html")


# ── ORGANIZER DASHBOARD ──────────────────────────────────────────────────────
@app.route("/dashboard/organizer")
def dashboard_organizer():
    if session.get("user_type") != "organizer":
        return redirect("/login/organizer")

    db = get_db()
    cursor = db.cursor()

    cursor.execute("""
        SELECT e.*,
               (SELECT COUNT(*) FROM registrations r WHERE r.event_id = e.id) AS reg_count
        FROM events e
        WHERE e.organizer_id = %s
        ORDER BY e.created_at DESC
    """, (session["user_id"],))
    raw_events = cursor.fetchall()

    cursor.execute("SELECT organization FROM organizers WHERE id = %s", (session["user_id"],))
    org_row = cursor.fetchone()
    org_name = org_row[0] if org_row else session.get("user_name")

    cursor.close()
    db.close()

    today = date.today().isoformat()
    events = []
    for ev in raw_events:
        reg_start = ev[13].isoformat() if hasattr(ev[13], 'isoformat') else str(ev[13])
        reg_end   = ev[14].isoformat() if hasattr(ev[14], 'isoformat') else str(ev[14])

        if today < reg_start:
            status = "upcoming"
        elif today <= reg_end:
            status = "active"
        else:
            status = "closed"

        events.append({
            "id":                ev[0],
            "title":             ev[2],
            "type":              ev[4],
            "mode":              ev[6],
            "location":          ev[7] or "",
            "participation_type": ev[10] or "Individual",
            "reg_start":         reg_start,
            "reg_end":           reg_end,
            "max_registrations": ev[15],
            "registrations":     ev[17],
            "status":            status,
            "day":               reg_start[8:10],
            "month":             ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"][int(reg_start[5:7])-1],
        })

    total_regs   = sum(e["registrations"] for e in events)
    active_count = sum(1 for e in events if e["status"] == "active")

    return render_template(
        "organizer_dashboard.html",
        organizer_name=session.get("user_name"),
        org_name=org_name,
        events=events,
        total_events=len(events),
        total_regs=total_regs,
        active_count=active_count,
    )


# ── CREATE EVENT ─────────────────────────────────────────────────────────────
@app.route("/create-event", methods=["GET", "POST"])
def create_event():
    if session.get("user_type") != "organizer":
        return redirect("/login/organizer")

    if request.method == "POST":
        title              = request.form.get("title", "").strip()
        description        = request.form.get("description", "").strip()
        event_type         = request.form.get("event_type", "").strip()
        website_url        = request.form.get("website_url", "").strip()
        event_mode         = request.form.get("event_mode", "Online")
        location           = request.form.get("location", "").strip()
        keywords           = request.form.get("keywords", "").strip()
        rules              = request.form.get("rules", "").strip()
        participation_type = request.form.get("participation_type", "Individual")
        min_team_size      = request.form.get("min_team_size") or None
        max_team_size      = request.form.get("max_team_size") or None
        reg_start          = request.form.get("reg_start", "")
        reg_end            = request.form.get("reg_end", "")
        max_registrations  = request.form.get("max_registrations", 0)

        if not all([title, event_type, reg_start, reg_end, max_registrations]):
            flash("Please fill in all required fields.", "error")
            return render_template("create_event.html", organizer_name=session.get("user_name"))

        if event_mode == "Offline" and not location:
            flash("Please provide a location for offline events.", "error")
            return render_template("create_event.html", organizer_name=session.get("user_name"))

        db = get_db()
        cursor = db.cursor()
        try:
            cursor.execute("""
                INSERT INTO events
                    (organizer_id, title, description, event_type, website_url,
                     event_mode, location, keywords, rules,
                     participation_type, min_team_size, max_team_size,
                     reg_start, reg_end, max_registrations)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                session["user_id"], title, description, event_type, website_url,
                event_mode, location, keywords, rules,
                participation_type, min_team_size, max_team_size,
                reg_start, reg_end, int(max_registrations)
            ))
            db.commit()
        except Exception as e:
            db.rollback()
            flash(f"Error creating event: {str(e)}", "error")
            cursor.close()
            db.close()
            return render_template("create_event.html", organizer_name=session.get("user_name"))
        finally:
            cursor.close()
            db.close()

        flash("Event published successfully!", "success")
        return redirect("/dashboard/organizer")

    return render_template("create_event.html", organizer_name=session.get("user_name"))


# ── API: PARTICIPANTS FOR AN EVENT ───────────────────────────────────────────
@app.route("/api/events/<int:event_id>/participants")
def get_participants(event_id):
    if session.get("user_type") != "organizer":
        return jsonify({"error": "Unauthorized"}), 401

    db = get_db()
    cursor = db.cursor()

    cursor.execute("SELECT id FROM events WHERE id = %s AND organizer_id = %s",
                   (event_id, session["user_id"]))
    if not cursor.fetchone():
        cursor.close()
        db.close()
        return jsonify({"error": "Not found"}), 404

    cursor.execute("""
        SELECT p.first_name, p.last_name, p.email, p.phone, r.registered_at
        FROM registrations r
        JOIN participants p ON p.id = r.participant_id
        WHERE r.event_id = %s
        ORDER BY r.registered_at DESC
    """, (event_id,))
    rows = cursor.fetchall()
    cursor.close()
    db.close()

    participants = [
        {"name": f"{r[0]} {r[1]}", "email": r[2], "phone": r[3], "registered_at": str(r[4])}
        for r in rows
    ]
    return jsonify({"participants": participants})


# ── PARTICIPANT DASHBOARD ─────────────────────────────────────────────────────
@app.route("/dashboard/participant")
def dashboard_participant():
    if session.get("user_type") != "participant":
        return redirect("/login/participant")

    db = get_db()
    cursor = db.cursor()

    cursor.execute("""
        SELECT e.*,
               o.organization,
               (SELECT COUNT(*) FROM registrations r WHERE r.event_id = e.id) AS reg_count
        FROM events e
        JOIN organizers o ON o.id = e.organizer_id
        ORDER BY e.reg_start ASC
    """)
    raw_events = cursor.fetchall()

    cursor.execute(
        "SELECT event_id FROM registrations WHERE participant_id = %s",
        (session["user_id"],)
    )
    my_event_ids = [row[0] for row in cursor.fetchall()]

    cursor.execute("SELECT created_at FROM participants WHERE id = %s", (session["user_id"],))
    p_row = cursor.fetchone()
    join_year = str(p_row[0])[:4] if p_row else "2025"

    cursor.close()
    db.close()

    today = date.today().isoformat()

    all_events = []
    for ev in raw_events:
        reg_start = ev[13].isoformat() if hasattr(ev[13], 'isoformat') else str(ev[13])
        reg_end   = ev[14].isoformat() if hasattr(ev[14], 'isoformat') else str(ev[14])
        all_events.append({
            "id":                ev[0],
            "title":             ev[2],
            "description":       ev[3] or "",
            "event_type":        ev[4],
            "website_url":       ev[5] or "",
            "event_mode":        ev[6],
            "location":          ev[7] or "",
            "keywords":          ev[8] or "",
            "rules":             ev[9] or "",
            "participation_type": ev[10],
            "min_team_size":     ev[11],
            "max_team_size":     ev[12],
            "reg_start":         reg_start,
            "reg_end":           reg_end,
            "max_registrations": ev[15],
            "organization":      ev[17],
            "registrations":     ev[18],
        })

    registered_events = [e for e in all_events if e["id"] in my_event_ids]
    upcoming_count    = sum(1 for e in registered_events if today < e["reg_end"])

    cities = sorted(set(
        ev["location"].strip()
        for ev in all_events
        if ev["event_mode"] == "Offline" and ev["location"].strip()
    ))

    return render_template(
        "participant_dashboard.html",
        user_name        = session.get("user_name"),
        join_year        = join_year,
        all_events       = all_events,
        my_event_ids     = my_event_ids,
        registered_count = len(registered_events),
        upcoming_count   = upcoming_count,
        cities           = cities,
    )


# ── REGISTER FOR EVENT ────────────────────────────────────────────────────────
@app.route("/register/<int:event_id>", methods=["POST"])
def register_event(event_id):
    if session.get("user_type") != "participant":
        return jsonify({"success": False, "message": "Please log in as a participant."}), 401

    db = get_db()
    cursor = db.cursor()

    cursor.execute("SELECT reg_start, reg_end, max_registrations FROM events WHERE id = %s", (event_id,))
    ev = cursor.fetchone()
    if not ev:
        cursor.close()
        db.close()
        return jsonify({"success": False, "message": "Event not found."}), 404

    today     = date.today().isoformat()
    reg_start = ev[0].isoformat() if hasattr(ev[0], 'isoformat') else str(ev[0])
    reg_end   = ev[1].isoformat() if hasattr(ev[1], 'isoformat') else str(ev[1])

    if today < reg_start or today > reg_end:
        cursor.close()
        db.close()
        return jsonify({"success": False, "message": "Registration is not open for this event."})

    cursor.execute("SELECT COUNT(*) FROM registrations WHERE event_id = %s", (event_id,))
    current_count = cursor.fetchone()[0]
    if current_count >= ev[2]:
        cursor.close()
        db.close()
        return jsonify({"success": False, "message": "This event is fully booked."})

    try:
        cursor.execute(
            "INSERT INTO registrations (event_id, participant_id) VALUES (%s, %s)",
            (event_id, session["user_id"])
        )
        db.commit()
    except psycopg2.IntegrityError:
        db.rollback()
        cursor.close()
        db.close()
        return jsonify({"success": False, "message": "You are already registered for this event."})
    finally:
        cursor.close()
        db.close()

    return jsonify({"success": True, "message": "Registered successfully!"})


# ── CANCEL REGISTRATION ───────────────────────────────────────────────────────
@app.route("/cancel-registration/<int:event_id>", methods=["POST"])
def cancel_registration(event_id):
    if session.get("user_type") != "participant":
        return jsonify({"success": False, "message": "Please log in as a participant."}), 401

    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        "DELETE FROM registrations WHERE event_id = %s AND participant_id = %s",
        (event_id, session["user_id"])
    )
    db.commit()
    cursor.close()
    db.close()

    return jsonify({"success": True, "message": "Registration cancelled."})


def build_events_list(raw_events):
    """Helper — converts raw DB rows to dicts."""
    today  = date.today().isoformat()
    months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
    events = []
    for ev in raw_events:
        # PostgreSQL returns date objects, not strings — normalise both
        reg_start = ev[13].isoformat() if hasattr(ev[13], 'isoformat') else str(ev[13])
        reg_end   = ev[14].isoformat() if hasattr(ev[14], 'isoformat') else str(ev[14])

        if today < reg_start:
            status = "upcoming"
        elif today <= reg_end:
            status = "active"
        else:
            status = "closed"

        events.append({
            "id":                ev[0],
            "title":             ev[2],
            "description":       ev[3] or "",
            "type":              ev[4],
            "mode":              ev[6],
            "location":          ev[7] or "",
            "participation_type": ev[10] or "Individual",
            "reg_start":         reg_start,
            "reg_end":           reg_end,
            "max_registrations": ev[15],
            "registrations":     ev[17],
            "status":            status,
            "day":               reg_start[8:10],
            "month":             months[int(reg_start[5:7])-1],
        })
    return events


# ── ORGANIZER EVENTS PAGE ─────────────────────────────────────────────────────
@app.route("/organizer/events")
def organizer_events():
    if session.get("user_type") != "organizer":
        return redirect("/login/organizer")

    db = get_db()
    cursor = db.cursor()
    cursor.execute("""
        SELECT e.*,
               (SELECT COUNT(*) FROM registrations r WHERE r.event_id = e.id) AS reg_count
        FROM events e
        WHERE e.organizer_id = %s
        ORDER BY e.created_at DESC
    """, (session["user_id"],))
    raw = cursor.fetchall()
    cursor.close()
    db.close()

    events = build_events_list(raw)
    total_regs     = sum(e["registrations"] for e in events)
    active_count   = sum(1 for e in events if e["status"] == "active")
    upcoming_count = sum(1 for e in events if e["status"] == "upcoming")

    return render_template(
        "organizer_events.html",
        organizer_name = session.get("user_name"),
        events         = events,
        total_events   = len(events),
        total_regs     = total_regs,
        active_count   = active_count,
        upcoming_count = upcoming_count,
    )


# ── ORGANIZER ANALYTICS PAGE ──────────────────────────────────────────────────
@app.route("/organizer/analytics")
def organizer_analytics():
    if session.get("user_type") != "organizer":
        return redirect("/login/organizer")

    db = get_db()
    cursor = db.cursor()
    cursor.execute("""
        SELECT e.*,
               (SELECT COUNT(*) FROM registrations r WHERE r.event_id = e.id) AS reg_count
        FROM events e
        WHERE e.organizer_id = %s
        ORDER BY e.created_at DESC
    """, (session["user_id"],))
    raw = cursor.fetchall()
    cursor.close()
    db.close()

    events = build_events_list(raw)
    total_regs   = sum(e["registrations"] for e in events)
    active_count = sum(1 for e in events if e["status"] == "active")

    return render_template(
        "organizer_analytics.html",
        organizer_name = session.get("user_name"),
        events         = events,
        total_events   = len(events),
        total_regs     = total_regs,
        active_count   = active_count,
    )


# ── DELETE EVENT ──────────────────────────────────────────────────────────────
@app.route("/organizer/event/<int:event_id>/delete", methods=["POST"])
def delete_event(event_id):
    if session.get("user_type") != "organizer":
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    db = get_db()
    cursor = db.cursor()

    cursor.execute("SELECT id FROM events WHERE id = %s AND organizer_id = %s",
                   (event_id, session["user_id"]))
    if not cursor.fetchone():
        cursor.close()
        db.close()
        return jsonify({"success": False, "message": "Event not found."}), 404

    cursor.execute("DELETE FROM registrations WHERE event_id = %s", (event_id,))
    cursor.execute("DELETE FROM events WHERE id = %s", (event_id,))
    db.commit()
    cursor.close()
    db.close()

    return jsonify({"success": True})


# ── ORGANIZER PARTICIPANTS PAGE ───────────────────────────────────────────────
@app.route("/organizer/event/<int:event_id>/participants")
def event_participants_page(event_id):
    if session.get("user_type") != "organizer":
        return redirect("/login/organizer")

    db = get_db()
    cursor = db.cursor()

    cursor.execute(
        "SELECT id, title, max_registrations FROM events WHERE id = %s AND organizer_id = %s",
        (event_id, session["user_id"])
    )
    ev = cursor.fetchone()
    if not ev:
        cursor.close()
        db.close()
        return redirect("/organizer/events")

    cursor.execute("""
        SELECT p.first_name, p.last_name, p.email, p.phone, r.registered_at
        FROM registrations r
        JOIN participants p ON p.id = r.participant_id
        WHERE r.event_id = %s
        ORDER BY r.registered_at DESC
    """, (event_id,))
    rows = cursor.fetchall()
    cursor.close()
    db.close()

    participants = [
        {"name": f"{r[0]} {r[1]}", "email": r[2], "phone": r[3], "registered_at": str(r[4])}
        for r in rows
    ]

    return render_template(
        "organizer_participants.html",
        organizer_name = session.get("user_name"),
        event_title    = ev[1],
        event_id       = event_id,
        max_seats      = ev[2],
        participants   = participants,
    )


# ── API — EVENT HEATMAP DATA (for organizers) ─────────────────────────────────
@app.route("/api/organizer/heatmap")
def organizer_heatmap_data():
    if session.get("user_type") != "organizer":
        return jsonify({"error": "Unauthorized"}), 401

    db = get_db()
    cursor = db.cursor()
    cursor.execute("""
        SELECT e.id, e.title, e.event_mode, e.location,
               e.max_registrations, e.reg_start, e.reg_end, e.event_type,
               (SELECT COUNT(*) FROM registrations r WHERE r.event_id = e.id) AS reg_count
        FROM events e
        WHERE e.organizer_id = %s
        ORDER BY reg_count DESC
    """, (session["user_id"],))
    rows = cursor.fetchall()
    cursor.close()
    db.close()

    today = date.today().isoformat()
    events = []
    for row in rows:
        reg_start = row[5].isoformat() if hasattr(row[5], 'isoformat') else str(row[5])
        reg_end   = row[6].isoformat() if hasattr(row[6], 'isoformat') else str(row[6])
        if today < reg_start:
            status = "upcoming"
        elif today <= reg_end:
            status = "active"
        else:
            status = "closed"
        fill_pct = round((row[8] / row[4]) * 100) if row[4] else 0
        events.append({
            "id":                row[0],
            "title":             row[1],
            "mode":              row[2],
            "location":          row[3] or "Online",
            "max_registrations": row[4],
            "reg_start":         reg_start,
            "reg_end":           reg_end,
            "event_type":        row[7],
            "registrations":     row[8],
            "fill_pct":          fill_pct,
            "status":            status,
        })
    return jsonify({"events": events})


# ── EVENT HEATMAP PAGE (organizer) ────────────────────────────────────────────
@app.route("/organizer/heatmap")
def organizer_heatmap():
    if session.get("user_type") != "organizer":
        return redirect("/login/organizer")

    db = get_db()
    cursor = db.cursor()
    cursor.execute("""
        SELECT e.id, e.title, e.event_mode, e.location,
               e.max_registrations, e.reg_start, e.reg_end, e.event_type,
               (SELECT COUNT(*) FROM registrations r WHERE r.event_id = e.id) AS reg_count
        FROM events e
        WHERE e.organizer_id = %s
        ORDER BY reg_count DESC
    """, (session["user_id"],))
    rows = cursor.fetchall()
    cursor.close()
    db.close()

    today = date.today().isoformat()
    events = []
    for row in rows:
        reg_start = row[5].isoformat() if hasattr(row[5], 'isoformat') else str(row[5])
        reg_end   = row[6].isoformat() if hasattr(row[6], 'isoformat') else str(row[6])
        if today < reg_start:
            status = "upcoming"
        elif today <= reg_end:
            status = "active"
        else:
            status = "closed"
        fill_pct = round((row[8] / row[4]) * 100) if row[4] else 0
        events.append({
            "id":                row[0],
            "title":             row[1],
            "mode":              row[2],
            "location":          row[3] or "Online",
            "max_registrations": row[4],
            "reg_start":         reg_start,
            "reg_end":           reg_end,
            "event_type":        row[7],
            "registrations":     row[8],
            "fill_pct":          fill_pct,
            "status":            status,
        })

    total_regs   = sum(e["registrations"] for e in events)
    active_count = sum(1 for e in events if e["status"] == "active")

    return render_template(
        "organizer_heatmap.html",
        organizer_name = session.get("user_name"),
        events         = events,
        total_events   = len(events),
        total_regs     = total_regs,
        active_count   = active_count,
    )


# ── LOGOUT ───────────────────────────────────────────────────────────────────
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


if __name__ == "__main__":
    app.run(debug=True)