from src.infrastructure.ali_imap import AliImapConfig, parse_email

RAW_EMAIL = (
    b"From: Buyer <sales@alpine.example>\n"
    b"To: seller@example.com\n"
    b"Subject: Re: Portable solar generators\n"
    b"Message-ID: <reply-1@example>\n"
    b"In-Reply-To: <draft-1@example>\n"
    b"References: <draft-1@example>\n"
    b"Date: Tue, 08 Sep 2026 10:00:00 +0000\n"
    b"Content-Type: text/plain; charset=utf-8\n\n"
    b"Please send your catalogue.\n"
)


def test_parse_email_builds_thread_and_plain_text():
    message = parse_email("7", RAW_EMAIL)

    assert message.message_id == "<reply-1@example>"
    assert message.thread_key == "<draft-1@example>"
    assert message.subject == "Re: Portable solar generators"
    assert message.body == "Please send your catalogue."
    assert message.from_email == "sales@alpine.example"
    assert not message.is_bounce


def test_bounce_is_detected_without_model_call():
    raw = RAW_EMAIL.replace(
        b"Buyer <sales@alpine.example>", b"Mail Delivery System <mailer-daemon@example>"
    ).replace(
        b"Re: Portable solar generators", b"Mail delivery failed"
    )

    assert parse_email("8", raw).is_bounce


def test_platform_welcome_mail_is_marked_as_system_notification():
    raw = (
        b"Message-ID: <welcome-1@aliyun.com>\n"
        b"From: Aliyun <no-reply@mailsupport.aliyun.com>\n"
        b"To: postmaster@example.com\n"
        b"Subject: Welcome to your mailbox\n\n"
        b"Welcome"
    )

    assert parse_email("9", raw).is_system_notification


def test_incomplete_imap_config_is_not_configured():
    assert not AliImapConfig("imap.example", "user", "").configured


def test_connection_check_opens_mailbox_read_only_without_searching():
    calls = []

    class Connection:
        def login(self, username, password):
            calls.append(("login", username, password))

        def select(self, mailbox, readonly=False):
            calls.append(("select", mailbox, readonly))
            return "OK", []

        def logout(self):
            calls.append(("logout",))

    from src.infrastructure.ali_imap import AliImapMailbox

    mailbox = AliImapMailbox(
        AliImapConfig("imap.example", "user", "secret"),
        connection_factory=lambda host, port: Connection(),
    )

    mailbox.test_connection()

    assert calls == [
        ("login", "user", "secret"),
        ("select", "INBOX", True),
        ("logout",),
    ]
