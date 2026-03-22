import base64
import email
import os
from dataclasses import dataclass
from datetime import datetime, timezone

import html2text
from googleapiclient.errors import HttpError

from auth import GoogleClient

FETCH_LABEL = "quotes"
PROCESSED_LABEL = "LQA/Processed"
FETCH_QUERY = f"is:unread label:{FETCH_LABEL} -label:{PROCESSED_LABEL}"


@dataclass
class EmailMessage:
    message_id: str
    sender: str
    subject: str
    received_at: datetime
    body: str


class GmailReader:
    def __init__(self) -> None:
        self._service = GoogleClient.get_instance().gmail
        self._processed_label_id: str | None = None

    def fetch_unread(self) -> list[EmailMessage]:
        results = (
            self._service.users()
            .messages()
            .list(userId="me", q=FETCH_QUERY, maxResults=50)
            .execute()
        )
        messages = results.get("messages", [])
        return [self._parse(msg["id"]) for msg in messages]

    def mark_processed(self, message_id: str) -> None:
        label_id = self._get_or_create_processed_label()
        self._service.users().messages().modify(
            userId="me",
            id=message_id,
            body={"addLabelIds": [label_id], "removeLabelIds": ["UNREAD"]},
        ).execute()

    def _parse(self, message_id: str) -> EmailMessage:
        raw = (
            self._service.users()
            .messages()
            .get(userId="me", id=message_id, format="full")
            .execute()
        )

        headers = {h["name"]: h["value"] for h in raw["payload"]["headers"]}
        sender = headers.get("From", "")
        subject = headers.get("Subject", "")
        date_str = headers.get("Date", "")

        try:
            received_at = email.utils.parsedate_to_datetime(date_str)
        except Exception:
            received_at = datetime.now(tz=timezone.utc)

        body = self._extract_body(raw["payload"])

        return EmailMessage(
            message_id=message_id,
            sender=sender,
            subject=subject,
            received_at=received_at,
            body=body,
        )

    def _extract_body(self, payload: dict) -> str:
        plain, html = self._walk_parts(payload)
        if plain:
            return plain.strip()
        if html:
            converter = html2text.HTML2Text()
            converter.ignore_links = True
            converter.ignore_images = True
            return converter.handle(html).strip()
        return ""

    def _walk_parts(self, payload: dict) -> tuple[str, str]:
        plain = ""
        html = ""
        mime = payload.get("mimeType", "")

        if mime == "text/plain":
            plain = _decode_data(payload.get("body", {}).get("data", ""))
        elif mime == "text/html":
            html = _decode_data(payload.get("body", {}).get("data", ""))
        else:
            for part in payload.get("parts", []):
                p, h = self._walk_parts(part)
                plain = plain or p
                html = html or h

        return plain, html

    def _get_or_create_processed_label(self) -> str:
        if self._processed_label_id:
            return self._processed_label_id

        existing = self._service.users().labels().list(userId="me").execute()
        for label in existing.get("labels", []):
            if label["name"] == PROCESSED_LABEL:
                self._processed_label_id = label["id"]
                return self._processed_label_id

        created = (
            self._service.users()
            .labels()
            .create(
                userId="me",
                body={
                    "name": PROCESSED_LABEL,
                    "labelListVisibility": "labelShow",
                    "messageListVisibility": "show",
                },
            )
            .execute()
        )
        self._processed_label_id = created["id"]
        return self._processed_label_id


def _decode_data(data: str) -> str:
    if not data:
        return ""
    return base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")
