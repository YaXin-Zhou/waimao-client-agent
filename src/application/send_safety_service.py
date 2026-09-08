"""发送安全闸门用例，只做检查，不调用 SMTP。"""

from src.domain.send_safety import SendPolicy, SendSafetyResult, check_send_safety


class SendSafetyService:
    def __init__(self, drafts):
        self._drafts = drafts

    def check(self, draft_id: str, policy: SendPolicy) -> SendSafetyResult:
        draft = self._drafts.get(draft_id)
        if draft is None:
            raise KeyError(f"Draft not found: {draft_id}")
        return check_send_safety(draft, policy)
