from extensions import db


class User(db.Model):
    __tablename__ = "user"
    id       = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role     = db.Column(db.String(20), default="user")


class Job(db.Model):
    __tablename__ = "job"
    id          = db.Column(db.Integer, primary_key=True)
    title       = db.Column(db.String(100))
    description = db.Column(db.Text, nullable=False)


class AnalysisRecord(db.Model):
    __tablename__ = "analysis_record"
    id             = db.Column(db.Integer, primary_key=True)
    user_id        = db.Column(db.Integer, db.ForeignKey("user.id"))
    job_id         = db.Column(db.Integer, db.ForeignKey("job.id"))
    filename       = db.Column(db.String(200))
    score          = db.Column(db.Float)
    matched_skills = db.Column(db.Text)
    missing_skills = db.Column(db.Text)
    status         = db.Column(db.String(20))
    timestamp      = db.Column(db.DateTime, default=db.func.current_timestamp())
