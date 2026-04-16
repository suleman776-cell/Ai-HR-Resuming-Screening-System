from flask_sqlalchemy import SQLAlchemy

# Single shared db instance imported by both app.py and blueprints
db = SQLAlchemy()
