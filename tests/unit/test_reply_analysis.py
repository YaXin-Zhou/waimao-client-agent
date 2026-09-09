from src.application.reply_analysis import classify_inbound
from src.application.reply_analysis_service import ReplyAnalysisService
from src.domain.inbound_email import InboundEmail
from src.domain.reply_analysis import ReplyCategory


def make_message(subject, body, bounce=False):
    message = InboundEmail.create(
        "1", "<message@example>", "", (), "buyer@alpine.example", ("seller@example.com",),
        subject, body, "2026-09-08T10:00:00+00:00", "task-1", "alpine.example"
    )
    return message if not bounce else InboundEmail(
        **{**message.__dict__, "is_bounce": True}
    )


def test_pricing_reply_gets_safe_human_confirmed_suggestion():
    analysis = classify_inbound(make_message("Re: quote", "Please send your price list."))

    assert analysis.category is ReplyCategory.PRICING
    assert analysis.confidence > 0.9
    assert not analysis.needs_human_review
    assert "人工确认" in analysis.suggested_action


def test_bounce_reply_is_high_risk_and_requires_human_review():
    analysis = classify_inbound(make_message("Mail delivery failed", "Undeliverable", True))

    assert analysis.category is ReplyCategory.BOUNCE
    assert analysis.risk_level == "high"
    assert analysis.needs_human_review


def test_multilingual_pricing_and_complaint_are_classified_without_model():
    pricing = classify_inbound(make_message("Re: Angebot", "Bitte senden Sie Ihren Preis."))
    complaint = classify_inbound(make_message("Réclamation", "Nous demandons un refund."))

    assert pricing.category is ReplyCategory.PRICING
    assert complaint.category is ReplyCategory.COMPLAINT
    assert complaint.needs_human_review


def test_system_notification_is_not_classified_as_customer_reply():
    message = InboundEmail.create(
        "2", "<welcome@example>", "", (), "no-reply@mailsupport.aliyun.com",
        ("seller@example.com",), "Welcome to your mailbox", "Welcome",
        "2026-09-08T10:00:00+00:00", "task-1", "",
    )

    assert message.is_system_notification


def test_analysis_service_skips_system_notifications():
    system_message = make_message("Welcome to your mailbox", "Welcome")
    system_message = InboundEmail(
        **{**system_message.__dict__, "from_email": "no-reply@mailsupport.aliyun.com"}
    )

    class Messages:
        def list_for_task(self, task_id):
            return [system_message]

    class Analyses:
        def get_by_message_id(self, message_id):
            raise AssertionError("system notification must not be classified")

    result = ReplyAnalysisService(Messages(), Analyses()).analyze_task("task-1")

    assert result.analyzed == 0
    assert result.reused == 0
    assert result.items == ()
