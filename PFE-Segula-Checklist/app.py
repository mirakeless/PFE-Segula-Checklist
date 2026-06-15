import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
import io
import os
import base64
import re
import smtplib
import ssl
import unicodedata
import secrets as py_secrets
from email.message import EmailMessage
from html import escape
from pathlib import Path

import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from reportlab.lib.units import inch

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# ==============================================================================
# CONFIGURATION GÉNÉRALE
# ==============================================================================
st.set_page_config(
    page_title="Checklist Digitalisée - Cahiers de Montage",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="collapsed",
)

BASE_DIR = Path(__file__).parent
DB_PATH = str(BASE_DIR / "segula_aerospace_quality.db")
CHECKLIST_CSV = BASE_DIR / "data" / "default_checklist.csv"
SEGULA_LOGO = BASE_DIR / "assets" / "segula_logo.png"
BOMBARDIER_LOGO = BASE_DIR / "assets" / "bombardier_logo.png"

ADMIN_EMAIL = "attaasma750@gmail.com"
ROLES = ["Agent Méthodes", "Pilote d'Activité", "Responsable Qualité"]
PROGRAMMES = ["Global Express", "Challenger 350", "Challenger 650", "Learjet Line"]
PROJECT_OWNER = "Asma AIT ATTA"
PROJECT_CONTEXT = "Projet de Fin d'Études 2025-2026"
PROJECT_OBJECTIVE = "Digitalisation, traçabilité et pilotage qualité du processus de création des cahiers de montage."
APP_TITLE = "CHECKLIST DIGITALISÉE DES CAHIERS DE MONTAGE"
APP_SUBTITLE = "Normes Bombardier Aerospace"

# ==============================================================================
# SECRETS / SMTP
# ==============================================================================
def get_secret_value(key, default=""):
    try:
        return st.secrets.get(key, os.environ.get(key, default))
    except Exception:
        return os.environ.get(key, default)

APP_URL = str(get_secret_value("APP_URL", "http://localhost:8501")).rstrip("/")
SMTP_HOST = str(get_secret_value("SMTP_HOST", "smtp.gmail.com"))
SMTP_PORT = int(get_secret_value("SMTP_PORT", "465") or "465")
SMTP_USER = str(get_secret_value("SMTP_USER", ""))
SMTP_PASSWORD = str(get_secret_value("SMTP_PASSWORD", ""))
SMTP_FROM = str(get_secret_value("SMTP_FROM", SMTP_USER or ADMIN_EMAIL))

# ==============================================================================
# OUTILS
# ==============================================================================
def clean_name(value):
    return re.sub(r"\s+", " ", str(value or "").strip())


def clean_email(value):
    return str(value or "").strip().lower()


def is_valid_email(email):
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", clean_email(email)))


def slug_without_accents(text):
    text = unicodedata.normalize("NFD", str(text or ""))
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = re.sub(r"[^A-Za-z0-9]", "", text)
    return text


def generer_mot_de_passe(role, nom):
    clean_role = slug_without_accents(role)
    clean_nom = slug_without_accents(nom)
    return f"{clean_role}{clean_nom}2026"


def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def get_query_param(name):
    try:
        value = st.query_params.get(name)
        if isinstance(value, list):
            return value[0] if value else None
        return value
    except Exception:
        try:
            params = st.experimental_get_query_params()
            values = params.get(name, [])
            return values[0] if values else None
        except Exception:
            return None


def clear_query_params():
    try:
        st.query_params.clear()
    except Exception:
        try:
            st.experimental_set_query_params()
        except Exception:
            pass


def get_image_src(path):
    path = Path(path)
    if not path.exists():
        return ""
    try:
        mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
        encoded = base64.b64encode(path.read_bytes()).decode("utf-8")
        return f"data:{mime};base64,{encoded}"
    except Exception:
        return ""


def logo_img(path, alt):
    src = get_image_src(path)
    if src:
        return f'<img src="{src}" alt="{escape(alt)}">'
    return f'<span style="font-weight:900;color:#0B2D4D;">{escape(alt)}</span>'

# ==============================================================================
# STYLE
# ==============================================================================
def apply_global_style():
    state = st.session_state.get("app_state", "LOGIN")

    if state == "HOME":
        background = """
        .stApp {
            background:
                linear-gradient(90deg, rgba(246,249,252,.97), rgba(246,249,252,.91), rgba(246,249,252,.97)),
                url("https://images.unsplash.com/photo-1540962351504-03099e0a754b?w=1800") center/cover fixed;
            animation: catalogSlide 24s infinite ease-in-out;
        }
        @keyframes catalogSlide {
            0% { background-image: linear-gradient(90deg, rgba(246,249,252,.97), rgba(246,249,252,.91), rgba(246,249,252,.97)), url("https://images.unsplash.com/photo-1540962351504-03099e0a754b?w=1800"); }
            50% { background-image: linear-gradient(90deg, rgba(246,249,252,.97), rgba(246,249,252,.91), rgba(246,249,252,.97)), url("https://images.unsplash.com/photo-1517976487492-5750f3195933?w=1800"); }
            100% { background-image: linear-gradient(90deg, rgba(246,249,252,.97), rgba(246,249,252,.91), rgba(246,249,252,.97)), url("https://images.unsplash.com/photo-1540962351504-03099e0a754b?w=1800"); }
        }
        """
    elif state == "LOGIN":
        background = """
        .stApp {
            background:
                radial-gradient(circle at 18% 12%, rgba(15,118,110,.09), transparent 28%),
                radial-gradient(circle at 82% 10%, rgba(11,45,77,.08), transparent 28%),
                linear-gradient(135deg, #F7FAFC 0%, #EAF0F6 45%, #FFFFFF 100%) !important;
        }
        """
    else:
        background = ".stApp { background: linear-gradient(180deg, #F7FAFC 0%, #EDF2F7 100%) !important; }"

    st.markdown(f"""
    <style>
    {background}
    :root {{
        --navy:#0B2D4D;
        --navy2:#123F63;
        --teal:#0F766E;
        --red:#C1121F;
        --green:#15803D;
        --amber:#B45309;
        --ink:#0F172A;
        --muted:#5B677A;
        --line:#D7E0EA;
        --shadow:0 18px 48px rgba(15,23,42,.10);
    }}
    html, body, [class*="css"] {{ font-family:'Segoe UI','Inter',Arial,sans-serif !important; }}
    .block-container {{ padding-top: 1.8rem !important; padding-bottom: 2.2rem !important; max-width: 1280px !important; }}
    h1,h2,h3,h4,h5,h6 {{ color:var(--navy) !important; font-weight:900 !important; letter-spacing:-.025em; }}
    p, span, div, label, .stMarkdown {{ color:var(--ink); }}
    label {{ color:#1E293B !important; font-weight:800 !important; font-size:.92rem !important; }}
    input, textarea, [data-baseweb="select"] > div {{
        border-radius: 11px !important; border:1px solid #C9D4E2 !important;
        background:#FFFFFF !important; color:#0F172A !important;
    }}
    input:focus, textarea:focus {{ border-color:var(--navy2) !important; box-shadow:0 0 0 3px rgba(18,63,99,.12) !important; }}
    .stButton>button, .stDownloadButton>button {{
        border-radius:12px !important; border:0 !important; color:#FFFFFF !important;
        background:linear-gradient(135deg,var(--navy),var(--navy2)) !important;
        font-weight:850 !important; padding:.68rem 1.25rem !important;
        box-shadow:0 10px 22px rgba(11,45,77,.18); transition:.15s ease;
    }}
    .stButton>button:hover, .stDownloadButton>button:hover {{
        transform:translateY(-1px); background:linear-gradient(135deg,var(--teal),var(--navy)) !important;
        box-shadow:0 14px 28px rgba(11,45,77,.22);
    }}
    .stTabs [data-baseweb="tab-list"] {{ gap:8px; border-bottom:1px solid #E2E8F0; }}
    .stTabs [data-baseweb="tab"] {{ height:44px; border-radius:10px 10px 0 0; background:#F1F5F9; color:#334155; font-weight:850; padding:0 18px; }}
    .stTabs [aria-selected="true"] {{ background:#FFFFFF !important; color:var(--navy) !important; border-top:4px solid var(--navy) !important; }}

    .top-header {{
        display:grid; grid-template-columns: 230px 1fr 230px; align-items:center; gap:20px;
        background:rgba(255,255,255,.98); border:1px solid var(--line); border-left:8px solid var(--navy);
        border-radius:18px; padding:12px 18px; margin-top:18px; margin-bottom:22px; box-shadow:var(--shadow);
    }}
    .logo-box {{ height:70px; display:flex; align-items:center; justify-content:center; background:#FFFFFF; border-radius:12px; overflow:hidden; }}
    .logo-box img {{ max-width:100%; max-height:64px; object-fit:contain; }}
    .main-title {{ text-align:center; color:var(--navy); font-size:22px; font-weight:950; line-height:1.22; text-transform:uppercase; }}
    .main-subtitle {{ color:#475569; font-size:12.5px; font-weight:800; margin-top:4px; text-transform:none; }}

    .auth-shell {{ min-height: calc(100vh - 35px); display:flex; align-items:flex-start; justify-content:center; padding: 34px 10px 4vh; }}
    .auth-card {{ width:100%; max-width:1040px; background:rgba(255,255,255,.985); border:1px solid #D7E0EA; border-radius:26px; box-shadow:0 30px 80px rgba(15,23,42,.14); overflow:hidden; }}
    .auth-header {{ display:grid; grid-template-columns:210px 1fr 210px; align-items:center; gap:14px; padding:22px 28px; border-bottom:1px solid #E2E8F0; background:#FFFFFF; }}
    .auth-title-center {{ text-align:center; }}
    .auth-title-center .t1 {{ color:var(--navy); font-size:20px; font-weight:950; line-height:1.25; text-transform:uppercase; }}
    .auth-title-center .t2 {{ color:#526173; font-size:13px; font-weight:800; margin-top:4px; }}
    .auth-body {{ display:grid; grid-template-columns:.9fr 1.1fr; min-height:500px; }}
    .auth-left {{ padding:34px 30px; background:linear-gradient(160deg,var(--navy),#123F63 62%,#0F766E); display:flex; flex-direction:column; justify-content:center; }}
    .auth-left * {{ color:#FFFFFF !important; }}
    .auth-left h1 {{ font-size:32px; line-height:1.08; margin:0 0 14px; font-weight:950; }}
    .auth-left p {{ font-size:14.5px; line-height:1.62; color:#E2E8F0 !important; }}
    .auth-line {{ height:1px; background:rgba(255,255,255,.18); margin:22px 0; }}
    .auth-point {{ margin:12px 0; font-size:13.5px; line-height:1.48; font-weight:650; }}
    .auth-right {{ padding:30px 32px; background:#FFFFFF; }}
    .form-title {{ color:var(--navy); font-weight:950; font-size:24px; margin-bottom:6px; }}
    .form-subtitle {{ color:#64748B; font-size:13.5px; line-height:1.52; margin-bottom:18px; }}
    .auth-footer {{ background:#F8FAFC; border-top:1px solid #E2E8F0; padding:14px 24px; text-align:center; color:#64748B; font-size:12.2px; line-height:1.5; }}

    @media(max-width:900px) {{
        .auth-body {{ grid-template-columns:1fr; }}
        .auth-header, .top-header {{ grid-template-columns:1fr; }}
        .auth-left {{ padding:26px; }}
        .auth-right {{ padding:26px; }}
    }}

    .hero-card {{ background:rgba(255,255,255,.96); border:1px solid var(--line); border-left:8px solid var(--navy); border-radius:22px; padding:26px; box-shadow:var(--shadow); margin-bottom:20px; }}
    .hero-title {{ color:var(--navy); font-size:30px; font-weight:950; letter-spacing:-.035em; margin-bottom:6px; }}
    .hero-subtitle {{ color:#334155; font-size:15px; line-height:1.58; max-width:900px; }}
    .session-banner {{ background:rgba(255,255,255,.96); border:1px solid var(--line); border-left:7px solid var(--teal); border-radius:16px; padding:13px 18px; font-weight:850; color:var(--navy); box-shadow:0 12px 28px rgba(15,23,42,.07); margin-bottom:18px; }}
    .pro-card, .white-card {{ background:rgba(255,255,255,.98); border:1px solid var(--line); border-radius:20px; padding:22px; box-shadow:var(--shadow); margin-bottom:18px; }}
    .module-card {{ height:100%; background:#FFFFFF; border:1px solid var(--line); border-top:6px solid var(--navy); border-radius:20px; padding:22px; box-shadow:0 12px 30px rgba(15,23,42,.08); }}
    .module-title {{ color:var(--navy); font-size:19px; font-weight:950; margin-bottom:8px; }}
    .module-text {{ color:#526173; font-size:13.5px; line-height:1.55; min-height:58px; }}
    .metric-card {{ background:#FFFFFF; border:1px solid var(--line); border-top:5px solid var(--navy); border-radius:18px; padding:17px; min-height:118px; box-shadow:0 12px 28px rgba(15,23,42,.07); }}
    .metric-label {{ color:#64748B; font-size:11.5px; font-weight:950; letter-spacing:.06em; text-transform:uppercase; }}
    .metric-value {{ color:var(--navy); font-size:31px; font-weight:950; margin-top:8px; line-height:1.05; }}
    .metric-help {{ color:#64748B; font-size:12.2px; margin-top:8px; line-height:1.35; }}
    .status-pill {{ display:inline-block; border-radius:999px; padding:7px 12px; font-size:12px; font-weight:950; border:1px solid #CBD5E1; background:#F8FAFC; color:#0F172A; }}
    .check-header {{ display:flex; align-items:center; background:linear-gradient(135deg,var(--navy),var(--navy2)); color:#FFFFFF !important; font-weight:950; font-size:13px; text-align:center; border-radius:15px 15px 0 0; padding:12px 8px; }}
    .check-header div {{ color:#FFFFFF !important; }}
    .chapter-band {{ background:#EAF1F8; color:var(--navy); border-left:6px solid var(--navy); border-radius:12px; padding:10px 14px; margin-top:10px; margin-bottom:4px; font-size:13px; font-weight:950; }}
    .id-badge {{ display:inline-block; min-width:44px; text-align:center; padding:7px 9px; border-radius:999px; background:#EFF6FF; color:#1E3A8A; font-weight:950; font-size:12px; }}
    .critere-text {{ font-size:13.2px; color:#1F2937; line-height:1.38; padding-top:7px; }}
    .trace-note {{ border-left:5px solid var(--teal); background:#ECFDF5; color:#065F46; padding:13px 16px; border-radius:13px; font-size:13px; font-weight:750; margin-bottom:15px; }}
    .warning-note {{ border-left:5px solid var(--amber); background:#FFFBEB; color:#92400E; padding:13px 16px; border-radius:13px; font-size:13px; font-weight:750; margin-bottom:15px; }}
    .audit-strip {{ display:grid; grid-template-columns: repeat(3, 1fr); gap:12px; margin:10px 0 16px; }}
    .audit-box {{ background:#F8FAFC; border:1px solid #D7E0EA; border-radius:14px; padding:12px 14px; }}
    .audit-label {{ color:#64748B; font-size:11px; font-weight:950; text-transform:uppercase; letter-spacing:.05em; }}
    .audit-value {{ color:#0B2D4D; font-size:13px; font-weight:850; margin-top:5px; }}
    .download-zone {{ background:#F8FAFC; border:1px dashed #94A3B8; border-radius:16px; padding:16px; margin-top:16px; }}
    </style>
    """, unsafe_allow_html=True)


def render_main_header():
    st.markdown(f"""
    <div class="top-header">
        <div class="logo-box">{logo_img(SEGULA_LOGO, "SEGULA Technologies")}</div>
        <div class="main-title">{APP_TITLE}<div class="main-subtitle">{APP_SUBTITLE}</div></div>
        <div class="logo-box">{logo_img(BOMBARDIER_LOGO, "Bombardier")}</div>
    </div>
    """, unsafe_allow_html=True)


def render_auth_header():
    st.markdown(f"""
    <div class="auth-header">
        <div class="logo-box">{logo_img(SEGULA_LOGO, "SEGULA Technologies")}</div>
        <div class="auth-title-center"><div class="t1">{APP_TITLE}</div><div class="t2">{APP_SUBTITLE}</div></div>
        <div class="logo-box">{logo_img(BOMBARDIER_LOGO, "Bombardier")}</div>
    </div>
    """, unsafe_allow_html=True)

# ==============================================================================
# BASE DE DONNÉES
# ==============================================================================
def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)


def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS notebooks_headers (
        ref_cahier TEXT PRIMARY KEY,
        nom_projet TEXT,
        programme_avion TEXT,
        ref_drawing TEXT,
        part_number TEXT,
        statut_global TEXT,
        agent_nom TEXT,
        pilote_nom TEXT,
        qualite_nom TEXT,
        date_modif TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS grid_evaluations (
        ref_cahier TEXT,
        id_point TEXT,
        jug_agent TEXT,
        jug_pilote TEXT,
        jug_qualite TEXT,
        commentaire TEXT,
        PRIMARY KEY (ref_cahier, id_point)
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS master_checklist (
        id_point TEXT PRIMARY KEY,
        chap TEXT,
        desc TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS access_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        full_name TEXT NOT NULL,
        role TEXT NOT NULL,
        email TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'PENDING',
        token TEXT UNIQUE NOT NULL,
        personal_password TEXT,
        created_at TEXT,
        approved_at TEXT,
        approved_by TEXT,
        admin_mail_sent INTEGER DEFAULT 0,
        user_mail_sent INTEGER DEFAULT 0,
        last_error TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS authorized_users (
        email TEXT PRIMARY KEY,
        full_name TEXT NOT NULL,
        role TEXT NOT NULL,
        personal_password TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'ACTIVE',
        created_at TEXT,
        approved_at TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS trace_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ref_cahier TEXT,
        action TEXT,
        user_name TEXT,
        user_role TEXT,
        details TEXT,
        created_at TEXT
    )""")

    # Migration douce : commentaires séparés par profil afin que chaque utilisateur
    # travaille uniquement dans sa zone sans modifier celle des autres.
    existing_cols = [row[1] for row in c.execute("PRAGMA table_info(grid_evaluations)").fetchall()]
    for col_name in ["commentaire_agent", "commentaire_pilote", "commentaire_qualite"]:
        if col_name not in existing_cols:
            c.execute(f"ALTER TABLE grid_evaluations ADD COLUMN {col_name} TEXT DEFAULT ''")

    c.execute("SELECT count(*) FROM master_checklist")
    if c.fetchone()[0] == 0:
        df = pd.read_csv(CHECKLIST_CSV) if CHECKLIST_CSV.exists() else pd.DataFrame(columns=["id_point", "chap", "desc"])
        c.executemany("INSERT INTO master_checklist VALUES (?, ?, ?)", df[["id_point", "chap", "desc"]].values.tolist())
    conn.commit()
    conn.close()


init_db()


def log_action(ref_cahier, action, details=""):
    try:
        conn = get_conn()
        conn.execute("INSERT INTO trace_log (ref_cahier, action, user_name, user_role, details, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                     (ref_cahier, action, st.session_state.get("user_name", ""), st.session_state.get("user_role", ""), details, now_str()))
        conn.commit()
        conn.close()
    except Exception:
        pass


def get_checklist_df():
    conn = get_conn()
    df = pd.read_sql_query("""
        SELECT * FROM master_checklist
        ORDER BY CAST(substr(id_point, 1, instr(id_point, '.') - 1) AS INTEGER),
                 CAST(substr(id_point, instr(id_point, '.') + 1) AS INTEGER)
    """, conn)
    conn.close()
    return df


def get_all_cahiers():
    conn = get_conn()
    df = pd.read_sql_query("SELECT ref_cahier, nom_projet, statut_global, date_modif FROM notebooks_headers ORDER BY date_modif DESC", conn)
    conn.close()
    return df


def get_header_and_evals(ref_cahier):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM notebooks_headers WHERE ref_cahier=?", (ref_cahier,))
    row = cursor.fetchone()
    if row:
        header = {
            "ref_cahier": row[0], "nom_projet": row[1], "programme_avion": row[2], "ref_drawing": row[3],
            "part_number": row[4], "statut_global": row[5], "agent_nom": row[6], "pilote_nom": row[7],
            "qualite_nom": row[8], "date_modif": row[9]
        }
        evals_df = pd.read_sql_query("SELECT * FROM grid_evaluations WHERE ref_cahier=?", conn, params=(ref_cahier,))
        if not evals_df.empty and "commentaire" in evals_df.columns:
            for col in ["commentaire_agent", "commentaire_pilote", "commentaire_qualite"]:
                if col not in evals_df.columns:
                    evals_df[col] = ""
            evals_df["commentaire_agent"] = evals_df["commentaire_agent"].where(evals_df["commentaire_agent"].astype(str).str.len() > 0, evals_df["commentaire"].fillna(""))
    else:
        header = {}
        evals_df = pd.DataFrame()
    conn.close()
    saved = evals_df.set_index("id_point").to_dict("index") if not evals_df.empty else {}
    return header, saved


def get_last_trace(ref_cahier, user_name=None, user_role=None):
    if not ref_cahier or ref_cahier == "NEW":
        return None
    conn = get_conn()
    query = "SELECT created_at, user_name, user_role, action, details FROM trace_log WHERE ref_cahier=?"
    params = [ref_cahier]
    if user_name:
        query += " AND user_name=?"
        params.append(user_name)
    if user_role:
        query += " AND user_role=?"
        params.append(user_role)
    query += " ORDER BY created_at DESC LIMIT 1"
    row = conn.execute(query, params).fetchone()
    conn.close()
    return row

# ==============================================================================
# MAILS
# ==============================================================================
def smtp_ready():
    return bool(SMTP_HOST and SMTP_PORT and SMTP_USER and SMTP_PASSWORD and SMTP_FROM)


def send_email(to_email, subject, html_body, text_body=None):
    if not smtp_ready():
        return False, "Configuration SMTP incomplète. Vérifiez .streamlit/secrets.toml."
    try:
        msg = EmailMessage()
        msg["From"] = SMTP_FROM
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.set_content(text_body or re.sub(r"<[^>]+>", "", html_body))
        msg.add_alternative(html_body, subtype="html")
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=context) as server:
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
        return True, "E-mail envoyé."
    except Exception as e:
        return False, str(e)


def email_template(title, body_html):
    return f"""
    <html><body style="margin:0;padding:0;background:#F4F7FA;font-family:Segoe UI,Arial,sans-serif;color:#0F172A;">
      <table width="100%" cellspacing="0" cellpadding="0" style="background:#F4F7FA;padding:24px 0;">
        <tr><td align="center">
          <table width="640" cellspacing="0" cellpadding="0" style="background:#FFFFFF;border-radius:18px;overflow:hidden;border:1px solid #DDE6F0;">
            <tr><td style="background:#0B2D4D;color:white;padding:22px 26px;font-size:20px;font-weight:800;">{escape(title)}</td></tr>
            <tr><td style="padding:26px;line-height:1.6;font-size:15px;">{body_html}</td></tr>
            <tr><td style="background:#F8FAFC;border-top:1px solid #E2E8F0;padding:16px 26px;color:#64748B;font-size:12px;">
              Checklist Digitalisée des Cahiers de Montage - Normes Bombardier Aerospace<br>
              Plateforme développée par {escape(PROJECT_OWNER)} dans le cadre du {escape(PROJECT_CONTEXT)}.
            </td></tr>
          </table>
        </td></tr>
      </table>
    </body></html>
    """


def send_admin_request_mail(request_id, full_name, role, email, token):
    approve_link = f"{APP_URL}/?approve_token={token}"
    body = f"""
    <p>Bonjour,</p>
    <p>Une nouvelle demande d'accès à la checklist digitalisée est en attente de validation.</p>
    <table cellspacing="0" cellpadding="8" style="border-collapse:collapse;width:100%;font-size:14px;">
      <tr><td style="border:1px solid #E2E8F0;background:#F8FAFC;font-weight:700;">Nom et prénom</td><td style="border:1px solid #E2E8F0;">{escape(full_name)}</td></tr>
      <tr><td style="border:1px solid #E2E8F0;background:#F8FAFC;font-weight:700;">Profil demandé</td><td style="border:1px solid #E2E8F0;">{escape(role)}</td></tr>
      <tr><td style="border:1px solid #E2E8F0;background:#F8FAFC;font-weight:700;">E-mail</td><td style="border:1px solid #E2E8F0;">{escape(email)}</td></tr>
    </table>
    <p style="margin-top:24px;">Après vérification, cliquez sur le bouton ci-dessous pour donner l'accès.</p>
    <p><a href="{approve_link}" style="display:inline-block;background:#0B2D4D;color:white;text-decoration:none;padding:13px 20px;border-radius:10px;font-weight:800;">Donner l'accès</a></p>
    <p style="color:#64748B;font-size:12px;">Identifiant demande : {request_id}</p>
    """
    return send_email(ADMIN_EMAIL, "Nouvelle demande d'accès - Checklist Digitalisée", email_template("Nouvelle demande d'accès", body))


def send_user_welcome_mail(full_name, role, email, password):
    body = f"""
    <p>Bonjour {escape(full_name)},</p>
    <p>Votre accès à la plateforme a été validé.</p>
    <p>Bienvenue dans la checklist digitalisée selon les normes Bombardier. Voici votre mot de passe personnel. Copiez-le puis utilisez-le dans la page d’authentification pour accéder à la plateforme.</p>
    <table cellspacing="0" cellpadding="10" style="border-collapse:collapse;width:100%;font-size:14px;margin-top:14px;">
      <tr><td style="border:1px solid #E2E8F0;background:#F8FAFC;font-weight:700;">Nom et prénom</td><td style="border:1px solid #E2E8F0;">{escape(full_name)}</td></tr>
      <tr><td style="border:1px solid #E2E8F0;background:#F8FAFC;font-weight:700;">Profil</td><td style="border:1px solid #E2E8F0;">{escape(role)}</td></tr>
      <tr><td style="border:1px solid #E2E8F0;background:#F8FAFC;font-weight:700;">Mot de passe personnel</td><td style="border:1px solid #E2E8F0;font-weight:900;color:#0B2D4D;font-size:16px;">{escape(password)}</td></tr>
    </table>
    <p style="margin-top:20px;">Pour revenir vers l’application, cliquez sur le bouton ci-dessous. Si le bouton ne fonctionne pas, vérifiez que le lien APP_URL est correctement renseigné dans les secrets Streamlit.</p>
    <p><a href="{APP_URL}" style="display:inline-block;background:#0F766E;color:white;text-decoration:none;padding:13px 20px;border-radius:10px;font-weight:800;">Ouvrir la plateforme</a></p>
    <p>Nous vous souhaitons une bonne utilisation.</p>
    """
    return send_email(email, "Accès validé - Checklist Digitalisée", email_template("Bienvenue dans la checklist digitalisée", body))

# ==============================================================================
# ACCÈS
# ==============================================================================
def create_access_request(full_name, role, email):
    full_name = clean_name(full_name)
    email = clean_email(email)
    token = py_secrets.token_urlsafe(32)
    conn = get_conn()
    c = conn.cursor()
    c.execute("""INSERT INTO access_requests
                 (full_name, role, email, status, token, created_at)
                 VALUES (?, ?, ?, 'PENDING', ?, ?)""", (full_name, role, email, token, now_str()))
    request_id = c.lastrowid
    conn.commit()
    conn.close()
    ok, msg = send_admin_request_mail(request_id, full_name, role, email, token)
    conn = get_conn()
    conn.execute("UPDATE access_requests SET admin_mail_sent=?, last_error=? WHERE id=?", (1 if ok else 0, None if ok else msg, request_id))
    conn.commit()
    conn.close()
    return ok, msg


def approve_access_by_token(token):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id, full_name, role, email, status FROM access_requests WHERE token=?", (token,))
    row = c.fetchone()
    if not row:
        conn.close()
        return False, "Lien invalide ou demande introuvable."
    req_id, full_name, role, email, status = row
    password = generer_mot_de_passe(role, full_name)
    if status != "APPROVED":
        c.execute("""UPDATE access_requests
                     SET status='APPROVED', personal_password=?, approved_at=?, approved_by=?
                     WHERE id=?""", (password, now_str(), ADMIN_EMAIL, req_id))
        c.execute("""INSERT OR REPLACE INTO authorized_users
                     (email, full_name, role, personal_password, status, created_at, approved_at)
                     VALUES (?, ?, ?, ?, 'ACTIVE',
                             COALESCE((SELECT created_at FROM authorized_users WHERE email=?), ?), ?)""",
                  (email, full_name, role, password, email, now_str(), now_str()))
        conn.commit()
    ok, msg = send_user_welcome_mail(full_name, role, email, password)
    c.execute("UPDATE access_requests SET user_mail_sent=?, last_error=? WHERE id=?", (1 if ok else 0, None if ok else msg, req_id))
    conn.commit()
    conn.close()
    if ok:
        return True, f"Accès validé pour {full_name}. L'utilisateur doit consulter sa boîte mail pour récupérer son mot de passe personnel."
    return False, f"Accès validé, mais l'e-mail utilisateur n'a pas été envoyé : {msg}"


def authenticate_user(full_name, role, password):
    conn = get_conn()
    df = pd.read_sql_query("""SELECT * FROM authorized_users
                              WHERE lower(full_name)=lower(?) AND role=? AND personal_password=? AND status='ACTIVE'""",
                           conn, params=(clean_name(full_name), role, password))
    conn.close()
    if not df.empty:
        return True, df.iloc[0].to_dict()
    return False, None

# ==============================================================================
# KPI
# ==============================================================================
def compute_profile_counts(df_evals, column_name, total_items):
    if df_evals.empty or column_name not in df_evals.columns:
        ok = nok = na = checked = 0
    else:
        ok = int((df_evals[column_name] == "OK").sum())
        nok = int((df_evals[column_name] == "NOK").sum())
        na = int((df_evals[column_name] == "NA").sum())
        checked = ok + nok + na
    remaining = max(total_items - checked, 0)
    return {
        "OK": ok,
        "NOK": nok,
        "NA": na,
        "Restant": remaining,
        "Renseigné": checked,
        "Taux renseignement": (checked / total_items * 100) if total_items else 0,
        "Taux OK": (ok / total_items * 100) if total_items else 0,
    }


def is_role_complete(saved_evals, column_key, total_items):
    count = 0
    for value in saved_evals.values():
        if value.get(column_key, "") in ["OK", "NOK", "NA"]:
            count += 1
    return total_items > 0 and count >= total_items


def compute_global_maturity(df_evals, total_items):
    total_cells = total_items * 3
    if total_cells == 0 or df_evals.empty:
        return 0.0, 0.0
    ok_total = int((df_evals["jug_agent"] == "OK").sum() + (df_evals["jug_pilote"] == "OK").sum() + (df_evals["jug_qualite"] == "OK").sum())
    checked_total = int(df_evals["jug_agent"].isin(["OK", "NOK", "NA"]).sum() + df_evals["jug_pilote"].isin(["OK", "NOK", "NA"]).sum() + df_evals["jug_qualite"].isin(["OK", "NOK", "NA"]).sum())
    return ok_total / total_cells * 100, checked_total / total_cells * 100


def final_status_from_evals(df_evals, total_items, names):
    maturity, _ = compute_global_maturity(df_evals, total_items)
    total_nok = int((df_evals[["jug_agent", "jug_pilote", "jug_qualite"]] == "NOK").sum().sum()) if not df_evals.empty else 0
    if total_nok > 0:
        return "Bloqué - NOK à traiter"
    if maturity >= 100:
        return "Approuvé - Cahier conforme"
    if names.get("qualite_nom"):
        return "Contrôle Qualité en cours"
    if names.get("pilote_nom"):
        return "Validation Pilote en cours"
    if names.get("agent_nom"):
        return "Contrôle Agent en cours"
    return "En cours de création"

# ==============================================================================
# PAGES
# ==============================================================================
def render_approval_page(token):
    apply_global_style()
    st.markdown('<div class="auth-shell"><div class="auth-card">', unsafe_allow_html=True)
    render_auth_header()
    st.markdown('<div style="padding:34px;">', unsafe_allow_html=True)
    ok, msg = approve_access_by_token(token)
    if ok:
        st.success(msg)
    else:
        st.error(msg)
    if st.button("Retour à la page de connexion"):
        clear_query_params()
        st.session_state["app_state"] = "LOGIN"
        st.rerun()
    st.markdown('</div><div class="auth-footer">Validation administrateur des demandes d’accès.</div></div></div>', unsafe_allow_html=True)
    st.stop()


def render_login_page():
    st.markdown('<div class="auth-shell"><div class="auth-card">', unsafe_allow_html=True)
    render_auth_header()
    st.markdown('<div class="auth-body">', unsafe_allow_html=True)
    st.markdown("""
    <div class="auth-left">
        <div>
            <h1>Portail d'authentification</h1>
            <p>Plateforme interne destinée au suivi, à la validation et à la traçabilité des cahiers de montage.</p>
            <div class="auth-line"></div>
            <div class="auth-point"><b>Traçabilité :</b> chaque cahier conserve sa checklist, ses visas et son historique.</div>
            <div class="auth-point"><b>Validation séquentielle :</b> Agent Méthodes, Pilote d'Activité, puis Responsable Qualité.</div>
            <div class="auth-point"><b>Pilotage :</b> les KPI permettent de suivre l’avancement et les points NOK par cahier.</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    st.markdown('<div class="auth-right">', unsafe_allow_html=True)
    tab_login, tab_request = st.tabs(["Connexion", "Demander l'accès"])

    with tab_login:
        st.markdown('<div class="form-title">Connexion utilisateur</div>', unsafe_allow_html=True)
        st.markdown('<div class="form-subtitle">Saisissez les informations validées par l’administrateur.</div>', unsafe_allow_html=True)
        role = st.selectbox("Profil", ROLES, key="login_role")
        nom_user = st.text_input("Nom & prénom", placeholder="Ex : Nom Prénom", key="login_name")
        pwd = st.text_input("Mot de passe personnel", type="password", placeholder="Saisir le mot de passe reçu par e-mail", key="login_pwd")
        if st.button("Se connecter", use_container_width=True):
            ok, user = authenticate_user(nom_user, role, pwd)
            if not clean_name(nom_user) or not pwd:
                st.error("Veuillez renseigner votre nom et votre mot de passe personnel.")
            elif ok:
                st.session_state["user_role"] = user["role"]
                st.session_state["user_name"] = user["full_name"]
                st.session_state["user_email"] = user["email"]
                st.session_state["app_state"] = "HOME"
                st.rerun()
            else:
                st.error("Accès refusé. Vérifiez votre nom, votre profil et le mot de passe reçu par e-mail.")

    with tab_request:
        st.markdown('<div class="form-title">Nouvelle demande d’accès</div>', unsafe_allow_html=True)
        st.markdown('<div class="form-subtitle">Votre demande sera envoyée à l’administrateur pour validation.</div>', unsafe_allow_html=True)
        req_name = st.text_input("Nom & prénom", placeholder="Ex : Nom Prénom", key="req_name")
        req_role = st.selectbox("Profil demandé", ROLES, key="req_role")
        req_email = st.text_input("Adresse e-mail", placeholder="exemple@domaine.com", key="req_email")
        if st.button("Envoyer la demande", use_container_width=True):
            if not clean_name(req_name):
                st.error("Veuillez saisir votre nom et prénom.")
            elif not is_valid_email(req_email):
                st.error("Veuillez saisir une adresse e-mail valide.")
            else:
                ok, msg = create_access_request(req_name, req_role, req_email)
                if ok:
                    st.success("Votre demande a été envoyée à l’administrateur. Après validation, vous recevrez votre mot de passe personnel par e-mail.")
                else:
                    st.error(f"Demande enregistrée, mais l’e-mail administrateur n’a pas été envoyé : {msg}")

    st.markdown('</div></div>', unsafe_allow_html=True)
    st.markdown(f'<div class="auth-footer">Application développée par <b>{PROJECT_OWNER}</b> dans le cadre de son <b>{PROJECT_CONTEXT}</b>. Objectif : {PROJECT_OBJECTIVE}</div>', unsafe_allow_html=True)
    st.markdown('</div></div>', unsafe_allow_html=True)
    st.stop()


def render_home_page():
    render_main_header()
    st.markdown(f"""
    <div class="session-banner">
        Session active : {escape(st.session_state.get('user_name',''))} | Profil : {escape(st.session_state.get('user_role',''))}
    </div>
    <div class="hero-card">
        <div class="hero-title">Plateforme de traçabilité des cahiers de montage</div>
        <div class="hero-subtitle">
            Cette interface permet de créer, contrôler et valider les cahiers VWI selon une logique séquentielle et traçable :
            Agent Méthodes, Pilote d'Activité puis Responsable Qualité. Chaque cahier conserve sa checklist, ses visas et son tableau de bord KPI.
        </div>
    </div>
    """, unsafe_allow_html=True)

    df_cahiers = get_all_cahiers()
    total = len(df_cahiers)
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(f'<div class="metric-card"><div class="metric-label">Cahiers enregistrés</div><div class="metric-value">{total}</div><div class="metric-help">Chaque référence VWI possède sa propre checklist.</div></div>', unsafe_allow_html=True)
    with c2:
        en_cours = int(df_cahiers["statut_global"].str.contains("cours|Contrôle|Validation", case=False, na=False).sum()) if not df_cahiers.empty else 0
        st.markdown(f'<div class="metric-card"><div class="metric-label">Cahiers en cours</div><div class="metric-value">{en_cours}</div><div class="metric-help">Dossiers non finalisés ou en validation.</div></div>', unsafe_allow_html=True)
    with c3:
        appr = int(df_cahiers["statut_global"].str.contains("Approuvé", case=False, na=False).sum()) if not df_cahiers.empty else 0
        st.markdown(f'<div class="metric-card"><div class="metric-label">Cahiers approuvés</div><div class="metric-value">{appr}</div><div class="metric-help">Dossiers arrivés au statut conforme.</div></div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    m1, m2, m3 = st.columns(3)
    with m1:
        st.markdown('<div class="module-card"><div class="module-title">Créer un nouveau cahier</div><div class="module-text">Ouvrir une nouvelle checklist indépendante avec son propre en-tête, ses contrôles et son historique.</div>', unsafe_allow_html=True)
        if st.button("Nouveau cahier VWI", use_container_width=True):
            st.session_state["current_cahier"] = "NEW"
            st.session_state["app_state"] = "WORKSPACE"
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
    with m2:
        st.markdown('<div class="module-card"><div class="module-title">Ouvrir un cahier existant</div><div class="module-text">Reprendre une checklist déjà enregistrée avec les visas et les jugements propres à ce cahier.</div>', unsafe_allow_html=True)
        if not df_cahiers.empty:
            selected = st.selectbox("Sélectionner un cahier", df_cahiers["ref_cahier"].tolist(), label_visibility="collapsed")
            if st.button("Ouvrir le cahier", use_container_width=True):
                st.session_state["current_cahier"] = selected
                st.session_state["app_state"] = "WORKSPACE"
                st.rerun()
        else:
            st.info("Aucun cahier enregistré.")
        st.markdown('</div>', unsafe_allow_html=True)
    with m3:
        st.markdown('<div class="module-card"><div class="module-title">Dashboard KPI</div><div class="module-text">Analyser l’avancement par profil, les OK, les NOK, les NA et la maturité globale du cahier.</div>', unsafe_allow_html=True)
        if st.button("Accéder au dashboard", use_container_width=True):
            st.session_state["app_state"] = "DASHBOARD"
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("Quitter la session"):
        for key in ["user_role", "user_name", "user_email", "current_cahier"]:
            st.session_state.pop(key, None)
        st.session_state["app_state"] = "LOGIN"
        st.rerun()


def render_workspace_page():
    render_main_header()
    if st.button("Retour à l'accueil"):
        st.session_state["app_state"] = "HOME"
        st.rerun()

    checklist_df = get_checklist_df()
    total_items = len(checklist_df)
    role = st.session_state["user_role"]
    user = st.session_state["user_name"]
    is_agent = role == "Agent Méthodes"
    is_pilote = role == "Pilote d'Activité"
    is_qualite = role == "Responsable Qualité"

    if st.session_state.get("current_cahier") == "NEW":
        header_data = {
            "ref_cahier": "", "nom_projet": "", "programme_avion": "Global Express", "ref_drawing": "", "part_number": "",
            "statut_global": "En cours de création", "agent_nom": "", "pilote_nom": "", "qualite_nom": "", "date_modif": "Nouvelle création"
        }
        saved_evals = {}
    else:
        header_data, saved_evals = get_header_and_evals(st.session_state["current_cahier"])
        if not header_data:
            st.error("Cahier introuvable.")
            return

    agent_value = header_data.get("agent_nom", "")
    pilote_value = header_data.get("pilote_nom", "")
    qualite_value = header_data.get("qualite_nom", "")
    if is_agent and not agent_value:
        agent_value = user
    if is_pilote and not pilote_value:
        pilote_value = user
    if is_qualite and not qualite_value:
        qualite_value = user

    agent_done = is_role_complete(saved_evals, "jug_agent", total_items)
    pilote_done = is_role_complete(saved_evals, "jug_pilote", total_items)
    allowed_to_edit = False
    block_reason = ""
    if is_agent:
        allowed_to_edit = True
    elif is_pilote:
        allowed_to_edit = agent_done
        if not allowed_to_edit:
            block_reason = "Le Pilote d'Activité peut intervenir seulement après que l’Agent Méthodes a renseigné toute sa colonne."
    elif is_qualite:
        allowed_to_edit = pilote_done
        if not allowed_to_edit:
            block_reason = "Le Responsable Qualité peut intervenir seulement après que le Pilote d'Activité a renseigné toute sa colonne."

    st.markdown(f'<div class="session-banner">Cahier sélectionné : {escape(header_data.get("ref_cahier") or "Nouvelle création")} | Session : {escape(user)} | Profil : {escape(role)}</div>', unsafe_allow_html=True)

    last_global = header_data.get("date_modif", "Nouvelle création")
    last_user_row = get_last_trace(header_data.get("ref_cahier", ""), user, role) if header_data.get("ref_cahier") else None
    last_user = last_user_row[0] if last_user_row else "Aucune modification enregistrée par cette session"
    st.markdown(f'''
    <div class="audit-strip">
        <div class="audit-box"><div class="audit-label">Dernière modification du cahier</div><div class="audit-value">{escape(str(last_global))}</div></div>
        <div class="audit-box"><div class="audit-label">Dernière modification par vous</div><div class="audit-value">{escape(str(last_user))}</div></div>
        <div class="audit-box"><div class="audit-label">Mode de saisie</div><div class="audit-value">Colonne profil verrouillée</div></div>
    </div>
    ''', unsafe_allow_html=True)

    st.markdown('<div class="pro-card">', unsafe_allow_html=True)
    st.markdown('<h4>En-tête technique du cahier</h4>', unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        vwi_input = st.text_input("Référence cahier VWI", value=header_data.get("ref_cahier", ""), disabled=(st.session_state.get("current_cahier") != "NEW"))
        proj_input = st.text_input("Nom du projet", value=header_data.get("nom_projet", ""))
    with c2:
        prog_default = header_data.get("programme_avion", "Global Express") or "Global Express"
        prog_index = PROGRAMMES.index(prog_default) if prog_default in PROGRAMMES else 0
        prog_input = st.selectbox("Programme aéronef", PROGRAMMES, index=prog_index)
        drw_input = st.text_input("Dessin d'ensemble DRW", value=header_data.get("ref_drawing", ""))
    with c3:
        pn_input = st.text_input("Part Number P/N", value=header_data.get("part_number", ""))
        st.markdown(f"<br><span class='status-pill'>{escape(header_data.get('statut_global',''))}</span>", unsafe_allow_html=True)
    with c4:
        agent_s = st.text_input("Visa Agent Méthodes", value=agent_value, disabled=True)
        pilote_s = st.text_input("Visa Pilote d'Activité", value=pilote_value, disabled=True)
        qualite_s = st.text_input("Visa Responsable Qualité", value=qualite_value, disabled=True)
    st.markdown('</div>', unsafe_allow_html=True)

    if block_reason:
        st.markdown(f'<div class="warning-note">{escape(block_reason)}</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="trace-note">Vous pouvez renseigner uniquement la colonne correspondant à votre profil. Les autres colonnes sont protégées.</div>', unsafe_allow_html=True)

    st.markdown("""
    <div class="check-header">
        <div style="width:6%;">ID</div>
        <div style="width:34%; text-align:left;">Critère de conformité</div>
        <div style="width:20%;">Agent Méthodes<br><span style="font-size:11px;font-weight:700;">Jugement / note</span></div>
        <div style="width:20%;">Pilote Activité<br><span style="font-size:11px;font-weight:700;">Jugement / note</span></div>
        <div style="width:20%;">Qualité<br><span style="font-size:11px;font-weight:700;">Jugement / note</span></div>
    </div>
    """, unsafe_allow_html=True)

    form_results = {}
    current_chapter = None
    opts = ["", "OK", "NOK", "NA"]
    for _, item in checklist_df.iterrows():
        if item["chap"] != current_chapter:
            current_chapter = item["chap"]
            st.markdown(f'<div class="chapter-band">{escape(current_chapter)}</div>', unsafe_allow_html=True)
        saved = saved_evals.get(item["id_point"], {})
        sv_ag = saved.get("jug_agent", "")
        sv_pi = saved.get("jug_pilote", "")
        sv_qu = saved.get("jug_qualite", "")
        sv_txt_ag = saved.get("commentaire_agent", saved.get("commentaire", ""))
        sv_txt_pi = saved.get("commentaire_pilote", "")
        sv_txt_qu = saved.get("commentaire_qualite", "")

        c_id, c_desc, c_ag, c_pi, c_qu = st.columns([0.6, 3.4, 2.0, 2.0, 2.0])
        c_id.markdown(f'<span class="id-badge">{escape(item["id_point"])}</span>', unsafe_allow_html=True)
        c_desc.markdown(f'<div class="critere-text">{escape(item["desc"])}</div>', unsafe_allow_html=True)
        j_ag = c_ag.selectbox(f"AG_{item['id_point']}", opts, index=opts.index(sv_ag) if sv_ag in opts else 0, label_visibility="collapsed", disabled=(not is_agent or not allowed_to_edit))
        txt_ag = c_ag.text_input(f"N_AG_{item['id_point']}", value=sv_txt_ag, label_visibility="collapsed", placeholder="Note Agent", disabled=(not is_agent or not allowed_to_edit))
        j_pi = c_pi.selectbox(f"PI_{item['id_point']}", opts, index=opts.index(sv_pi) if sv_pi in opts else 0, label_visibility="collapsed", disabled=(not is_pilote or not allowed_to_edit))
        txt_pi = c_pi.text_input(f"N_PI_{item['id_point']}", value=sv_txt_pi, label_visibility="collapsed", placeholder="Note Pilote", disabled=(not is_pilote or not allowed_to_edit))
        j_qu = c_qu.selectbox(f"QU_{item['id_point']}", opts, index=opts.index(sv_qu) if sv_qu in opts else 0, label_visibility="collapsed", disabled=(not is_qualite or not allowed_to_edit))
        txt_qu = c_qu.text_input(f"N_QU_{item['id_point']}", value=sv_txt_qu, label_visibility="collapsed", placeholder="Note Qualité", disabled=(not is_qualite or not allowed_to_edit))
        legacy_comment = " | ".join([txt for txt in [txt_ag, txt_pi, txt_qu] if str(txt or "").strip()])
        form_results[item["id_point"]] = {
            "jug_agent": j_ag, "jug_pilote": j_pi, "jug_qualite": j_qu,
            "commentaire": legacy_comment,
            "commentaire_agent": txt_ag, "commentaire_pilote": txt_pi, "commentaire_qualite": txt_qu
        }
        st.markdown('<div style="border-bottom:1px solid #E2E8F0; margin:2px 0 0;"></div>', unsafe_allow_html=True)

    with st.expander("Configuration des critères de la checklist (ajouter / modifier / supprimer)"):
        st.markdown("Ajouter ou supprimer un critère de la base maître.")
        col_new1, col_new2, col_new3 = st.columns([1, 2, 3])
        new_id = col_new1.text_input("ID unique", placeholder="Ex : 10.1")
        new_chap = col_new2.text_input("Chapitre", placeholder="Ex : CHAPITRE 10 : ...")
        new_desc = col_new3.text_input("Critère", placeholder="Énoncé du critère")
        if st.button("Enregistrer le nouveau critère"):
            if new_id and new_chap and new_desc:
                conn = get_conn()
                conn.execute("INSERT OR REPLACE INTO master_checklist VALUES (?, ?, ?)", (new_id, new_chap, new_desc))
                conn.commit()
                conn.close()
                st.success("Critère enregistré.")
                st.rerun()
            else:
                st.error("Veuillez renseigner ID, chapitre et critère.")
        st.markdown("---")
        # Compatibilité Streamlit Cloud / Pandas Arrow : éviter l’addition directe de Series texte
        # qui peut provoquer un TypeError avec certains types string[pyarrow].
        options_liste = [
            f"{str(row['id_point'])} - {str(row['desc'])}"
            for _, row in checklist_df.iterrows()
        ]
        if options_liste:
            critere_selectionne = st.selectbox("Critère à supprimer", options_liste)
            if st.button("Supprimer le critère sélectionné"):
                id_a_effacer = critere_selectionne.split(" - ")[0]
                conn = get_conn()
                conn.execute("DELETE FROM master_checklist WHERE id_point=?", (id_a_effacer,))
                conn.commit()
                conn.close()
                st.success("Critère supprimé.")
                st.rerun()
        else:
            st.info("Aucun critère disponible à supprimer.")


    def build_checklist_export_dataframe():
        export_rows = []
        for _, row in checklist_df.iterrows():
            values = form_results.get(row["id_point"], {})
            export_rows.append({
                "ID": row["id_point"],
                "Chapitre": row["chap"],
                "Critère": row["desc"],
                "Agent Méthodes": values.get("jug_agent", ""),
                "Note Agent": values.get("commentaire_agent", ""),
                "Pilote d'Activité": values.get("jug_pilote", ""),
                "Note Pilote": values.get("commentaire_pilote", ""),
                "Responsable Qualité": values.get("jug_qualite", ""),
                "Note Qualité": values.get("commentaire_qualite", ""),
            })
        return pd.DataFrame(export_rows)

    def export_checklist_excel():
        output = io.BytesIO()
        export_df = build_checklist_export_dataframe()
        header_df = pd.DataFrame([
            ["Référence VWI", vwi_input.strip()],
            ["Projet", proj_input],
            ["Programme", prog_input],
            ["DRW", drw_input],
            ["Part Number", pn_input],
            ["Statut", header_data.get("statut_global", "")],
            ["Agent Méthodes", agent_s],
            ["Pilote d'Activité", pilote_s],
            ["Responsable Qualité", qualite_s],
            ["Dernière modification", header_data.get("date_modif", "")],
        ], columns=["Champ", "Valeur"])
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            header_df.to_excel(writer, sheet_name="En-tête", index=False)
            export_df.to_excel(writer, sheet_name="Checklist", index=False)
        output.seek(0)
        return output

    def export_checklist_pdf():
        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=landscape(letter), leftMargin=24, rightMargin=24, topMargin=24, bottomMargin=24)
        styles = getSampleStyleSheet()
        story = [Paragraph(f"CHECKLIST DU CAHIER VWI : {vwi_input.strip() or header_data.get('ref_cahier', 'Nouvelle création')}", styles["Heading1"]), Spacer(1, 10)]
        meta = [["Champ", "Valeur"], ["Projet", proj_input], ["Programme", prog_input], ["Statut", header_data.get("statut_global", "")], ["Agent", agent_s], ["Pilote", pilote_s], ["Qualité", qualite_s], ["Dernière modification", str(header_data.get("date_modif", ""))]]
        mt = Table(meta, colWidths=[150, 420])
        mt.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,0), colors.HexColor("#0B2D4D")), ("TEXTCOLOR", (0,0), (-1,0), colors.white), ("GRID", (0,0), (-1,-1), .5, colors.HexColor("#CBD5E1")), ("PADDING", (0,0), (-1,-1), 6)]))
        story += [mt, Spacer(1, 14)]
        export_df = build_checklist_export_dataframe()
        data = [["ID", "Critère", "Agent", "Pilote", "Qualité", "Notes"]]
        for _, r in export_df.iterrows():
            notes = " | ".join([str(x) for x in [r["Note Agent"], r["Note Pilote"], r["Note Qualité"]] if str(x).strip()])
            data.append([str(r["ID"]), Paragraph(str(r["Critère"]), styles["BodyText"]), str(r["Agent Méthodes"]), str(r["Pilote d'Activité"]), str(r["Responsable Qualité"]), Paragraph(notes, styles["BodyText"])])
        table = Table(data, colWidths=[42, 300, 70, 70, 70, 220], repeatRows=1)
        table.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,0), colors.HexColor("#0B2D4D")), ("TEXTCOLOR", (0,0), (-1,0), colors.white), ("GRID", (0,0), (-1,-1), .35, colors.HexColor("#CBD5E1")), ("VALIGN", (0,0), (-1,-1), "TOP"), ("FONTSIZE", (0,0), (-1,-1), 7), ("PADDING", (0,0), (-1,-1), 4)]))
        story.append(table)
        doc.build(story)
        buf.seek(0)
        return buf

    st.markdown('<div class="download-zone"><b>Export du cahier</b><br><span style="color:#64748B;font-size:13px;">Téléchargement de la checklist complète du cahier sélectionné avec en-tête, jugements, notes et traçabilité.</span></div>', unsafe_allow_html=True)
    st.download_button(
        "Télécharger la checklist PDF",
        data=export_checklist_pdf(),
        file_name=f"Checklist_{(vwi_input or header_data.get('ref_cahier','Nouveau')).replace('/', '_')}.pdf",
        mime="application/pdf",
        use_container_width=True
    )

    if allowed_to_edit:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Sauvegarder l'état du cahier", use_container_width=True):
            if not vwi_input.strip():
                st.error("La référence VWI est obligatoire pour enregistrer le cahier.")
            else:
                rows = []
                for pt_id, values in form_results.items():
                    rows.append({"id_point": pt_id, **values})
                current_df = pd.DataFrame(rows)
                names = {"agent_nom": agent_s, "pilote_nom": pilote_s, "qualite_nom": qualite_s}
                final_status = final_status_from_evals(current_df, total_items, names)
                conn = get_conn()
                c = conn.cursor()
                c.execute("""INSERT OR REPLACE INTO notebooks_headers VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                          (vwi_input.strip(), proj_input, prog_input, drw_input, pn_input, final_status, agent_s, pilote_s, qualite_s, now_str()))
                for pt_id, values in form_results.items():
                    c.execute("""INSERT OR REPLACE INTO grid_evaluations
                                 (ref_cahier, id_point, jug_agent, jug_pilote, jug_qualite, commentaire, commentaire_agent, commentaire_pilote, commentaire_qualite)
                                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                              (vwi_input.strip(), pt_id, values["jug_agent"], values["jug_pilote"], values["jug_qualite"], values.get("commentaire", ""), values.get("commentaire_agent", ""), values.get("commentaire_pilote", ""), values.get("commentaire_qualite", "")))
                conn.commit()
                conn.close()
                log_action(vwi_input.strip(), "Sauvegarde cahier", f"Statut : {final_status} | Dernière modification par {user} ({role})")
                st.success("Cahier sauvegardé avec succès. Les données sont archivées pour cette référence VWI.")
                st.session_state["current_cahier"] = vwi_input.strip()
                st.rerun()


def render_dashboard_page():
    render_main_header()
    if st.button("Revenir au menu principal"):
        st.session_state["app_state"] = "HOME"
        st.rerun()

    st.markdown('<div class="hero-card"><div class="hero-title">Dashboard KPI par cahier</div><div class="hero-subtitle">Analyse de l’avancement, des OK, NOK, NA, points restants et maturité qualité du cahier sélectionné.</div></div>', unsafe_allow_html=True)
    df_headers = get_all_cahiers()
    if df_headers.empty:
        st.info("Aucun cahier enregistré pour générer un dashboard.")
        return

    cahier_dashboard = st.selectbox("Sélectionnez le cahier VWI à analyser", df_headers["ref_cahier"].unique())
    conn = get_conn()
    df_evals = pd.read_sql_query("SELECT * FROM grid_evaluations WHERE ref_cahier=?", conn, params=(cahier_dashboard,))
    df_master = get_checklist_df()
    df_trace = pd.read_sql_query("SELECT * FROM trace_log WHERE ref_cahier=? ORDER BY created_at DESC LIMIT 20", conn, params=(cahier_dashboard,))
    conn.close()
    total_items = len(df_master)
    if df_evals.empty:
        st.warning("Aucune évaluation disponible pour ce cahier.")
        return

    counts = {
        "Agent Méthodes": compute_profile_counts(df_evals, "jug_agent", total_items),
        "Pilote d'Activité": compute_profile_counts(df_evals, "jug_pilote", total_items),
        "Responsable Qualité": compute_profile_counts(df_evals, "jug_qualite", total_items),
    }
    maturity, completion = compute_global_maturity(df_evals, total_items)
    total_ok = sum(value["OK"] for value in counts.values())
    total_nok = sum(value["NOK"] for value in counts.values())
    total_na = sum(value["NA"] for value in counts.values())
    total_remaining = sum(value["Restant"] for value in counts.values())

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.markdown(f'<div class="metric-card"><div class="metric-label">Maturité qualité</div><div class="metric-value">{maturity:.1f}%</div><div class="metric-help">100% uniquement si toutes les cellules des trois profils sont OK.</div></div>', unsafe_allow_html=True)
    with k2:
        st.markdown(f'<div class="metric-card"><div class="metric-label">Renseignement global</div><div class="metric-value">{completion:.1f}%</div><div class="metric-help">OK + NOK + NA renseignés sur toutes les colonnes.</div></div>', unsafe_allow_html=True)
    with k3:
        st.markdown(f'<div class="metric-card"><div class="metric-label">Total NOK</div><div class="metric-value">{total_nok}</div><div class="metric-help">Points bloquants ou à justifier.</div></div>', unsafe_allow_html=True)
    with k4:
        st.markdown(f'<div class="metric-card"><div class="metric-label">Points restants</div><div class="metric-value">{total_remaining}</div><div class="metric-help">Cellules encore non renseignées.</div></div>', unsafe_allow_html=True)

    st.markdown('<div class="pro-card">', unsafe_allow_html=True)
    st.markdown("#### Avancement par profil")
    prof_df = pd.DataFrame([
        {"Profil": role, "OK": value["OK"], "NOK": value["NOK"], "NA": value["NA"], "Restant": value["Restant"]}
        for role, value in counts.items()
    ])
    fig_bar = px.bar(prof_df, x="Profil", y=["OK", "NOK", "NA", "Restant"], barmode="group", text_auto=True, height=370)
    fig_bar.update_layout(margin=dict(t=35, b=20, l=10, r=10), legend_title_text="Statut", plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig_bar, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    g1, g2 = st.columns([1, 1])
    with g1:
        st.markdown('<div class="pro-card">', unsafe_allow_html=True)
        st.markdown("#### Synthèse globale")
        pie_df = pd.DataFrame({"Statut": ["OK", "NOK", "NA", "Restant"], "Nombre": [total_ok, total_nok, total_na, total_remaining]})
        fig_pie = px.pie(pie_df, values="Nombre", names="Statut", hole=0.45, height=390)
        fig_pie.update_layout(margin=dict(t=25, b=15, l=10, r=10), paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig_pie, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)
    with g2:
        st.markdown('<div class="pro-card">', unsafe_allow_html=True)
        st.markdown("#### Jauge de maturité")
        fig_gauge = go.Figure(go.Indicator(
            mode="gauge+number",
            value=maturity,
            number={"suffix": "%"},
            gauge={
                "axis": {"range": [0, 100]},
                "bar": {"color": "#0B2D4D"},
                "steps": [
                    {"range": [0, 50], "color": "#FEE2E2"},
                    {"range": [50, 85], "color": "#FEF3C7"},
                    {"range": [85, 100], "color": "#DCFCE7"},
                ],
            },
            title={"text": "Maturité qualité"},
        ))
        fig_gauge.update_layout(height=390, margin=dict(t=45, b=15, l=10, r=10), paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig_gauge, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="pro-card">', unsafe_allow_html=True)
    st.markdown("#### Avancement OK par chapitre")
    df_m = df_evals.merge(df_master, on="id_point", how="left")
    rows = []
    for chapter, group in df_m.groupby("chap"):
        total_cells = len(group) * 3
        ok_cells = int((group[["jug_agent", "jug_pilote", "jug_qualite"]] == "OK").sum().sum())
        rows.append({"Chapitre": chapter, "Taux OK": (ok_cells / total_cells * 100) if total_cells else 0})
    chap_df = pd.DataFrame(rows)
    fig_chap = px.bar(chap_df, y="Chapitre", x="Taux OK", orientation="h", text="Taux OK", height=max(430, 38 * len(chap_df)))
    fig_chap.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
    fig_chap.update_layout(xaxis_range=[0, 100], margin=dict(t=25, b=20, l=10, r=30), plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig_chap, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="pro-card">', unsafe_allow_html=True)
    st.markdown("#### Plan d'action NOK")
    nok_rows = []
    for _, row in df_m.iterrows():
        for role_name, column in [("Agent Méthodes", "jug_agent"), ("Pilote d'Activité", "jug_pilote"), ("Responsable Qualité", "jug_qualite")]:
            if row.get(column) == "NOK":
                nok_rows.append({"ID": row.get("id_point"), "Chapitre": row.get("chap"), "Critère": row.get("desc"), "Profil": role_name, "Commentaire": " | ".join([str(row.get(c, "")) for c in ["commentaire_agent", "commentaire_pilote", "commentaire_qualite"] if str(row.get(c, "")).strip()])})
    if nok_rows:
        st.dataframe(pd.DataFrame(nok_rows), use_container_width=True, hide_index=True)
    else:
        st.success("Aucun NOK enregistré sur ce cahier.")
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="pro-card">', unsafe_allow_html=True)
    st.markdown("#### Historique de traçabilité")
    if df_trace.empty:
        st.info("Aucune action historisée pour ce cahier.")
    else:
        st.dataframe(df_trace[["created_at", "action", "user_name", "user_role", "details"]], use_container_width=True, hide_index=True)
    st.markdown('</div>', unsafe_allow_html=True)

    def _mpl_to_png(fig):
        buf_img = io.BytesIO()
        fig.savefig(buf_img, format="png", dpi=180, bbox_inches="tight", facecolor="white")
        plt.close(fig)
        buf_img.seek(0)
        return buf_img.read()

    def dashboard_chart_png(title):
        navy = "#0B2D4D"
        red = "#DC2626"
        blue = "#2563EB"
        gray = "#94A3B8"
        green = "#16A34A"

        if title == "Avancement par profil":
            fig, ax = plt.subplots(figsize=(9.2, 4.5))
            x = list(range(len(prof_df)))
            width = 0.18
            series = [("OK", green), ("NOK", red), ("NA", blue), ("Restant", gray)]
            for idx, (col, color) in enumerate(series):
                values = prof_df[col].astype(float).tolist()
                bars = ax.bar([v + (idx - 1.5) * width for v in x], values, width=width, label=col, color=color)
                for bar in bars:
                    height = bar.get_height()
                    ax.text(bar.get_x() + bar.get_width()/2, height + 0.3, f"{int(height)}", ha="center", va="bottom", fontsize=8)
            ax.set_xticks(x)
            ax.set_xticklabels(prof_df["Profil"].tolist(), rotation=0, fontsize=9)
            ax.set_ylabel("Nombre de points")
            ax.set_title("Avancement par profil", fontweight="bold", color=navy)
            ax.grid(axis="y", alpha=0.25)
            ax.legend(ncol=4, loc="upper center", bbox_to_anchor=(0.5, -0.12))
            return _mpl_to_png(fig)

        if title == "Synthèse globale":
            fig, ax = plt.subplots(figsize=(6.8, 4.5))
            values = [total_ok, total_nok, total_na, total_remaining]
            labels = ["OK", "NOK", "NA", "Restant"]
            colors_m = [green, red, blue, gray]
            if sum(values) == 0:
                values = [1]
                labels = ["Aucune donnée"]
                colors_m = [gray]
            ax.pie(values, labels=labels, autopct=lambda p: f"{p:.1f}%" if p > 0 else "", startangle=90, colors=colors_m, textprops={"fontsize": 9})
            centre = plt.Circle((0, 0), 0.55, fc="white")
            ax.add_artist(centre)
            ax.set_title("Synthèse globale", fontweight="bold", color=navy)
            return _mpl_to_png(fig)

        if title == "Jauge de maturité":
            fig, ax = plt.subplots(figsize=(7.8, 2.6))
            ax.barh([0], [100], color="#E2E8F0", height=0.42)
            ax.barh([0], [maturity], color=navy, height=0.42)
            ax.text(min(maturity + 2, 96), 0, f"{maturity:.1f}%", va="center", ha="left", fontsize=16, fontweight="bold", color=navy)
            ax.set_xlim(0, 100)
            ax.set_yticks([])
            ax.set_xlabel("Taux de maturité qualité")
            ax.set_title("Jauge de maturité qualité", fontweight="bold", color=navy)
            ax.grid(axis="x", alpha=0.20)
            for spine in ax.spines.values():
                spine.set_visible(False)
            return _mpl_to_png(fig)

        if title == "Avancement OK par chapitre":
            fig_height = max(4.8, 0.42 * max(1, len(chap_df)))
            fig, ax = plt.subplots(figsize=(10, fig_height))
            plot_df = chap_df.copy().sort_values("Taux OK")
            bars = ax.barh(plot_df["Chapitre"], plot_df["Taux OK"], color=navy)
            ax.set_xlim(0, 100)
            ax.set_xlabel("Taux OK (%)")
            ax.set_title("Avancement OK par chapitre", fontweight="bold", color=navy)
            ax.grid(axis="x", alpha=0.20)
            ax.tick_params(axis='y', labelsize=7)
            for bar in bars:
                width = bar.get_width()
                ax.text(width + 1, bar.get_y() + bar.get_height()/2, f"{width:.1f}%", va="center", fontsize=7)
            return _mpl_to_png(fig)

        return None

    def export_dash_html():
        nok_html = pd.DataFrame(nok_rows).to_html(index=False, escape=True) if nok_rows else "<p>Aucun NOK enregistré.</p>"
        trace_html = df_trace[["created_at", "action", "user_name", "user_role", "details"]].to_html(index=False, escape=True) if not df_trace.empty else "<p>Aucune action historisée.</p>"
        prof_html = prof_df.to_html(index=False, escape=True)
        chap_html = chap_df.to_html(index=False, escape=True)
        return f"""
        <html><head><meta charset='utf-8'>
        <title>Dashboard KPI - {cahier_dashboard}</title>
        <style>
        body{{font-family:Segoe UI,Arial,sans-serif;background:#F5F7FA;color:#0F172A;margin:28px;}}
        .card{{background:white;border:1px solid #D7E0EA;border-radius:14px;padding:18px;margin:16px 0;box-shadow:0 8px 22px rgba(15,23,42,.06);}}
        h1,h2{{color:#0B2D4D;}}
        table{{border-collapse:collapse;width:100%;font-size:12px;}}
        th{{background:#0B2D4D;color:white;text-align:left;}}
        td,th{{border:1px solid #D7E0EA;padding:7px;vertical-align:top;}}
        .kpi{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;}}
        .box{{background:#F8FAFC;border:1px solid #D7E0EA;border-radius:12px;padding:14px;}}
        .value{{font-size:28px;font-weight:900;color:#0B2D4D;}}
        </style></head><body>
        <h1>Dashboard KPI - Cahier {cahier_dashboard}</h1>
        <p>Rapport complet exporté le {now_str()}.</p>
        <div class='kpi'>
          <div class='box'><b>Maturité qualité</b><div class='value'>{maturity:.1f}%</div></div>
          <div class='box'><b>Renseignement global</b><div class='value'>{completion:.1f}%</div></div>
          <div class='box'><b>Total NOK</b><div class='value'>{total_nok}</div></div>
          <div class='box'><b>Restant</b><div class='value'>{total_remaining}</div></div>
        </div>
        <div class='card'><h2>Avancement par profil</h2>{pio.to_html(fig_bar, full_html=False, include_plotlyjs='cdn')}</div>
        <div class='card'><h2>Synthèse globale</h2>{pio.to_html(fig_pie, full_html=False, include_plotlyjs=False)}</div>
        <div class='card'><h2>Jauge de maturité</h2>{pio.to_html(fig_gauge, full_html=False, include_plotlyjs=False)}</div>
        <div class='card'><h2>Avancement OK par chapitre</h2>{pio.to_html(fig_chap, full_html=False, include_plotlyjs=False)}</div>
        <div class='card'><h2>Détail par profil</h2>{prof_html}</div>
        <div class='card'><h2>Détail par chapitre</h2>{chap_html}</div>
        <div class='card'><h2>Plan d'action NOK</h2>{nok_html}</div>
        <div class='card'><h2>Historique de traçabilité</h2>{trace_html}</div>
        </body></html>
        """.encode("utf-8")

    def export_dash_pdf():
        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=landscape(letter), leftMargin=22, rightMargin=22, topMargin=22, bottomMargin=22)
        story = []
        styles = getSampleStyleSheet()
        story.append(Paragraph(f"RAPPORT KPI COMPLET - CAHIER : {cahier_dashboard}", styles["Heading1"]))
        story.append(Paragraph(f"Export généré le {now_str()}", styles["Normal"]))
        story.append(Spacer(1, 12))
        data = [["Indicateur", "Valeur"], ["Maturité qualité", f"{maturity:.1f}%"], ["Renseignement global", f"{completion:.1f}%"], ["OK", str(total_ok)], ["NOK", str(total_nok)], ["NA", str(total_na)], ["Restant", str(total_remaining)]]
        table = Table(data, colWidths=[260, 160])
        table.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,0), colors.HexColor("#0B2D4D")), ("TEXTCOLOR", (0,0), (-1,0), colors.white), ("GRID", (0,0), (-1,-1), 1, colors.HexColor("#CBD5E1")), ("PADDING", (0,0), (-1,-1), 8), ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold")]))
        story.append(table)
        story.append(Spacer(1, 14))
        for title in ["Avancement par profil", "Synthèse globale", "Jauge de maturité", "Avancement OK par chapitre"]:
            story.append(Paragraph(title, styles["Heading2"]))
            img = dashboard_chart_png(title)
            if img:
                if title == "Avancement OK par chapitre":
                    story.append(Image(io.BytesIO(img), width=9.1*inch, height=4.4*inch))
                else:
                    story.append(Image(io.BytesIO(img), width=7.6*inch, height=3.7*inch))
            story.append(Spacer(1, 10))
        story.append(PageBreak())
        story.append(Paragraph("Détail par profil", styles["Heading2"]))
        prof_table_data = [["Profil", "OK", "NOK", "NA", "Restant"]] + prof_df.astype(str).values.tolist()
        prof_table = Table(prof_table_data, colWidths=[170, 70, 70, 70, 90])
        prof_table.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,0), colors.HexColor("#0B2D4D")), ("TEXTCOLOR", (0,0), (-1,0), colors.white), ("GRID", (0,0), (-1,-1), .5, colors.HexColor("#CBD5E1")), ("PADDING", (0,0), (-1,-1), 6)]))
        story.append(prof_table)
        story.append(Spacer(1, 14))
        story.append(Paragraph("Plan d'action NOK", styles["Heading2"]))
        if nok_rows:
            nok_data = [["ID", "Chapitre", "Critère", "Profil", "Commentaire"]]
            for r in nok_rows[:80]:
                nok_data.append([str(r.get("ID", "")), Paragraph(str(r.get("Chapitre", "")), styles["BodyText"]), Paragraph(str(r.get("Critère", "")), styles["BodyText"]), str(r.get("Profil", "")), Paragraph(str(r.get("Commentaire", "")), styles["BodyText"])])
            nt = Table(nok_data, colWidths=[40, 140, 250, 100, 210], repeatRows=1)
            nt.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,0), colors.HexColor("#0B2D4D")), ("TEXTCOLOR", (0,0), (-1,0), colors.white), ("GRID", (0,0), (-1,-1), .35, colors.HexColor("#CBD5E1")), ("VALIGN", (0,0), (-1,-1), "TOP"), ("FONTSIZE", (0,0), (-1,-1), 7)]))
            story.append(nt)
        else:
            story.append(Paragraph("Aucun NOK enregistré sur ce cahier.", styles["Normal"]))
        story.append(Spacer(1, 14))
        story.append(Paragraph("Historique de traçabilité", styles["Heading2"]))
        if not df_trace.empty:
            tr_data = [["Date", "Action", "Utilisateur", "Profil", "Détails"]]
            for _, r in df_trace.head(30).iterrows():
                tr_data.append([str(r.get("created_at", "")), str(r.get("action", "")), str(r.get("user_name", "")), str(r.get("user_role", "")), Paragraph(str(r.get("details", "")), styles["BodyText"])])
            tt = Table(tr_data, colWidths=[110, 120, 120, 110, 270], repeatRows=1)
            tt.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,0), colors.HexColor("#0B2D4D")), ("TEXTCOLOR", (0,0), (-1,0), colors.white), ("GRID", (0,0), (-1,-1), .35, colors.HexColor("#CBD5E1")), ("VALIGN", (0,0), (-1,-1), "TOP"), ("FONTSIZE", (0,0), (-1,-1), 7)]))
            story.append(tt)
        else:
            story.append(Paragraph("Aucune action historisée pour ce cahier.", styles["Normal"]))
        doc.build(story)
        buf.seek(0)
        return buf

    st.markdown('<div class="download-zone"><b>Exports complets du dashboard</b><br><span style="color:#64748B;font-size:13px;">Téléchargement du rapport complet avec indicateurs, graphes, plan d’action NOK et historique de traçabilité.</span></div>', unsafe_allow_html=True)
    e1, e2 = st.columns(2)
    with e1:
        st.download_button("Télécharger toute la page dashboard HTML", data=export_dash_html(), file_name=f"Dashboard_Complet_{cahier_dashboard}.html", mime="text/html", use_container_width=True)
    with e2:
        st.download_button("Télécharger le dashboard PDF complet", data=export_dash_pdf(), file_name=f"Dashboard_Complet_{cahier_dashboard}.pdf", mime="application/pdf", use_container_width=True)

# ==============================================================================
# ROUTEUR
# ==============================================================================
if "app_state" not in st.session_state:
    st.session_state["app_state"] = "LOGIN"

approve_token = get_query_param("approve_token")
if approve_token:
    render_approval_page(approve_token)

apply_global_style()

if st.session_state.get("app_state") == "LOGIN":
    render_login_page()
elif st.session_state.get("app_state") == "HOME":
    render_home_page()
elif st.session_state.get("app_state") == "WORKSPACE":
    render_workspace_page()
elif st.session_state.get("app_state") == "DASHBOARD":
    render_dashboard_page()
else:
    st.session_state["app_state"] = "LOGIN"
    st.rerun()
