"""基于客户事实生成开发信草稿，不执行发送。"""

from __future__ import annotations

from typing import Protocol

from src.domain.email_draft import EmailDraft
from src.domain.email_language import resolve_language
from src.domain.lead import CleanLead
from src.domain.research import ResearchResult
from src.domain.sender_profile import SenderProfile


class StructuredProvider(Protocol):
    def generate_json(self, prompt: str) -> dict: ...


class EmailDraftService:
    def __init__(
        self,
        provider: StructuredProvider,
        country_languages: dict[str, str] | None = None,
    ):
        self._provider = provider
        self._country_languages = country_languages or {}

    def generate(
        self,
        task_id: str,
        lead: CleanLead,
        research: ResearchResult,
        template: str,
        product: str,
        sender_profile: SenderProfile | None = None,
        requested_language: str = "auto",
    ) -> EmailDraft:
        if not lead.emails:
            raise ValueError("recipient email is required")
        if not template.strip():
            raise ValueError("email template is required")
        if not product.strip():
            raise ValueError("product is required")
        try:
            template_hint = template.format(company=lead.company_name, product=product)
        except (KeyError, ValueError) as exc:
            raise ValueError("email template contains unsupported placeholders") from exc
        sender_company, sender_name, sender_position = (
            sender_profile or SenderProfile()
        ).prompt_values()
        decision = resolve_language(
            requested_language,
            research.country,
            research.website_language,
            self._country_languages,
        )
        prompt = (
            f"Write a concise first-contact B2B email in {decision.language} "
            "to the recipient company. "
            "The recipient company is not the sender. Use [Our Company], [Your Name], "
            "or [Your Position] when sender details are not supplied. Use only the supplied facts. "
            "Do not invent prices, delivery times, certifications, partnerships, or buyer needs. "
            "Return JSON with exactly two string fields: subject and body. "
            f"Company: {lead.company_name}\n"
            f"Business summary: {research.business_summary}\n"
            f"Products: {', '.join(research.products)}\n"
            f"Country: {research.country}\n"
            f"Website language: {research.website_language}\n"
            f"Language decision: {decision.language} (source: {decision.source})\n"
            f"Evidence URL: {research.evidence_url}\n"
            f"Sender company: {sender_company}\n"
            f"Sender name: {sender_name}\n"
            f"Sender position: {sender_position}\n"
            f"Configured template direction: {template_hint}"
        )
        data = self._provider.generate_json(prompt)
        subject = data.get("subject")
        body = data.get("body")
        if not isinstance(subject, str) or not subject.strip():
            raise ValueError("email subject is required")
        if not isinstance(body, str) or not body.strip():
            raise ValueError("email body is required")
        subject = self._replace_sender_placeholders(subject, sender_company, sender_name, sender_position)
        body = self._replace_sender_placeholders(body, sender_company, sender_name, sender_position)
        return EmailDraft.create(
            task_id=task_id,
            lead_domain=lead.domain,
            recipient_email=lead.emails[0],
            subject=subject.strip(),
            body=body.strip(),
            evidence_urls=(research.evidence_url,),
            language=decision.language,
            language_source=decision.source,
            language_requires_review=decision.requires_review,
        )

    @staticmethod
    def _replace_sender_placeholders(
        content: str,
        sender_company: str,
        sender_name: str,
        sender_position: str,
    ) -> str:
        """Ensure generated drafts never expose the template's sender placeholders."""
        replacements = {
            "[Our Company]": sender_company,
            "[Your Company]": sender_company,
            "[Your Name]": sender_name,
            "[Your Position]": sender_position,
        }
        for placeholder, value in replacements.items():
            content = content.replace(placeholder, value)
        return content
