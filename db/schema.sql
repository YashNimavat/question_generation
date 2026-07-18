CREATE TABLE IF NOT EXISTS metadata_logs (
    id TEXT PRIMARY KEY,
    operation_type TEXT NOT NULL,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    prompt_version TEXT,
    input_tokens INTEGER NOT NULL,
    output_tokens INTEGER NOT NULL,
    latency_ms REAL NOT NULL,
    cost_usd REAL NOT NULL,
    rag_usage TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    original_filename TEXT NOT NULL,
    status TEXT NOT NULL,
    chunk_count INTEGER NOT NULL DEFAULT 0,
    topic TEXT,
    tags TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS questions (
    id TEXT NOT NULL,
    version INTEGER NOT NULL,
    type TEXT NOT NULL,
    status TEXT NOT NULL,
    stem TEXT NOT NULL,
    payload TEXT NOT NULL,
    difficulty TEXT NOT NULL,
    topic TEXT NOT NULL,
    tags TEXT NOT NULL DEFAULT '[]',
    source TEXT NOT NULL,
    document_id TEXT,
    parent_id TEXT,
    parent_version INTEGER,
    generation_metadata_id TEXT,
    duplicate_of_id TEXT,
    duplicate_of_version INTEGER,
    duplicate_score REAL,
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (id, version),
    FOREIGN KEY (document_id) REFERENCES documents (id),
    FOREIGN KEY (generation_metadata_id) REFERENCES metadata_logs (id)
);

CREATE INDEX IF NOT EXISTS idx_questions_topic_status ON questions (topic, status);
CREATE INDEX IF NOT EXISTS idx_questions_id ON questions (id);

CREATE TABLE IF NOT EXISTS evaluations (
    id TEXT PRIMARY KEY,
    question_id TEXT NOT NULL,
    question_version INTEGER NOT NULL,
    rubric_id TEXT NOT NULL,
    rubric_version TEXT NOT NULL,
    scores TEXT NOT NULL,
    overall_verdict TEXT NOT NULL,
    reference_answer_used INTEGER NOT NULL DEFAULT 0,
    metadata_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (question_id, question_version) REFERENCES questions (id, version),
    FOREIGN KEY (metadata_id) REFERENCES metadata_logs (id)
);

CREATE INDEX IF NOT EXISTS idx_evaluations_question ON evaluations (question_id, question_version);

CREATE TABLE IF NOT EXISTS reviews (
    id TEXT PRIMARY KEY,
    question_id TEXT NOT NULL,
    question_version INTEGER NOT NULL,
    reviewer_id TEXT NOT NULL,
    decision TEXT NOT NULL,
    reason_category TEXT,
    comment TEXT,
    severity TEXT,
    linked_new_version INTEGER,
    created_at TEXT NOT NULL,
    FOREIGN KEY (question_id, question_version) REFERENCES questions (id, version)
);

CREATE INDEX IF NOT EXISTS idx_reviews_question ON reviews (question_id, question_version);
CREATE INDEX IF NOT EXISTS idx_reviews_reviewer ON reviews (reviewer_id);

CREATE TABLE IF NOT EXISTS experiments (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    hypothesis TEXT NOT NULL,
    variants TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS experiment_runs (
    id TEXT PRIMARY KEY,
    experiment_id TEXT NOT NULL,
    variant_key TEXT NOT NULL,
    question_id TEXT NOT NULL,
    question_version INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (experiment_id) REFERENCES experiments (id),
    FOREIGN KEY (question_id, question_version) REFERENCES questions (id, version)
);

CREATE INDEX IF NOT EXISTS idx_experiment_runs_experiment ON experiment_runs (experiment_id);
