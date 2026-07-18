"""
Status constants and data helpers for the content pipeline.
No ORM — uses plain dicts from SQLite rows.
"""


class Status:
    """All valid statuses for a content_item record."""

    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    GENERATING_CONTENT = "generating_content"
    GENERATING_IMAGE = "generating_image"
    PREVIEW_PENDING = "preview_pending"
    PUBLISHING = "publishing"
    PUBLISHED = "published"
    FAILED = "failed"

    # Statuses that require admin action (approve/reject buttons shown)
    ACTIONABLE = {PENDING_APPROVAL, PREVIEW_PENDING}

    # All valid statuses for CHECK constraint
    ALL = {
        PENDING_APPROVAL,
        APPROVED,
        REJECTED,
        GENERATING_CONTENT,
        GENERATING_IMAGE,
        PREVIEW_PENDING,
        PUBLISHING,
        PUBLISHED,
        FAILED,
    }

    # Human-readable labels for the UI
    LABELS = {
        PENDING_APPROVAL: "Pending Approval",
        APPROVED: "Approved",
        REJECTED: "Rejected",
        GENERATING_CONTENT: "Generating Content",
        GENERATING_IMAGE: "Generating Image",
        PREVIEW_PENDING: "Preview Pending",
        PUBLISHING: "Publishing",
        PUBLISHED: "Published",
        FAILED: "Failed",
    }


def content_item_from_row(row) -> dict:
    """Convert a sqlite3.Row to a plain dict."""
    if row is None:
        return None
    return dict(row)


def format_status(status: str) -> str:
    """Return a human-readable label for a status value."""
    return Status.LABELS.get(status, status.replace("_", " ").title())
