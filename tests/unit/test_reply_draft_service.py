from src.application.reply_analysis import classify_inbound
from src.application.reply_draft_service import ReplyDraftService
from src.domain.inbound_email import InboundEmail
from src.domain.lead import CleanLead
from src.domain.research import CustomerType, EvidenceStatus, ResearchResult


class Provider:
    def __init__(self):
        self.prompt = ""

    def generate_json(self, prompt):
        self.prompt = prompt
        return {"subject": "Re: Product catalogue", "body": "Thank you for your message."}


def make_context():
    message = InboundEmail.create(
        "1", "<reply@example>", "", (), "buyer@alpine.example", ("seller@example.com",),
        "Re: catalogue", "Please send your catalogue.",
        "2026-09-09T10:00:00+00:00", "task-1", "alpine.example",
    )
    analysis = classify_inbound(message)
    lead = CleanLead("Alpine", "alpine.example", ("buyer@alpine.example",), "DE", "high")
    research = ResearchResult(
        "Alpine", "Outdoor equipment retailer", CustomerType.RETAILER,
        ("solar generators",), "Germany", 0.9, "https://alpine.example", EvidenceStatus.SUFFICIENT,
    )
    return message, analysis, lead, research


def test_reply_draft_uses_customer_email_and_requires_review():
    provider = Provider()
    message, analysis, lead, research = make_context()

    draft = ReplyDraftService(provider).generate(message, analysis, lead, research)

    assert draft.recipient_email == "buyer@alpine.example"
    assert draft.status.value == "pending_review"
    assert "Do not invent" in provider.prompt


def test_reply_draft_rejects_system_notification():
    message, analysis, lead, research = make_context()
    system_message = InboundEmail(
        **{**message.__dict__, "from_email": "no-reply@mailsupport.aliyun.com"}
    )

    try:
        ReplyDraftService(Provider()).generate(system_message, analysis, lead, research)
    except ValueError as error:
        assert "system notifications" in str(error)
    else:
        raise AssertionError("system notifications must not produce drafts")
