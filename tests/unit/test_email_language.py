from src.application.email_draft_service import EmailDraftService
from src.domain.email_language import detect_reply_language, resolve_language
from src.domain.lead import CleanLead
from src.domain.research import CustomerType, EvidenceStatus, ResearchResult


class Provider:
    def __init__(self):
        self.prompt = ""

    def generate_json(self, prompt):
        self.prompt = prompt
        return {"subject": "Subject", "body": "Body"}


def research(country="Germany", website_language="unknown"):
    return ResearchResult(
        "Alpine", "A retailer", CustomerType.RETAILER, ("power stations",),
        country, 0.9, "https://alpine.example", EvidenceStatus.SUFFICIENT,
        website_language,
    )


def test_explicit_language_wins_over_market_defaults():
    decision = resolve_language("Spanish", "Germany", "German", {"Germany": "German"})
    assert decision.language == "Spanish"
    assert decision.source == "task configuration"
    assert not decision.requires_review


def test_website_language_wins_over_country():
    decision = resolve_language("auto", "Germany", "Spanish", {"Germany": "German"})
    assert decision.language == "Spanish"
    assert decision.source == "website language"


def test_unknown_market_falls_back_to_english_and_requires_review():
    decision = resolve_language("auto", "Switzerland", "unknown", {})
    assert decision.language == "English"
    assert decision.requires_review


def test_outreach_prompt_contains_resolved_language_and_metadata():
    provider = Provider()
    draft = EmailDraftService(provider).generate(
        "task-1", CleanLead("Alpine", "alpine.example", ("sales@alpine.example",), "Germany", "complete"),
        research(website_language="German"), "Introduce {product} to {company}", "power stations",
    )
    assert draft.language == "German"
    assert draft.language_source == "website language"
    assert "in German" in provider.prompt


def test_reply_language_detector_handles_cyrillic_and_chinese():
    assert detect_reply_language("Здравствуйте, спасибо за письмо") == "Russian"
    assert detect_reply_language("您好，感谢您的邮件") == "Chinese"
