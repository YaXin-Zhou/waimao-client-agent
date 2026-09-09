"""根据真实客户来信和已保存分析生成跟进草稿；不执行发送。"""

from __future__ import annotations

from src.domain.email_draft import EmailDraft, EmailDraftKind
from src.domain.email_language import detect_reply_language
from src.domain.inbound_email import InboundEmail
from src.domain.lead import CleanLead
from src.domain.reply_analysis import ReplyAnalysis, ReplyCategory
from src.domain.research import ResearchResult
from src.domain.sender_profile import SenderProfile


class ReplyDraftService:
    def __init__(self, provider):
        self._provider = provider

    def generate(
        self,
        message: InboundEmail,
        analysis: ReplyAnalysis,
        lead: CleanLead,
        research: ResearchResult,
        sender_profile: SenderProfile | None = None,
    ) -> EmailDraft:
        if message.is_system_notification:
            raise ValueError("system notifications cannot generate reply drafts")
        if message.is_bounce or analysis.category is ReplyCategory.BOUNCE:
            raise ValueError("bounce messages cannot generate reply drafts")
        if analysis.message_id != message.message_id:
            raise ValueError("reply analysis does not match message")
        sender_company, sender_name, sender_position = (
            sender_profile or SenderProfile()
        ).prompt_values()
        language = detect_reply_language(message.body)
        prompt = (
            f"Write a concise {language} B2B follow-up email replying to the customer. "
            "Use only the supplied facts. Do not invent prices, delivery times, certifications, "
            "partnerships, stock, or commitments. Do not mention internal classification. "
            "Return JSON with exactly two string fields: subject and body. "
            f"Customer email: {message.from_email}\n"
            f"Customer subject: {message.subject}\n"
            f"Customer message: {message.body}\n"
            f"Detected customer language: {language}\n"
            f"Reply category: {analysis.category}\n"
            f"Suggested action: {analysis.suggested_action}\n"
            f"Company: {lead.company_name}\n"
            f"Business summary: {research.business_summary}\n"
            f"Products: {', '.join(research.products)}\n"
            f"Evidence URL: {research.evidence_url}\n"
            f"Sender company: {sender_company}\n"
            f"Sender name: {sender_name}\n"
            f"Sender position: {sender_position}"
        )
        data = self._provider.generate_json(prompt)
        subject = data.get("subject")
        body = data.get("body")
        if not isinstance(subject, str) or not subject.strip():
            raise ValueError("reply draft subject is required")
        if not isinstance(body, str) or not body.strip():
            raise ValueError("reply draft body is required")
        return EmailDraft.create(
            task_id=message.task_id,
            lead_domain=lead.domain,
            recipient_email=message.from_email,
            subject=subject.strip(),
            body=body.strip(),
            evidence_urls=(research.evidence_url,),
            kind=EmailDraftKind.REPLY,
            language=language,
            language_source="customer reply",
            language_requires_review=False,
        )
