from src.domain.email_draft import EmailDraft, EmailDraftStatus
from src.infrastructure.sqlite_repositories import SQLiteEmailDraftRepository


def test_email_draft_survives_repository_recreation(tmp_path):
    database = tmp_path / "drafts.db"
    draft = EmailDraft(
        id="draft-1",
        task_id="task-1",
        lead_domain="alpine.example",
        recipient_email="sales@alpine.example",
        subject="Portable power",
        body="Hello Alpine team.",
        evidence_urls=("https://alpine.example/about",),
    ).approve("reviewer-1")

    SQLiteEmailDraftRepository(database).save(draft)
    restored = SQLiteEmailDraftRepository(database).get(draft.id)

    assert restored == draft
    assert restored.status is EmailDraftStatus.APPROVED
