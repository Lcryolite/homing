"""Tests for MailBuilder — outgoing mail construction."""

from email.mime.multipart import MIMEMultipart

from openemail.core.mail_builder import MailBuilder


class TestMailBuilderPlainText:
    def test_build_plain_text(self) -> None:
        builder = MailBuilder()
        builder.set_from("test@example.com", "Test User")
        builder.set_to(["to@example.com"])
        builder.set_subject("Hello")
        builder.set_text_body("World")

        msg = builder.build()
        assert msg["From"] == "Test User <test@example.com>"
        assert msg["To"] == "to@example.com"
        assert msg["Subject"] == "Hello"
        assert msg.get_payload()[0].get_payload(decode=True).decode("utf-8") == "World"
        assert msg.get_payload()[0].get_content_type() == "text/plain"

    def test_build_multiple_recipients(self) -> None:
        builder = MailBuilder()
        builder.set_from("a@example.com")
        builder.set_to(["to1@example.com", "to2@example.com"])
        builder.set_cc(["cc@example.com"])
        builder.set_bcc(["bcc@example.com"])
        builder.set_subject("Multi")
        builder.set_text_body("Body")

        msg = builder.build()
        assert msg["To"] == "to1@example.com, to2@example.com"
        assert msg["Cc"] == "cc@example.com"
        # Bcc is not added to headers (envelope only in real SMTP)
        assert "Bcc" not in msg

    def test_message_id_format(self) -> None:
        builder = MailBuilder()
        builder.set_from("test@example.com")
        builder.set_to(["to@example.com"])
        builder.set_subject("ID Test")
        builder.set_text_body("Body")

        msg = builder.build()
        mid = msg["Message-ID"]
        assert mid.startswith("<")
        assert mid.endswith(">")
        assert "@example.com" in mid

    def test_date_header_present(self) -> None:
        builder = MailBuilder()
        builder.set_from("test@example.com")
        builder.set_to(["to@example.com"])
        builder.set_subject("Date Test")
        builder.set_text_body("Body")

        msg = builder.build()
        assert msg["Date"] is not None


class TestMailBuilderHtml:
    def test_build_html_only(self) -> None:
        builder = MailBuilder()
        builder.set_from("test@example.com")
        builder.set_to(["to@example.com"])
        builder.set_subject("HTML")
        builder.set_html_body("<h1>Hello</h1>")

        msg = builder.build()
        assert msg.get_content_type() == "multipart/alternative"
        parts = msg.get_payload()
        assert len(parts) == 1
        assert parts[0].get_content_type() == "text/html"
        assert parts[0].get_payload(decode=True).decode("utf-8") == "<h1>Hello</h1>"

    def test_build_text_and_html(self) -> None:
        builder = MailBuilder()
        builder.set_from("test@example.com")
        builder.set_to(["to@example.com"])
        builder.set_subject("Both")
        builder.set_text_body("Plain")
        builder.set_html_body("<p>HTML</p>")

        msg = builder.build()
        assert msg.get_content_type() == "multipart/alternative"
        parts = msg.get_payload()
        assert len(parts) == 2
        assert parts[0].get_content_type() == "text/plain"
        assert parts[0].get_payload(decode=True).decode("utf-8") == "Plain"
        assert parts[1].get_content_type() == "text/html"
        assert parts[1].get_payload(decode=True).decode("utf-8") == "<p>HTML</p>"


class TestMailBuilderAttachments:
    def test_single_attachment(self) -> None:
        builder = MailBuilder()
        builder.set_from("test@example.com")
        builder.set_to(["to@example.com"])
        builder.set_subject("Attach")
        builder.set_text_body("See attached")
        builder.add_attachment("file.txt", b"data", "text/plain")

        msg = builder.build()
        assert msg.get_content_type() == "multipart/mixed"
        parts = msg.get_payload()
        # First part is the text body wrapper
        assert len(parts) == 2
        att_part = parts[1]
        assert att_part.get_content_type() == "text/plain"
        assert att_part.get_filename() == "file.txt"
        assert att_part.get_payload(decode=True) == b"data"

    def test_attachment_with_html(self) -> None:
        builder = MailBuilder()
        builder.set_from("test@example.com")
        builder.set_to(["to@example.com"])
        builder.set_subject("Attach+HTML")
        builder.set_text_body("Plain")
        builder.set_html_body("<p>HTML</p>")
        builder.add_attachment("file.txt", b"data", "text/plain")

        msg = builder.build()
        assert msg.get_content_type() == "multipart/mixed"
        parts = msg.get_payload()
        # First part is multipart/alternative wrapper, second is attachment
        assert len(parts) == 2
        assert parts[0].get_content_type() == "multipart/alternative"
        assert parts[1].get_content_type() == "text/plain"

    def test_custom_header(self) -> None:
        builder = MailBuilder()
        builder.set_from("test@example.com")
        builder.set_to(["to@example.com"])
        builder.set_subject("Custom")
        builder.set_text_body("Body")
        builder.add_header("X-Custom", "value")

        msg = builder.build()
        assert msg["X-Custom"] == "value"


class TestMailBuilderReplyForward:
    def test_reply_structure(self) -> None:
        builder = MailBuilder()
        builder.set_from("test@example.com")
        builder.set_to(["to@example.com"])
        builder.set_subject("Re: Original")
        builder.set_text_body("My reply")

        msg = builder.build_reply("Original text", "Original Sender <orig@example.com>")
        assert msg["Subject"] == "Re: Original"
        body = msg.get_payload()[0].get_payload(decode=True).decode("utf-8")
        assert "My reply" in body
        assert "于 Original Sender <orig@example.com> 写道:" in body
        assert "> Original text" in body

    def test_forward_structure(self) -> None:
        builder = MailBuilder()
        builder.set_from("test@example.com")
        builder.set_to(["to@example.com"])
        builder.set_subject("Fwd: Original")
        builder.set_text_body("See below")

        msg = builder.build_forward("Original text", "From: orig@example.com")
        assert msg["Subject"] == "Fwd: Original"
        body = msg.get_payload()[0].get_payload(decode=True).decode("utf-8")
        assert "See below" in body
        assert "---------- 转发的邮件 ----------" in body
        assert "From: orig@example.com" in body
        assert "Original text" in body

    def test_in_reply_to_header(self) -> None:
        builder = MailBuilder()
        builder.set_from("test@example.com")
        builder.set_to(["to@example.com"])
        builder.set_subject("Re: Thread")
        builder.set_text_body("Reply")
        builder.set_in_reply_to("<orig-msg-id@example.com>")
        builder.set_references("<orig-msg-id@example.com>")

        msg = builder.build()
        assert msg["In-Reply-To"] == "<orig-msg-id@example.com>"
        assert msg["References"] == "<orig-msg-id@example.com>"

    def test_reply_to_header(self) -> None:
        builder = MailBuilder()
        builder.set_from("test@example.com")
        builder.set_to(["to@example.com"])
        builder.set_subject("Sub")
        builder.set_text_body("Body")
        builder.set_reply_to("reply@example.com")

        msg = builder.build()
        assert msg["Reply-To"] == "reply@example.com"


class TestMailBuilderEdgeCases:
    def test_empty_body(self) -> None:
        builder = MailBuilder()
        builder.set_from("test@example.com")
        builder.set_to(["to@example.com"])
        builder.set_subject("Empty")

        msg = builder.build()
        # No text/html body → empty multipart
        assert isinstance(msg, MIMEMultipart)

    def test_no_recipients(self) -> None:
        builder = MailBuilder()
        builder.set_from("test@example.com")
        builder.set_subject("No To")
        builder.set_text_body("Body")

        msg = builder.build()
        assert "To" not in msg

    def test_from_without_name(self) -> None:
        builder = MailBuilder()
        builder.set_from("test@example.com")
        builder.set_to(["to@example.com"])
        builder.set_subject("No Name")
        builder.set_text_body("Body")

        msg = builder.build()
        assert msg["From"] == "test@example.com"
