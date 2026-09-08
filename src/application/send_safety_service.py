"""发送安全闸门用例，只做检查，不调用 SMTP。"""

from dataclasses import replace

from src.domain.send_safety import SendPolicy, SendSafetyResult, check_send_safety


class SendSafetyService:
    def __init__(self, drafts, attempts=None):
        self._drafts = drafts
        self._attempts = attempts

    def check(self, draft_id: str, policy: SendPolicy) -> SendSafetyResult:
        draft = self._drafts.get(draft_id)
        if draft is None:
            raise KeyError(f"Draft not found: {draft_id}")
        if (
            self._attempts is not None
            and policy.recent_contact_days > 0
            and hasattr(self._attempts, "was_recipient_contacted_since")
        ):
            policy = replace(
                policy,
                contacted_recently=self._attempts.was_recipient_contacted_since(
                    draft.recipient_email, policy.recent_contact_days
                ),
            )
        return check_send_safety(draft, policy)
