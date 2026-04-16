from datetime import datetime
from extensions import db


class Token(db.Model):
    __tablename__ = "tokens"

    id         = db.Column(db.Integer, primary_key=True, autoincrement=True)
    created_at = db.Column(db.Date, default=datetime.utcnow)
    token      = db.Column(db.Text, nullable=False)
    revoked_is = db.Column(db.Integer, default=0)   # 0 = active, 1 = revoked
    user_id    = db.Column(db.Integer, nullable=False)

    def to_dict(self):
        return {
            "id":         self.id,
            "created_at": str(self.created_at),
            "token":      self.token,
            "revoked_is": self.revoked_is,
            "user_id":    self.user_id,
        }
