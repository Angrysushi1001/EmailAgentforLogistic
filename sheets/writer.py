import re

from auth import GoogleClient
from extractor.ai_extractor import QuoteExtraction

SHEET_NAME_PREFIX = "Logistics_Quotes_"
HEADER_ROW = [
    "Date",
    "Client",
    "Item",
    "Carrier",
    "Fee Name",
    "Amount",
    "Unit",
    "Confidence",
    "Email Subject",
    "Message ID",
]


def _domain_from_email(email_address: str | None) -> str:
    """Extract the company slug from an email address.
    e.g. 'eugene@barry-callebaut.com' -> 'barry-callebaut'
         'user@gkegroup.com.sg'        -> 'gkegroup'
    """
    if not email_address:
        return "Unknown"
    match = re.search(r"@([\w.-]+)", email_address)
    if not match:
        return "Unknown"
    domain = match.group(1)          # e.g. 'barry-callebaut.com'
    return domain.split(".")[0]      # e.g. 'barry-callebaut'


class SheetsWriter:
    def __init__(self) -> None:
        self._drive = GoogleClient.get_instance().drive
        self._sheets = GoogleClient.get_instance().sheets

    def write(self, extraction: QuoteExtraction, subject: str) -> str:
        """Append one row per fee to the client's sheet. Returns the spreadsheet URL."""
        sheet_id = self._get_or_create_sheet(extraction.client_email)
        rows = self._build_rows(extraction, subject)
        self._append_rows(sheet_id, rows)
        return f"https://docs.google.com/spreadsheets/d/{sheet_id}"

    def _get_or_create_sheet(self, client_email: str | None) -> str:
        slug = _domain_from_email(client_email)
        title = f"{SHEET_NAME_PREFIX}{slug}"

        existing_id = self._search_drive(title)
        if existing_id:
            return existing_id

        return self._create_sheet(title)

    def _search_drive(self, title: str) -> str | None:
        query = f"name = '{title}' and mimeType = 'application/vnd.google-apps.spreadsheet' and trashed = false"
        result = (
            self._drive.files()
            .list(q=query, fields="files(id)", pageSize=1)
            .execute()
        )
        files = result.get("files", [])
        return files[0]["id"] if files else None

    def _create_sheet(self, title: str) -> str:
        spreadsheet = (
            self._sheets.spreadsheets()
            .create(
                body={
                    "properties": {"title": title},
                    "sheets": [{"properties": {"title": "Quotes"}}],
                },
                fields="spreadsheetId",
            )
            .execute()
        )
        sheet_id = spreadsheet["spreadsheetId"]
        self._append_rows(sheet_id, [HEADER_ROW])
        return sheet_id

    def _build_rows(self, extraction: QuoteExtraction, subject: str) -> list[list]:
        rows = []
        for fee in extraction.fees:
            rows.append([
                extraction.quote_date or "",
                extraction.client_name or "",
                extraction.cargo_description or "",
                extraction.carrier_name or "",
                fee.master_name,
                fee.amount,
                fee.unit,
                round(extraction.confidence_score, 2),
                subject,
                extraction.message_id,
            ])
        return rows

    def _append_rows(self, sheet_id: str, rows: list[list]) -> None:
        self._sheets.spreadsheets().values().append(
            spreadsheetId=sheet_id,
            range="Quotes!A1",
            valueInputOption="USER_ENTERED",
            insertDataOption="INSERT_ROWS",
            body={"values": rows},
        ).execute()
