import pytest

from src.application.email_draft_service import EmailDraftService
from src.domain.email_draft import EmailDraftStatus
from src.domain.lead import CleanLead
from src.domain.research import CustomerType, EvidenceStatus, ResearchResult
from src.domain.sender_profile import SenderProfile


class FakeProvider:
    def __init__(self, payload):
        self.payload = payload
        self.prompts = []

    def generate_json(self, prompt):
        self.prompts.append(prompt)
        return self.payload


def sample_lead():
    return CleanLead(
        "Alpine Energy",
        "alpine.example",
        ("sales@alpine.example",),
        "Germany",
        "complete",
    )


def sample_research():
    return ResearchResult(
        "Alpine Energy",
        "An online seller of portable power stations.",
        CustomerType.RETAILER,
        ("portable power stations",),
        "Germany",
        0.9,
        "https://alpine.example/about",
        EvidenceStatus.SUFFICIENT,
    )


def test_generate_draft_uses_configured_template_and_requires_review():
    provider = FakeProvider({"subject": "Portable power for Alpine", "body": "Hello Alpine team."})
    service = EmailDraftService(provider)

    draft = service.generate(
        task_id="task-1",
        lead=sample_lead(),
        research=sample_research(),
        template="Introduce {product} to {company}. Keep it concise.",
        product="portable power stations",
    )

    assert draft.status is EmailDraftStatus.PENDING_REVIEW
    assert draft.recipient_email == "sales@alpine.example"
    assert draft.subject == "Portable power for Alpine"
    assert draft.evidence_urls == ("https://alpine.example/about",)
    assert "Introduce portable power stations to Alpine Energy" in provider.prompts[0]
    assert "The recipient company is not the sender" in provider.prompts[0]


def test_generate_draft_uses_configured_sender_profile():
    provider = FakeProvider({
        "subject": "Connect with [Your Company]",
        "body": "Hello from [Our Company]. I am [Your Name], [Your Position].",
    })

    draft = EmailDraftService(provider).generate(
        "task-1", sample_lead(), sample_research(), "Hello {company}", "product",
        SenderProfile("Northstar Trading", "Li Ming", "Sales Manager"),
    )

    assert "Sender company: Northstar Trading" in provider.prompts[0]
    assert "Sender name: Li Ming" in provider.prompts[0]
    assert "Sender position: Sales Manager" in provider.prompts[0]
    assert draft.subject == "Connect with Northstar Trading"
    assert draft.body == "Hello from Northstar Trading. I am Li Ming, Sales Manager."


def test_generate_draft_rejects_missing_recipient():
    provider = FakeProvider({"subject": "Subject", "body": "Body"})
    service = EmailDraftService(provider)
    lead = CleanLead("Alpine Energy", "alpine.example", (), "Germany", "needs_review")

    with pytest.raises(ValueError, match="recipient email"):
        service.generate("task-1", lead, sample_research(), "Hello {company}", "product")


def test_draft_approval_is_separate_from_sending():
    provider = FakeProvider({"subject": "Subject", "body": "Body"})
    draft = EmailDraftService(provider).generate(
        "task-1", sample_lead(), sample_research(), "Hello {company}", "product"
    )

    approved = draft.approve("reviewer-1")

    assert approved.status is EmailDraftStatus.APPROVED
    assert approved.reviewed_by == "reviewer-1"
    assert not hasattr(approved, "sent_at")
