from src.application.translation_service import TranslationService
from src.domain.email_draft import EmailDraft


class FakeTranslator:
    def __init__(self):
        self.calls = []

    def translate(self, text, source, target):
        self.calls.append((text, source, target))
        return f"中文：{text}"


def test_translation_preview_does_not_change_draft_and_caches_text():
    provider = FakeTranslator()
    service = TranslationService(provider)
    draft = EmailDraft.create("task-1", "example.com", "sales@example.com", "Subject", "Body")

    first = service.preview(draft)
    second = service.preview(draft)

    assert first["is_preview"] is True
    assert first["target_language"] == "zh-CN"
    assert first["subject"] == "中文：Subject"
    assert first["body"] == "中文：Body"
    assert second == first
    assert len(provider.calls) == 2
    assert draft.subject == "Subject"


def test_translation_preview_rejects_unsupported_language():
    service = TranslationService(FakeTranslator())
    draft = EmailDraft.create("task-1", "example.com", "sales@example.com", "Subject", "Body")

    try:
        service.preview(draft, "fr")
    except ValueError as error:
        assert str(error) == "only zh-CN preview is supported"
    else:
        raise AssertionError("unsupported language should fail")
