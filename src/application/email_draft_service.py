"""基于客户事实生成开发信草稿，不执行发送。"""

from __future__ import annotations

from typing import Protocol

from src.domain.email_draft import EmailDraft
from src.domain.lead import CleanLead
from src.domain.research import ResearchResult


class StructuredProvider(Protocol):
    def generate_json(self, prompt: str) -> dict: ...


class EmailDraftService:
    def __init__(self, provider: StructuredProvider):
        self._provider = provider

    def generate(
        self,
        task_id: str,
        lead: CleanLead,
        research: ResearchResult,
        template: str,
        product: str,
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
        prompt = (
            "Write a concise first-contact B2B email to the recipient company. "
            "The recipient company is not the sender. Use [Our Company], [Your Name], "
            "or [Your Position] when sender details are not supplied. Use only the supplied facts. "
            "Do not invent prices, delivery times, certifications, partnerships, or buyer needs. "
            "Return JSON with exactly two string fields: subject and body. "
            f"Company: {lead.company_name}\n"
            f"Business summary: {research.business_summary}\n"
            f"Products: {', '.join(research.products)}\n"
            f"Country: {research.country}\n"
            f"Evidence URL: {research.evidence_url}\n"
            f"Configured template direction: {template_hint}"
        )
        data = self._provider.generate_json(prompt)
        subject = data.get("subject")
        body = data.get("body")
        if not isinstance(subject, str) or not subject.strip():
            raise ValueError("email subject is required")
        if not isinstance(body, str) or not body.strip():
            raise ValueError("email body is required")
        return EmailDraft.create(
            task_id=task_id,
            lead_domain=lead.domain,
            recipient_email=lead.emails[0],
            subject=subject.strip(),
            body=body.strip(),
            evidence_urls=(research.evidence_url,),
        )
