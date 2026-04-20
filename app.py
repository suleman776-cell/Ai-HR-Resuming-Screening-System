import os, json, uuid, re
import pdfplumber
import docx2txt
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file, jsonify, g
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from joblib import load
from sklearn.metrics.pairwise import cosine_similarity
from flask_swagger_ui import get_swaggerui_blueprint
from flask_cors import CORS

from extensions import db
from models import User, Job, AnalysisRecord
from login import login_bp
from api import api_bp
from middleware_login import jwt_middleware

app = Flask(__name__)
# 32-byte key — satisfies PyJWT's minimum for HS256
app.secret_key = "enterprise_access_key_2026_secure"
app.config['SECRET_KEY'] = app.secret_key

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(BASE_DIR, "recruiter_enterprise.db")}'
app.config['UPLOAD_FOLDER'] = os.path.join(BASE_DIR, 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

db.init_app(app)

# ── CORS ──────────────────────────────────────────────────────────────────────
CORS(app, resources={r"/api/*": {"origins": "*"}},
     supports_credentials=False,
     allow_headers=["Content-Type", "Authorization"],
     methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"])

# ── JWT middleware (guards all /api/* except /api/login) ─────────────────────
app.before_request(jwt_middleware)

# ── Swagger UI at /docs ───────────────────────────────────────────────────────
swaggerui_bp = get_swaggerui_blueprint(
    "/docs",
    "/static/openapi.json",
    config={"app_name": "AI HR Recruiter API"},
)
app.register_blueprint(swaggerui_bp)

@app.route("/static/openapi.json")
def openapi_spec():
    return send_file(os.path.join(BASE_DIR, "static", "openapi.json"),
                     mimetype="application/json")

# ── Blueprints ────────────────────────────────────────────────────────────────
app.register_blueprint(login_bp)   # /api/login, /api/me
app.register_blueprint(api_bp)     # /api/jobs, /api/records, /api/analyze

if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

# ── ML vectorizer ─────────────────────────────────────────────────────────────
SKILL_DB = ['python', 'flask', 'django', 'react', 'node.js', 'aws', 'docker',
            'kubernetes', 'sql', 'mongodb', 'git', 'java', 'javascript', 'html', 'css']

try:
    vectorizer = load(os.path.join(BASE_DIR, "resume_vectorizer.joblib"))
    AI_READY = True
except Exception:
    vectorizer = None
    AI_READY = False

# ── Helpers (used by api.py via import) ───────────────────────────────────────
def extract_text(file_path):
    try:
        if file_path.endswith('.pdf'):
            with pdfplumber.open(file_path) as pdf:
                return " ".join([p.extract_text() for p in pdf.pages if p.extract_text()])
        elif file_path.endswith('.docx'):
            return docx2txt.process(file_path)
    except Exception:
        return ""
    return ""

def get_skills_analysis(text, jd_text):
    text, jd_text = text.lower(), jd_text.lower()
    jd_skills  = set(s for s in SKILL_DB if re.search(r'\b' + re.escape(s) + r'\b', jd_text))
    res_skills = set(s for s in SKILL_DB if re.search(r'\b' + re.escape(s) + r'\b', text))
    return list(res_skills & jd_skills), list(jd_skills - res_skills)

@app.template_filter('from_json')
def from_json_filter(value):
    try:
        return json.loads(value) if value else []
    except Exception:
        return []

# ── Web routes (HTML browser UI) ──────────────────────────────────────────────
@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        u = request.form.get('username').strip()
        p = request.form.get('password')
        if User.query.filter_by(username=u).first():
            flash("User exists", "danger")
        else:
            db.session.add(User(username=u, password=generate_password_hash(p)))
            db.session.commit()
            return redirect(url_for('login'))
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        u = request.form.get('username')
        p = request.form.get('password')
        user = User.query.filter_by(username=u).first()
        if user and check_password_hash(user.password, p):
            session.update({'user': user.username, 'role': user.role, 'user_id': user.id})
            if user.role == 'admin':
                return redirect(url_for('admin_dashboard'))
            return redirect(url_for('candidate_dashboard'))
        flash("Invalid credentials", "danger")
    return render_template('login.html')

@app.route('/admin')
def admin_dashboard():
    """Serve the admin dashboard HTML — JS handles auth via localStorage token."""
    return render_template('admindashboard.html')

@app.route('/candidate')
def candidate_dashboard():
    """Serve the candidate dashboard HTML — JS handles auth via localStorage token."""
    return render_template('Candidate.html')

@app.route('/dashboard')
def dashboard():
    """Legacy route — JS will redirect based on role after token check."""
    return redirect(url_for('login'))

@app.route('/download/<int:record_id>')
def download(record_id):
    if 'user' not in session:
        return redirect(url_for('login'))
    record = AnalysisRecord.query.get_or_404(record_id)
    if session['role'] != 'admin' and record.user_id != session['user_id']:
        return redirect(url_for('candidate_dashboard'))
    return send_file(os.path.join(app.config['UPLOAD_FOLDER'], record.filename),
                     as_attachment=True)

@app.route('/logout')
def logout():
    session.clear()
    # Return a page that clears localStorage then redirects — avoids loop
    return '''<!DOCTYPE html>
<html><head><title>Logging out…</title></head>
<body>
<script>
    localStorage.removeItem("jwt_token");
    localStorage.removeItem("jwt_user");
    window.location.replace("/login");
</script>
</body></html>'''

if __name__ == '__main__':
    with app.app_context():
        from login_model import Token
        db.create_all()
    app.run(debug=True)
