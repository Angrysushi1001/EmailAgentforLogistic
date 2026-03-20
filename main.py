"""
Logistics Quote Agent entry point.
Run with: python main.py
"""

from auth import SupabaseClient
from extractor import AIExtractor, QuoteExtraction
from gmail import EmailMessage, GmailReader
from sheets import SheetsWriter


def write_pending(email: EmailMessage, extraction: QuoteExtraction) -> None:
    SupabaseClient.get_instance().table("pending_quotes").upsert(
        {
            "message_id": email.message_id,
            "sender": email.sender,
            "subject": email.subject,
            "received_at": email.received_at.isoformat(),
            "email_body": email.body,
            "raw_extraction": {
                "confidence_score": extraction.confidence_score,
                "client_name": extraction.client_name,
                "carrier_name": extraction.carrier_name,
                "quote_date": extraction.quote_date,
                "fees": [
                    {
                        "raw_name": f.raw_name,
                        "master_name": f.master_name,
                        "amount": f.amount,
                        "unit": f.unit,
                    }
                    for f in extraction.fees
                ],
            },
            "confidence_score": extraction.confidence_score,
            "status": "pending",
        },
        on_conflict="message_id",
    ).execute()


def main() -> None:
    reader = GmailReader()
    extractor = AIExtractor()
    writer = SheetsWriter()

    emails = reader.fetch_unread()
    if not emails:
        print("No unread emails in label:quotes.")
        return

    print(f"Found {len(emails)} email(s) to process.")

    for email in emails:
        print(f"\n  Processing: {email.subject!r} from {email.sender}")
        extraction = extractor.extract(email)
        print(f"  Confidence: {extraction.confidence_score:.2f}")

        if extraction.needs_review:
            write_pending(email, extraction)
            print(f"  -> Low confidence. Written to pending_quotes for review.")
        else:
            url, action = writer.write(extraction, email.subject)
            label = "New entry" if action == "new" else "Updated existing entry"
            print(f"  -> {label}. Client: {extraction.client_name} | Item: {extraction.cargo_description} | Fees: {len(extraction.fees)}")
            print(f"  -> {url}")

        reader.mark_processed(email.message_id)
        print(f"  -> Marked as LQA/Processed.")

    print(f"\nDone. {len(emails)} email(s) processed.")


if __name__ == "__main__":
    main()
