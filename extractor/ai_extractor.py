import json
import os
from dataclasses import dataclass

from dotenv import load_dotenv
from openai import OpenAI

from auth import SupabaseClient
from gmail.reader import EmailMessage

load_dotenv()

CONFIDENCE_THRESHOLD = float(os.environ.get("CONFIDENCE_THRESHOLD", "0.5"))

SYSTEM_PROMPT = """You are a logistics quote extraction agent.

Extract structured data from the email and return a single JSON object.
Use null for any field you cannot find with confidence.

IMPORTANT: Emails are often reply chains with the same content quoted multiple times.
Extract fees ONLY from the most recent message at the top of the thread.
Do not extract the same fee more than once. If a fee appears in both the latest
message and a quoted/forwarded section, include it exactly once.

JSON structure:
{
  "confidence_score": <float 0.0-1.0>,
  "client_name": <string | null>,
  "carrier_name": <string | null>,
  "quote_date": <ISO 8601 date string | null>,
  "fees": [
    {
      "raw_name": <string>,
      "amount": <float>,
      "unit": <"flat" | "per_unit" | "percent">
    }
  ]
}

confidence_score rules:
- 0.9-1.0: all fields present, no ambiguity
- 0.6-0.89: minor gaps (e.g. date missing) but core data is clear
- 0.5-0.59: client name uncertain or fees partially readable
- below 0.5: client name missing, conflicting amounts, or body is a reply chain with unclear data

unit rules:
- "flat": a fixed dollar amount (e.g. $150, USD 200)
- "per_unit": a rate per item/pallet/cwt (e.g. $12/pallet)
- "percent": a percentage surcharge (e.g. 12%, FSC 8.5%)"""


@dataclass
class ExtractedFee:
    raw_name: str
    master_name: str
    amount: float
    unit: str


@dataclass
class QuoteExtraction:
    confidence_score: float
    client_name: str | None
    carrier_name: str | None
    quote_date: str | None
    fees: list[ExtractedFee]
    message_id: str
    needs_review: bool


class AIExtractor:
    def __init__(self) -> None:
        self._client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        self._supabase = SupabaseClient.get_instance()

    def extract(self, email: EmailMessage) -> QuoteExtraction:
        raw = self._call_gpt(email)
        fees = self._map_fees(raw.get("fees", []))
        confidence = float(raw.get("confidence_score", 0.0))

        return QuoteExtraction(
            confidence_score=confidence,
            client_name=raw.get("client_name"),
            carrier_name=raw.get("carrier_name"),
            quote_date=raw.get("quote_date"),
            fees=fees,
            message_id=email.message_id,
            needs_review=confidence <= CONFIDENCE_THRESHOLD,
        )

    def _call_gpt(self, email: EmailMessage) -> dict:
        user_content = (
            f"Subject: {email.subject}\n"
            f"From: {email.sender}\n"
            f"Date: {email.received_at.isoformat()}\n\n"
            f"{email.body}"
        )

        response = self._client.chat.completions.create(
            model="gpt-4o",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            temperature=0,
        )

        return json.loads(response.choices[0].message.content)

    def _map_fees(self, raw_fees: list[dict]) -> list[ExtractedFee]:
        mapped = []
        seen: set[str] = set()
        for fee in raw_fees:
            raw_name = fee.get("raw_name", "")
            dedup_key = raw_name.lower().strip()
            if dedup_key in seen:
                continue
            seen.add(dedup_key)
            master_name = self._lookup_master_name(raw_name)
            mapped.append(
                ExtractedFee(
                    raw_name=raw_name,
                    master_name=master_name,
                    amount=float(fee.get("amount", 0.0)),
                    unit=fee.get("unit", "flat"),
                )
            )
        return mapped

    def _lookup_master_name(self, raw_name: str) -> str:
        if not raw_name:
            return raw_name
        result = (
            self._supabase.table("fee_dictionary")
            .select("master_name")
            .ilike("raw_name", raw_name)
            .limit(1)
            .execute()
        )
        if result.data:
            return result.data[0]["master_name"]
        return raw_name
