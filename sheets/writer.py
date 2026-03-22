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

ITEM_COL_INDEX = 2  # zero-based index of "Item" in HEADER_ROW


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
    domain = match.group(1)
    return domain.split(".")[0]


class SheetsWriter:
    def __init__(self) -> None:
        self._drive = GoogleClient.get_instance().drive
        self._sheets = GoogleClient.get_instance().sheets

    def write(self, extraction: QuoteExtraction, subject: str) -> tuple[str, str]:
        """Write fees to the client's sheet.

        Returns (spreadsheet_url, action) where action is 'new' or 'updated'.
        """
        sheet_id = self._get_or_create_sheet(extraction.client_email)
        new_rows = self._build_rows(extraction, subject)
        action = self._upsert_rows(sheet_id, extraction.cargo_description, new_rows)
        return f"https://docs.google.com/spreadsheets/d/{sheet_id}", action

    def _upsert_rows(
        self, sheet_id: str, cargo_description: str | None, new_rows: list[list]
    ) -> str:
        existing = self._read_data_rows(sheet_id)
        item_key = (cargo_description or "").strip().lower()

        if item_key and any(
            (row[ITEM_COL_INDEX] if len(row) > ITEM_COL_INDEX else "").strip().lower()
            == item_key
            for row in existing
        ):
            # Remove old rows for this item, append updated ones at the end
            kept = [
                row for row in existing
                if (row[ITEM_COL_INDEX] if len(row) > ITEM_COL_INDEX else "").strip().lower()
                != item_key
            ]
            self._overwrite_data_rows(sheet_id, kept + new_rows)
            return "updated"

        self._append_rows(sheet_id, new_rows)
        return "new"

    def _read_data_rows(self, sheet_id: str) -> list[list]:
        """Returns all rows below the header row."""
        result = (
            self._sheets.spreadsheets()
            .values()
            .get(spreadsheetId=sheet_id, range="Quotes!A2:Z")
            .execute()
        )
        return result.get("values", [])

    def _overwrite_data_rows(self, sheet_id: str, rows: list[list]) -> None:
        """Clears everything below the header and writes rows from A2."""
        self._sheets.spreadsheets().values().clear(
            spreadsheetId=sheet_id, range="Quotes!A2:Z"
        ).execute()
        if rows:
            self._sheets.spreadsheets().values().update(
                spreadsheetId=sheet_id,
                range="Quotes!A2",
                valueInputOption="USER_ENTERED",
                body={"values": rows},
            ).execute()

    def _get_or_create_sheet(self, client_email: str | None) -> str:
        slug = _domain_from_email(client_email)
        title = f"{SHEET_NAME_PREFIX}{slug}"
        existing_id = self._search_drive(title)
        if existing_id:
            return existing_id
        return self._create_sheet(title)

    def _search_drive(self, title: str) -> str | None:
        query = (
            f"name = '{title}' and "
            f"mimeType = 'application/vnd.google-apps.spreadsheet' and "
            f"trashed = false"
        )
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
