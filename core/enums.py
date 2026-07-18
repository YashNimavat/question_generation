from enum import StrEnum


class QuestionType(StrEnum):
    MCQ = "mcq"
    TRUE_FALSE = "true_false"
    FILL_BLANK = "fill_blank"


class QuestionStatus(StrEnum):
    GENERATED = "generated"
    AUTO_EVALUATED = "auto_evaluated"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    EDITED = "edited"


class Source(StrEnum):
    TOPIC = "topic"
    DOCUMENT = "document"


class ReviewDecision(StrEnum):
    APPROVE = "approve"
    REJECT = "reject"
    EDIT = "edit"


class ReasonCategory(StrEnum):
    FACTUALLY_INCORRECT = "factually_incorrect"
    AMBIGUOUS_WORDING = "ambiguous_wording"
    WEAK_DISTRACTORS = "weak_distractors"
    ANSWER_KEY_ERROR = "answer_key_error"
    DUPLICATE = "duplicate"
    OFF_TOPIC = "off_topic"
    DIFFICULTY_MISMATCH = "difficulty_mismatch"
    FORMATTING_ISSUE = "formatting_issue"
    OTHER = "other"


class Severity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class DocumentStatus(StrEnum):
    INGESTED = "ingested"
    CHUNKED = "chunked"
    EMBEDDED = "embedded"
    READY = "ready"
    FAILED = "failed"


class OverallVerdict(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    NEEDS_REVIEW = "needs_review"


class ExperimentStatus(StrEnum):
    RUNNING = "running"
    COMPLETE = "complete"


class OperationType(StrEnum):
    GENERATION = "generation"
    EVALUATION = "evaluation"
    EMBEDDING = "embedding"
