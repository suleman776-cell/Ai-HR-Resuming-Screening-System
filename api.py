"""
api.py — Protected API routes blueprint
All routes here are automatically guarded by middleware_login.py.
g.user_ctx is always available (user_id, username, role).
"""
import json, uuid, os
from flask import Blueprint, request, jsonify, g, current_app
from werkzeug.utils import secure_filename

from extensions import db
from models import Job, AnalysisRecord

api_bp = Blueprint("api_bp", __name__, url_prefix="/api")


# ── Jobs ──────────────────────────────────────────────────────────────────────

@api_bp.route("/jobs", methods=["GET"])
def get_jobs():
    """List all jobs. Any authenticated user."""
    jobs = Job.query.all()
    return jsonify([
        {"id": j.id, "title": j.title, "description": j.description}
        for j in jobs
    ]), 200


@api_bp.route("/jobs", methods=["POST"])
def create_job():
    """Create a job. Admin only."""
    ctx = g.user_ctx
    if not ctx.is_admin():
        return jsonify({"error": "Admin role required"}), 403

    data        = request.get_json(silent=True) or {}
    title       = (data.get("title") or "").strip()
    description = (data.get("description") or "").strip()

    if not title or not description:
        return jsonify({"error": "title and description are required"}), 400

    job = Job(title=title, description=description)
    db.session.add(job)
    db.session.commit()
    return jsonify({"id": job.id, "title": job.title, "description": job.description}), 201


# ── Records ───────────────────────────────────────────────────────────────────

@api_bp.route("/records", methods=["GET"])
def get_records():
    """
    Admin → all records sorted by score desc.
    User  → only their own records.
    """
    ctx = g.user_ctx
    if ctx.is_admin():
        records = AnalysisRecord.query.order_by(AnalysisRecord.score.desc()).all()
    else:
        records = AnalysisRecord.query.filter_by(user_id=ctx.user_id).all()

    return jsonify([{
        "id":             r.id,
        "user_id":        r.user_id,
        "job_id":         r.job_id,
        "filename":       r.filename,
        "score":          r.score,
        "matched_skills": json.loads(r.matched_skills) if r.matched_skills else [],
        "missing_skills": json.loads(r.missing_skills) if r.missing_skills else [],
        "status":         r.status,
        "timestamp":      str(r.timestamp),
    } for r in records]), 200


# ── Analyze ───────────────────────────────────────────────────────────────────

@api_bp.route("/analyze", methods=["POST"])
def analyze():
    """
    Upload a resume (.docx / .pdf) and score it against a job.
    Multipart form fields: resume (file), job_id (int).
    """
    from app import vectorizer, AI_READY, extract_text, get_skills_analysis
    from sklearn.metrics.pairwise import cosine_similarity

    ctx = g.user_ctx

    if not AI_READY:
        return jsonify({"error": "AI vectorizer not available"}), 503

    job_id = request.form.get("job_id")
    file   = request.files.get("resume")

    if not file or not job_id:
        return jsonify({"error": "resume file and job_id are required"}), 400

    job = Job.query.get(int(job_id))
    if not job:
        return jsonify({"error": f"Job {job_id} not found"}), 404

    upload_folder = current_app.config["UPLOAD_FOLDER"]
    filename  = f"{uuid.uuid4().hex[:8]}_{secure_filename(file.filename)}"
    filepath  = os.path.join(upload_folder, filename)
    file.save(filepath)

    resume_text = extract_text(filepath)
    if not resume_text:
        return jsonify({"error": "Could not extract text from the uploaded file"}), 422

    jd_text   = job.description
    vec_sim   = cosine_similarity(
        vectorizer.transform([jd_text.lower()]),
        vectorizer.transform([resume_text.lower()])
    )[0][0] * 100

    matched, missing = get_skills_analysis(resume_text, jd_text)
    skill_score  = (len(matched) / (len(matched) + len(missing)) * 100) \
                   if (len(matched) + len(missing)) > 0 else 0
    final_score  = round((0.7 * vec_sim) + (0.3 * skill_score), 2)

    record = AnalysisRecord(
        user_id        = ctx.user_id,
        job_id         = job.id,
        filename       = filename,
        score          = final_score,
        matched_skills = json.dumps(matched),
        missing_skills = json.dumps(missing),
        status         = "analyzed",
    )
    db.session.add(record)
    db.session.commit()

    return jsonify({
        "record_id":      record.id,
        "filename":       filename,
        "score":          final_score,
        "matched_skills": matched,
        "missing_skills": missing,
        "analyzed_by":    {"user_id": ctx.user_id, "username": ctx.username},
    }), 201
