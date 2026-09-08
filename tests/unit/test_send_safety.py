from src.domain.email_draft import EmailDraft
from src.domain.send_safety import SendPolicy, check_send_safety


def draft(status=None):
    item = EmailDraft.create(
        "task-1", "alpine.example", "sales@alpine.example",
        "Subject", "Body", ("https://alpine.example",)
    )
    return item if status is None else item.__class__(**{**item.__dict__, "status": status})


def test_unapproved_draft_is_blocked_even_with_valid_recipient():
    result = check_send_safety(draft(), SendPolicy())

    assert not result.allowed
    assert "approved" in result.reasons[0]
    assert result.requires_manual_confirmation


def test_approved_draft_is_blocked_by_domain_and_daily_limit():
    from src.domain.email_draft import EmailDraftStatus

    result = check_send_safety(
        draft(EmailDraftStatus.APPROVED),
        SendPolicy(blocked_domains=("alpine.example",), daily_limit=5, sent_today=5),
    )

    assert not result.allowed
    assert len(result.reasons) == 2
    assert result.requires_manual_confirmation


def test_allowed_result_still_requires_manual_confirmation_and_does_not_send():
    from src.domain.email_draft import EmailDraftStatus

    result = check_send_safety(draft(EmailDraftStatus.APPROVED), SendPolicy())

    assert result.allowed
    assert result.requires_manual_confirmation


def test_recent_contact_and_unsafe_attachments_are_blocked():
    from src.domain.email_draft import EmailDraftStatus

    result = check_send_safety(
        draft(EmailDraftStatus.APPROVED),
        SendPolicy(
            contacted_recently=True,
            attachment_names=("../secrets.txt", "catalog.pdf", "price.xlsx"),
            max_attachments=2,
        ),
    )

    assert not result.allowed
    assert "recipient was contacted recently" in result.reasons
    assert "attachment count" in result.reasons[1]
    assert any("secrets.txt" in reason for reason in result.reasons)


def test_attachment_size_limits_are_checked_without_opening_files():
    from src.domain.email_draft import EmailDraftStatus

    result = check_send_safety(
        draft(EmailDraftStatus.APPROVED),
        SendPolicy(
            attachment_sizes=(("catalog.pdf", 11), ("price.xlsx", 9)),
            max_attachment_bytes=10,
            max_total_attachment_bytes=15,
        ),
    )

    assert not result.allowed
    assert "attachment is too large: catalog.pdf" in result.reasons
    assert "total attachment size" in result.reasons[-1]
