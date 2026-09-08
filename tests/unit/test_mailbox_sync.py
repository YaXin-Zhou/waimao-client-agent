from src.application.acquisition_service import AssessedLead
from src.application.mailbox_sync import MailboxSyncService
from src.domain.audit_event import AuditEvent
from src.domain.inbound_email import InboundEmail
from src.domain.lead import CleanLead, LeadScore


class Leads:
    def __init__(self, item):
        self.item = item

    def list_assessments(self, task_id):
        return [self.item]


class Messages:
    def __init__(self):
        self.items = {}

    def save(self, message):
        self.items[message.message_id] = message

    def get_by_message_id(self, message_id):
        return self.items.get(message_id)

    def list_for_task(self, task_id):
        return [item for item in self.items.values() if item.task_id == task_id]


class Inbox:
    def __init__(self, messages):
        self.messages = messages

    def fetch_inbox(self):
        return self.messages


class Audit:
    def __init__(self):
        self.events = []

    def save(self, event):
        self.events.append(event)


def test_sync_deduplicates_and_associates_customer_domain():
    lead = CleanLead("Alpine", "alpine.example", ("sales@alpine.example",), "Germany", "complete")
    assessed = AssessedLead(lead, LeadScore(70, "B", {}))
    message = InboundEmail.create(
        "1", "<one@example>", "", (), "sales@alpine.example", ("seller@example.com",),
        "Interested", "Please send pricing", "2026-09-08T10:00:00+00:00"
    )
    repository = Messages()
    audit = Audit()
    service = MailboxSyncService(Leads(assessed), repository, audit=audit)

    first = service.sync("task-1", Inbox([message]))
    second = service.sync("task-1", Inbox([message]))

    assert (len(first.fetched), first.inserted, first.skipped_duplicates) == (1, 1, 0)
    assert (len(second.fetched), second.inserted, second.skipped_duplicates) == (1, 0, 1)
    assert repository.items[message.message_id].lead_domain == "alpine.example"
    assert len(audit.events) == 2
    assert isinstance(audit.events[0], AuditEvent)
    assert audit.events[0].entity_type == "mailbox_sync"
    assert "duplicates=0" in audit.events[0].note
