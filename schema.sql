-- Schema for recruiter_enterprise.db
-- SQLite

CREATE TABLE IF NOT EXISTS user (
    id       INTEGER      NOT NULL PRIMARY KEY,
    username VARCHAR(80),
    password VARCHAR(200),
    role     VARCHAR(20)
);

CREATE TABLE IF NOT EXISTS job (
    id          INTEGER      NOT NULL PRIMARY KEY,
    title       VARCHAR(100) NOT NULL,
    description TEXT         NOT NULL
);

CREATE TABLE IF NOT EXISTS analysis_record (
    id             INTEGER      NOT NULL PRIMARY KEY,
    user_id        INTEGER,
    job_id         INTEGER,
    filename       VARCHAR(200),
    score          FLOAT,
    matched_skills TEXT,
    missing_skills TEXT,
    status         VARCHAR(20),
    timestamp      DATETIME,
    FOREIGN KEY (user_id) REFERENCES user(id),
    FOREIGN KEY (job_id)  REFERENCES job(id)
);

CREATE TABLE IF NOT EXISTS tokens (
    created_at date,
    token text,
    revoked_is integer,
    user_id integer
);