# Logistics Quote Agent — Full Lesson

This document explains everything built in this project: every file, every line of
code, every decision, and the architecture behind it. Written for someone who wants
to understand not just what the code does, but why it was written that way.

---

## Table of Contents

1. [What This Project Does](#1-what-this-project-does)
2. [The Full Architecture](#2-the-full-architecture)
3. [How We Built It — Step by Step](#3-how-we-built-it--step-by-step)
4. [File-by-File Code Explanation](#4-file-by-file-code-explanation)
5. [The Database — Supabase Tables](#5-the-database--supabase-tables)
6. [Architecture Pros and Cons](#6-architecture-pros-and-cons)
7. [Known Flaws and How to Fix Them](#7-known-flaws-and-how-to-fix-them)

---

## 1. What This Project Does

You (Raphael at lxpantos) receive logistics quote emails from warehouse providers
like GKE. These emails contain pricing information — storage fees, handling fees,
surcharges — for a specific client's cargo.

Before this agent existed, you would manually read each email and type the numbers
into a Google Sheet. This agent automates that entire process:

1. Reads unread emails from a Gmail label called `quotes`
2. Uses GPT-4o to understand the email and extract the pricing data
3. Writes the data into a Google Sheet named after the client
4. If the AI isn't confident enough, sends it to a human review queue instead

The result: you run `python3 main.py` and your Google Sheets are updated automatically.

---

## 2. The Full Architecture

```
                        ┌─────────────────────────────────────────────┐
                        │                  main.py                     │
                        │         (entry point / orchestrator)         │
                        └──────┬──────────┬──────────────┬────────────┘
                               │          │              │
                    ┌──────────▼──┐  ┌────▼──────┐  ┌───▼────────┐
                    │ GmailReader │  │AIExtractor│  │SheetsWriter│
                    │gmail/reader │  │extractor/ │  │sheets/     │
                    └──────┬──────┘  └─────┬─────┘  └─────┬──────┘
                           │               │               │
                    ┌──────▼──────┐  ┌─────▼──────┐  ┌────▼───────┐
                    │  Gmail API  │  │  OpenAI    │  │Google Drive│
                    │             │  │  GPT-4o    │  │   + Sheets │
                    └─────────────┘  └─────┬──────┘  └────────────┘
                                           │
                                    ┌──────▼──────┐
                                    │  Supabase   │
                                    │pending_quotes│
                                    │fee_dictionary│
                                    └─────────────┘
```

### The Four Layers

**Layer 1 — Auth (`auth/`)**
Handles all credential management. Every other layer calls into auth to get an
authenticated client. Nothing else deals with tokens or keys.

**Layer 2 — Gmail (`gmail/`)**
Reads emails and marks them as processed. Knows nothing about AI or spreadsheets.
Its only job is to fetch email data and update Gmail labels.

**Layer 3 — Extractor (`extractor/`)**
Takes an email and returns structured data. Knows nothing about Gmail or Sheets.
Calls GPT-4o, maps fee names, decides if confidence is high enough.

**Layer 4 — Sheets (`sheets/`)**
Takes structured data and writes it to Google Sheets. Knows nothing about Gmail
or AI. Its only job is to find/create the right spreadsheet and write rows.

**Orchestrator — `main.py`**
Wires all four layers together. Calls them in order. Decides what to do based
on the extraction result.

### Data Flow

```
Email arrives in Gmail
       ↓
GmailReader.fetch_unread()
  → Returns list of EmailMessage objects
       ↓
AIExtractor.extract(email)
  → Sends body to GPT-4o
  → Gets JSON back
  → Maps fee names via fee_dictionary
  → Returns QuoteExtraction object
       ↓
confidence_score <= 0.5?
  YES → write to Supabase pending_quotes (human reviews later)
  NO  → SheetsWriter.write(extraction)
          → Search Drive for Logistics_Quotes_[domain]
          → Create sheet if missing
          → Check if item already exists in sheet
          → Update existing rows OR append new rows
       ↓
reader.mark_processed(message_id)
  → Apply LQA/Processed label
  → Remove UNREAD label
```

---

## 3. How We Built It — Step by Step

### Step 1 — Planning Before Coding

Before writing a single line of code, we created a plan for each section. This
matters because jumping straight into code leads to contradictions — you build
a Gmail reader without knowing what shape of data the extractor needs, then have
to rewrite both.

The plan answered: what does each module receive, what does it return, and how
do the modules talk to each other?

### Step 2 — Section 1: Authentication Layer

**Why start here?**
Every other section needs an authenticated API client. If auth doesn't work,
nothing works. Getting this right first means every section after it has a
reliable foundation.

**What we built:**
- `auth/google_client.py` — connects to Google using OAuth2
- `auth/supabase_client.py` — connects to Supabase using a service role key
- `auth_test.py` — a sanity check script that verifies all connections work

**The OAuth2 flow (first run):**
1. Python opens a browser
2. You log in to Google and click Allow
3. Google sends back a token
4. We save that token to `token.json`
5. Every run after that, we load `token.json` and refresh it silently

**Why a Singleton?**
Without a Singleton, every class that needs Gmail would independently load the
token and build a new API client. That's wasteful (3 API clients for one run)
and fragile (what if the token file changes mid-run?). The Singleton ensures
the token is loaded exactly once and the same client is shared everywhere.

**The scope change during development:**
We originally used `gmail.readonly` but `mark_processed()` needs to modify labels
(write access). We upgraded to `gmail.modify` (a superset that includes read) and
deleted `token.json` to force re-authentication with the new scope.

### Step 3 — Section 2: Gmail Reader

**Why read from a label, not all inbox?**
If we queried all unread emails, the agent would try to process every email you
receive — newsletters, notifications, personal messages. Using a `quotes` label
means you have explicit control over what the agent sees. You apply the label
(manually or via a Gmail filter), the agent reads it.

**The Gmail filter (one-time setup):**
In Gmail settings, create a filter: Subject contains "quote" → Apply label `quotes`.
From that point, matching emails are auto-labeled.

**Why mark processed with a label instead of deleting?**
- Deletion is irreversible
- A Gmail label is a tag, not a folder — the email still lives in your inbox
- `LQA/Processed` is auto-created on first run if it doesn't exist
- The fetch query `is:unread label:quotes -label:LQA/Processed` excludes it on
  every subsequent run

**The MIME tree problem:**
Emails are not plain text files. They're structured in a format called MIME, which
is a nested tree of parts. A typical email looks like this:

```
multipart/alternative
├── text/plain   ← we want this first
└── text/html    ← fallback if no plain text
```

A forwarded or replied email looks like this:

```
multipart/mixed
├── multipart/alternative
│   ├── text/plain
│   └── text/html
└── message/rfc822  ← the original forwarded email (nested)
    └── multipart/alternative
        ├── text/plain
        └── text/html
```

The `_walk_parts()` function recursively navigates this tree, preferring `text/plain`.
If none exists, it falls back to `text/html` and strips the HTML tags using `html2text`.

**Why base64 decode?**
Gmail transmits email body content encoded in base64 URL-safe format. The `+==`
padding added in `_decode_data()` handles cases where the base64 string length
is not a multiple of 4 (a requirement of the base64 standard).

### Step 4 — Section 3: AI Extractor

**Why GPT-4o specifically?**
GPT-4o is the most capable model available at the time of writing and handles
unstructured, messy email text reliably. It understands context — it knows that
"S$50 per unit per calendar week" means amount=50, unit=per_unit.

**The `response_format: json_object` setting:**
By default, GPT-4o returns plain text. Setting `response_format` to `json_object`
forces it to always return valid JSON. Without this, it might return a JSON block
wrapped in a markdown code fence, which would break `json.loads()`.

**Why `temperature=0`?**
Temperature controls randomness. At 0, the model is fully deterministic — given
the same input it will always return the same output. For data extraction, we want
no creativity, no variation. We want the most likely correct answer every time.

**The confidence score:**
We ask GPT-4o to rate its own confidence from 0.0 to 1.0. This is called
self-reported confidence. The model has been trained to be reasonably calibrated —
when it says 0.9, it usually means it found all the data clearly. When it says 0.3,
it usually means something was ambiguous or missing.

The 0.5 threshold is a business decision: above it we trust the extraction enough
to write to a live Google Sheet. Below it, a human must review.

**The reply chain problem:**
Email threads repeat content. The original quote appears in the first message,
then is quoted again in every reply. Without instruction, GPT-4o extracts it
multiple times. Two defences:
1. The system prompt explicitly tells GPT-4o to only read the latest message
2. `_map_fees()` deduplicates by `raw_name.lower().strip()` as a safety net

**The fee_dictionary:**
Different logistics providers write the same fee differently:
- "Forklift Handling In Fee"
- "Handling-In"
- "H/I charge"

They all mean the same thing. The `fee_dictionary` Supabase table maps raw names
to a master name. After GPT-4o extracts `raw_name`, we query Supabase with a
case-insensitive match (`ilike`). If a match exists, we use `master_name`. If not,
we use `raw_name` as-is.

You populate this table manually over time as you encounter new variations.

**Dataclasses:**
`ExtractedFee` and `QuoteExtraction` are Python dataclasses. A dataclass is a
class that exists purely to hold data — it auto-generates `__init__`, `__repr__`,
and equality methods. It's the correct tool for structured data that gets passed
between functions.

### Step 5 — Section 4: Sheets Writer

**The Drive search before create:**
We don't blindly create a new sheet every time. We first search Drive for a file
named `Logistics_Quotes_[domain]`. If it exists, we reuse it. This is the
"one sheet per client" rule — all quotes for a client accumulate in one place.

**Sheet naming from email domain:**
Originally we used GPT-4o's extracted `client_name`, which produced names like
"Barry Callebaut Chocolate Asia Pacific Pte Ltd". Two problems:
1. Long and inconsistent (GPT-4o might extract it slightly differently next time)
2. Creates a new sheet if the name differs by even one character

Using the email domain (e.g. `barry-callebaut.com` → `barry-callebaut`) is
deterministic. The domain never changes regardless of how the company is named
in the email body.

**The upsert pattern:**
"Upsert" means "update if exists, insert if not". When a new quote arrives for
an item the sheet already has:
1. Read all existing data rows from the sheet
2. Filter out any rows where the Item column matches the new cargo
3. Write back the kept rows + the new rows

This handles any fee count change cleanly — if the old quote had 2 fees and the
new quote has 3, the old 2 rows are removed and the new 3 are added. There is
no partial overlap.

---

## 4. File-by-File Code Explanation

---

### `.env`

Stores all secrets. Never committed to git.

```
GMAIL_OAUTH_CONFIG=credentials.json
```
Path to the OAuth2 app credentials file. Tells `google_client.py` where to find
the client_id and client_secret for the browser login flow.

```
GOOGLE_TOKEN_PATH=token.json
```
Path where the OAuth token is saved after first login. This is what gets loaded
on every subsequent run to avoid opening the browser again.

```
SUPABASE_URL=https://...supabase.co
```
The URL of your Supabase project. Required for the Supabase client to know which
database to connect to.

```
SUPABASE_SERVICE_ROLE_KEY=eyJ...
```
A JWT (JSON Web Token) that grants full database access, bypassing all Row Level
Security rules. Used because this agent is a server-side process, not a user.

```
OPENAI_API_KEY=sk-proj-...
```
The key that authorises calls to GPT-4o. Each call costs money — protect this key.

```
CONFIDENCE_THRESHOLD=0.5
```
The cutoff score. Extractions at or below this go to `pending_quotes`. Above it
go straight to Google Sheets.

---

### `credentials.json`

Created in Google Cloud Console. Contains the app's identity — not your personal
credentials. Fields:

- `client_id` — unique identifier for this app
- `client_secret` — proves this is the real app, not an impersonator
- `redirect_uris` — where Google sends the token after you approve access
- `auth_uri` / `token_uri` — Google's OAuth endpoints

This file is gitignored. It never changes once created.

---

### `auth/google_client.py`

```python
import os
import threading
```
`os` — reads environment variables (`os.environ`).
`threading` — provides `Lock`, used to make the Singleton thread-safe.

```python
from dotenv import load_dotenv
```
`python-dotenv` reads the `.env` file and loads each line into `os.environ`.
Without this, `os.environ["GMAIL_OAUTH_CONFIG"]` would raise a KeyError.

```python
from google.auth.transport.requests import Request
```
Used to refresh an expired token. Makes an HTTP request to Google's token
endpoint with the refresh token, gets a new access token back.

```python
from google.oauth2.credentials import Credentials
```
Represents a set of OAuth2 credentials — access token, refresh token, expiry.
Can be serialised to JSON (for `token.json`) and deserialised back.

```python
from google_auth_oauthlib.flow import InstalledAppFlow
```
Manages the browser-based OAuth2 flow for "installed apps" (desktop/local scripts).
Opens a local server, redirects the browser to it after Google approval, captures
the token.

```python
from googleapiclient.discovery import build
```
Builds a Google API client from a service name and version. The API schema is
fetched from Google's discovery endpoint and cached locally.

```python
load_dotenv()
```
Executed at import time — as soon as this module is loaded, the `.env` file is
read. This means `os.environ` is populated before any class or function runs.

```python
SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]
```
The list of permissions the agent requests from you during the OAuth consent screen.
- `gmail.modify` — read emails, apply labels, remove UNREAD. Superset of readonly.
- `spreadsheets` — read and write any Google Sheet the account has access to.
- `drive` — search Drive for files, create new files.

All three are requested at once so there is only one consent screen.

```python
class GoogleClient:
    _instance: "GoogleClient | None" = None
    _lock = threading.Lock()
```
`_instance` — class-level variable (not instance-level). Shared across all code.
Starts as `None`, gets set once.
`_lock` — a mutex. Only one thread can hold the lock at a time, preventing two
threads from both seeing `_instance is None` and both building a new client
simultaneously. This is called "double-checked locking".

```python
    def __init__(self, credentials: Credentials) -> None:
        self.gmail = build("gmail", "v1", credentials=credentials)
        self.sheets = build("sheets", "v4", credentials=credentials)
        self.drive = build("drive", "v3", credentials=credentials)
```
The constructor. Called only once (by `_build()`). Builds three API service
objects using the same credentials. "v1", "v4", "v3" are API version numbers —
they change when Google releases breaking changes to the API.

```python
    @classmethod
    def get_instance(cls) -> "GoogleClient":
        if cls._instance is None:          # fast path — no lock needed if already built
            with cls._lock:                # slow path — acquire lock
                if cls._instance is None:  # check again inside lock
                    cls._instance = cls._build()
        return cls._instance
```
The public entry point. The outer `if` is an optimisation — once `_instance` is
set, future calls skip the lock entirely (locks are expensive). The inner `if`
re-checks after acquiring the lock because another thread might have built the
instance between the outer check and acquiring the lock.

```python
    @classmethod
    def _build(cls) -> "GoogleClient":
        creds_path = os.environ["GMAIL_OAUTH_CONFIG"]
        token_path = os.environ["GOOGLE_TOKEN_PATH"]
        creds: Credentials | None = None
```
Reads paths from env. `creds` starts as `None`.

```python
        if os.path.exists(token_path):
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)
```
If `token.json` exists (not first run), load it. The `SCOPES` argument is used
to check that the saved token covers all the scopes we need. If the saved token
was created with fewer scopes, `creds.valid` will return `False`.

```python
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
```
If the token doesn't exist or is invalid: first try to refresh silently. An
expired token has a `refresh_token` field that can be exchanged for a new
`access_token` without re-opening the browser.

```python
            else:
                flow = InstalledAppFlow.from_client_secrets_file(creds_path, SCOPES)
                creds = flow.run_local_server(port=0)
```
If refresh isn't possible (first run, or refresh token revoked): start the
browser flow. `port=0` means Python picks any available local port automatically.

```python
            with open(token_path, "w") as token_file:
                token_file.write(creds.to_json())
```
After getting a valid token (by refresh or new login), save it to `token.json`
so future runs don't need to open the browser.

```python
        return cls(creds)
```
Call `__init__` with the valid credentials. This builds the three API clients
and returns the `GoogleClient` instance.

---

### `auth/supabase_client.py`

```python
class SupabaseClient:
    _instance: "Client | None" = None
    _lock = threading.Lock()
```
Same Singleton pattern as `GoogleClient`. `Client` here is the Supabase client
type imported from the `supabase` library.

```python
    @classmethod
    def get_instance(cls) -> Client:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    url = os.environ["SUPABASE_URL"]
                    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
                    cls._instance = create_client(url, key)
        return cls._instance
```
`create_client(url, key)` establishes the connection to Supabase. The service
role key is a JWT — Supabase decodes it to verify the request is authorised and
knows to bypass Row Level Security.

Unlike the Google client, there is no token refresh — the service role key does
not expire during the lifetime of a run.

---

### `auth/__init__.py`

```python
from auth.google_client import GoogleClient
from auth.supabase_client import SupabaseClient

__all__ = ["GoogleClient", "SupabaseClient"]
```
Makes `from auth import GoogleClient` work without needing `from auth.google_client
import GoogleClient`. `__all__` defines what is exported when someone writes
`from auth import *`.

---

### `gmail/reader.py`

```python
FETCH_LABEL = "quotes"
PROCESSED_LABEL = "LQA/Processed"
FETCH_QUERY = f"is:unread label:{FETCH_LABEL} -label:{PROCESSED_LABEL}"
```
Module-level constants. `FETCH_QUERY` uses Gmail search syntax — identical to
what you would type in the Gmail search bar. The `-label:` prefix means "exclude
emails with this label". So the full query means: unread emails tagged `quotes`
that have NOT been tagged `LQA/Processed`.

```python
@dataclass
class EmailMessage:
    message_id: str
    sender: str
    subject: str
    received_at: datetime
    body: str
```
A dataclass is a container for structured data. Python generates `__init__`
automatically — `EmailMessage(message_id="...", sender="...", ...)` just works.
This is the contract between the Gmail layer and the Extractor layer — the
extractor always receives this exact shape of data.

```python
class GmailReader:
    def __init__(self) -> None:
        self._service = GoogleClient.get_instance().gmail
        self._processed_label_id: str | None = None
```
`self._service` — holds the Gmail API client. The underscore prefix is a Python
convention meaning "private to this class".
`self._processed_label_id` — cached once `_get_or_create_processed_label()` runs.
Avoids calling the Gmail API to look up the label ID on every `mark_processed()` call.

```python
    def fetch_unread(self) -> list[EmailMessage]:
        results = (
            self._service.users()
            .messages()
            .list(userId="me", q=FETCH_QUERY, maxResults=50)
            .execute()
        )
        messages = results.get("messages", [])
        return [self._parse(msg["id"]) for msg in messages]
```
The Gmail API returns only message IDs in a list call (not full content). We get
the IDs here, then call `_parse()` for each one to fetch the full message.
`userId="me"` means "the authenticated user" — the account that went through OAuth.
`maxResults=50` is a hard cap (known flaw — see Section 7).

```python
    def _parse(self, message_id: str) -> EmailMessage:
        raw = (
            self._service.users()
            .messages()
            .get(userId="me", id=message_id, format="full")
            .execute()
        )
```
`format="full"` returns the complete message including all headers and body parts.
Other options are `"minimal"` (just IDs and labels) and `"raw"` (RFC 2822 format).

```python
        headers = {h["name"]: h["value"] for h in raw["payload"]["headers"]}
```
Dict comprehension — converts `[{"name": "From", "value": "..."}, ...]` into
`{"From": "...", "Subject": "...", ...}` for easy lookup.

```python
        try:
            received_at = email.utils.parsedate_to_datetime(date_str)
        except Exception:
            received_at = datetime.now(tz=timezone.utc)
```
Email date strings are notoriously inconsistent (different timezones, formats,
missing fields). If parsing fails for any reason, we fall back to the current
time rather than crashing.

```python
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
```
Recursive function. If the current part IS text/plain or text/html, extract it.
If it's a container type (like `multipart/alternative`), recurse into its children.
`plain = plain or p` — keep the first `text/plain` found, ignore subsequent ones.
This prevents grabbing text from deep inside a nested forwarded message when the
top message already has plain text.

```python
def _decode_data(data: str) -> str:
    if not data:
        return ""
    return base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")
```
Gmail body data is base64 URL-safe encoded (uses `-` and `_` instead of `+` and `/`).
`+ "=="` pads the string to a valid base64 length (must be multiple of 4).
`errors="replace"` means invalid UTF-8 bytes are replaced with `?` instead of
raising an exception.

```python
    def _get_or_create_processed_label(self) -> str:
        if self._processed_label_id:
            return self._processed_label_id
        ...
        created = self._service.users().labels().create(...).execute()
        self._processed_label_id = created["id"]
        return self._processed_label_id
```
First checks the in-memory cache. Then lists all existing labels looking for
`LQA/Processed`. If not found, creates it. This runs at most once per agent
run — the result is cached in `self._processed_label_id`.

---

### `extractor/ai_extractor.py`

```python
CONFIDENCE_THRESHOLD = float(os.environ.get("CONFIDENCE_THRESHOLD", "0.5"))
```
`os.environ.get` with a default — if `CONFIDENCE_THRESHOLD` is not in the env,
use `"0.5"`. Wrapped in `float()` because env vars are always strings.

```python
SYSTEM_PROMPT = """..."""
```
The instructions given to GPT-4o at the start of every conversation. The system
prompt sets the model's role and rules. Key instructions:
- Only extract from the most recent message (not quoted history)
- Return exactly this JSON structure
- How to rate confidence
- What "flat", "per_unit", "percent" mean

The system prompt is a constant because it never changes between emails.

```python
@dataclass
class ExtractedFee:
    raw_name: str      # what appeared in the email, verbatim
    master_name: str   # after fee_dictionary lookup
    amount: float
    unit: str
```
`raw_name` is preserved so you can trace back to exactly what the email said.
`master_name` is the normalised name used in the sheet.

```python
@dataclass
class QuoteExtraction:
    confidence_score: float
    client_name: str | None     # e.g. "Barry Callebaut"
    client_email: str | None    # e.g. "eugene@barry-callebaut.com"
    carrier_name: str | None    # e.g. "GKE Warehousing"
    quote_date: str | None      # ISO 8601: "2026-03-18"
    cargo_description: str | None  # e.g. "2 x belts"
    fees: list[ExtractedFee]
    message_id: str
    needs_review: bool          # True if confidence_score <= threshold
```
`str | None` means the field can be a string or None. This is Python's union
type hint. GPT-4o returns `null` for fields it can't find, which becomes `None`
in Python after `json.loads()`.

```python
    def extract(self, email: EmailMessage) -> QuoteExtraction:
        raw = self._call_gpt(email)
        fees = self._map_fees(raw.get("fees", []))
        confidence = float(raw.get("confidence_score", 0.0))
```
`raw.get("fees", [])` — if GPT-4o somehow omits the "fees" key, default to an
empty list rather than crashing with a KeyError.
`float(raw.get("confidence_score", 0.0))` — same defensive pattern. Also wraps
in `float()` in case the model returns an integer (e.g. `1` instead of `1.0`).

```python
    def _call_gpt(self, email: EmailMessage) -> dict:
        user_content = (
            f"Subject: {email.subject}\n"
            f"From: {email.sender}\n"
            f"Date: {email.received_at.isoformat()}\n\n"
            f"{email.body}"
        )
```
Formats the email data into a single string. The `\n\n` between the headers and
body visually separates them — GPT-4o reads this like a human would read an email.
`received_at.isoformat()` converts the datetime to a standard string like
`"2026-03-18T13:59:00+08:00"`.

```python
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
```
`response.choices[0]` — the API can return multiple completions, but we only
ask for one. `[0]` gets the first (and only) one.
`.message.content` — the text of the response.
`json.loads()` — parses the JSON string into a Python dict.

```python
    def _map_fees(self, raw_fees: list[dict]) -> list[ExtractedFee]:
        mapped = []
        seen: set[str] = set()
        for fee in raw_fees:
            raw_name = fee.get("raw_name", "")
            dedup_key = raw_name.lower().strip()
            if dedup_key in seen:
                continue
            seen.add(dedup_key)
```
`seen` is a set (unordered collection of unique values). `dedup_key` is the
lowercased, whitespace-stripped fee name. If we've already seen this key, `continue`
skips to the next fee without processing it. This catches duplicates from reply
chains that GPT-4o may have missed.

```python
    def _lookup_master_name(self, raw_name: str) -> str:
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
```
`.ilike()` — case-insensitive LIKE query. Matches `"Forklift handling"` against
`"forklift handling"`. `.limit(1)` — we only need the first match.
Falls back to `raw_name` if no match found, so extraction never fails due to a
missing dictionary entry.

---

### `sheets/writer.py`

```python
def _domain_from_email(email_address: str | None) -> str:
    if not email_address:
        return "Unknown"
    match = re.search(r"@([\w.-]+)", email_address)
    if not match:
        return "Unknown"
    domain = match.group(1)
    return domain.split(".")[0]
```
`re.search(r"@([\w.-]+)", ...)` — regex that finds `@` followed by the domain.
The `(...)` captures the domain into group 1.
`[\w.-]+` matches word characters, dots, and hyphens — valid domain characters.
`.split(".")[0]` — splits `"barry-callebaut.com"` by `.` and takes the first
part: `"barry-callebaut"`. Works for `.com`, `.com.sg`, `.co.uk`, etc.

```python
    def write(self, extraction: QuoteExtraction, subject: str) -> tuple[str, str]:
        sheet_id = self._get_or_create_sheet(extraction.client_email)
        new_rows = self._build_rows(extraction, subject)
        action = self._upsert_rows(sheet_id, extraction.cargo_description, new_rows)
        return f"https://docs.google.com/spreadsheets/d/{sheet_id}", action
```
Returns a tuple of `(url, action)`. The caller unpacks this with
`url, action = writer.write(...)`. Action is either `"new"` or `"updated"`.

```python
    def _upsert_rows(self, sheet_id, cargo_description, new_rows) -> str:
        existing = self._read_data_rows(sheet_id)
        item_key = (cargo_description or "").strip().lower()

        if item_key and any(
            (row[ITEM_COL_INDEX] if len(row) > ITEM_COL_INDEX else "").strip().lower()
            == item_key
            for row in existing
        ):
```
`any(... for row in existing)` — a generator expression that checks if any row's
Item column matches. Short-circuits — stops at the first match.
`len(row) > ITEM_COL_INDEX` — defensive check: if a row is shorter than expected
(e.g. a blank row at the bottom of the sheet), don't crash with an IndexError.

```python
            kept = [
                row for row in existing
                if (row[ITEM_COL_INDEX] if len(row) > ITEM_COL_INDEX else "").strip().lower()
                != item_key
            ]
            self._overwrite_data_rows(sheet_id, kept + new_rows)
            return "updated"
```
List comprehension that filters out all rows matching the item. `kept + new_rows`
concatenates the unaffected rows with the new rows. The new rows go at the end.

```python
    def _overwrite_data_rows(self, sheet_id, rows) -> None:
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
```
`clear()` wipes everything from row 2 downward (row 1 is the header, never touched).
`update()` writes from cell A2 onward. `valueInputOption="USER_ENTERED"` means
Google Sheets interprets the values as if you typed them — it will auto-format
dates, numbers, etc.

---

### `main.py`

```python
def write_pending(email: EmailMessage, extraction: QuoteExtraction) -> None:
    SupabaseClient.get_instance().table("pending_quotes").upsert(
        {...},
        on_conflict="message_id",
    ).execute()
```
`upsert` = insert or update. `on_conflict="message_id"` means: if a row with
this `message_id` already exists, update it instead of inserting a duplicate.
This handles the case where an email is reprocessed (e.g. `LQA/Processed` was
removed manually).

```python
def main() -> None:
    reader = GmailReader()
    extractor = AIExtractor()
    writer = SheetsWriter()
```
All three are instantiated once. They share the same authenticated Google client
via the Singleton. No re-authentication happens between these lines.

```python
    for email in emails:
        print(f"\n  Processing: {email.subject!r} from {email.sender}")
```
`!r` in an f-string calls `repr()` on the value — it wraps the string in quotes
in the output. So a subject of `Hello World` prints as `'Hello World'`. Useful
for seeing exactly what the string contains, including whitespace.

```python
        if extraction.needs_review:
            write_pending(email, extraction)
        else:
            url, action = writer.write(extraction, email.subject)

        reader.mark_processed(email.message_id)
```
`mark_processed` runs regardless of which path was taken. Whether the email went
to Sheets or to pending_quotes, it gets marked as processed. An email should
never be processed twice.

---

## 5. The Database — Supabase Tables

### `fee_dictionary`

| Column | Type | Purpose |
|---|---|---|
| id | uuid | Primary key, auto-generated |
| raw_name | text | What appears in the email (e.g. "Forklift Handling In Fee") |
| master_name | text | The normalised name used in Sheets (e.g. "Handling In") |
| created_at | timestamptz | When the mapping was added |

You populate this manually. As you process more emails and encounter new fee
name variants, add a row mapping raw to master.

### `pending_quotes`

| Column | Type | Purpose |
|---|---|---|
| id | uuid | Primary key |
| message_id | text | Gmail message ID — unique per email |
| sender | text | Who sent the email |
| subject | text | Email subject line |
| received_at | timestamptz | When the email was received |
| email_body | text | Full plain text body |
| raw_extraction | jsonb | Everything GPT-4o returned |
| confidence_score | float | The score that triggered human review |
| status | text | "pending", "approved", or "rejected" |
| created_at | timestamptz | When this record was created |

Low-confidence extractions land here. A human reviews them, corrects any mistakes,
and manually writes to the sheet if the data looks right. The `status` field
tracks whether it has been reviewed.

---

## 6. Architecture Pros and Cons

### Architecture Used: Layered Pipeline with AI Extraction

The system is a linear pipeline with clearly separated layers. Each layer has
one responsibility and communicates with the next through well-defined data types
(`EmailMessage`, `QuoteExtraction`).

---

### Pros

**Separation of concerns**
Each module does exactly one thing. If Google changes the Gmail API, you only
touch `gmail/reader.py`. If you switch from GPT-4o to Claude, you only touch
`extractor/ai_extractor.py`. No other file cares.

**Human-in-the-loop where it matters**
The 50% confidence threshold is a safety valve. The agent doesn't write to live
business data unless it's confident. Low-confidence extractions go to a review
queue. This is appropriate for a financial data system where a wrong number has
real consequences.

**Self-learning fee mapping**
The `fee_dictionary` means the system gets more accurate over time without
code changes. As you add mappings, future extractions use the master names
automatically.

**Idempotent by design**
Running `main.py` twice on the same emails produces the same result — not double
the rows. The `LQA/Processed` label prevents re-reading. The `upsert` on
`pending_quotes` prevents duplicate records. The Sheets upsert replaces rather
than duplicates. You can safely re-run without damage.

**Zero infrastructure to deploy**
This runs on your laptop with `python3 main.py`. No server, no cron daemon, no
Docker container. For the current usage (manual runs), this is the right level
of complexity.

**Auditable**
Every sheet row has a `Message ID` column linking back to the original Gmail
message. Every `pending_quotes` row stores the full email body and GPT-4o output.
You can always trace a number back to its source.

---

### Cons

**GPT-4o is a black box**
You cannot predict exactly what it will extract. Two similar emails may produce
slightly different field values. The confidence score is self-reported — the
model can be confidently wrong. For a production financial system, this is a
significant risk.

**No error recovery**
One API failure crashes the entire run. Emails after the failure are not processed.
There is no retry queue, no dead-letter mechanism, no partial success handling.
A robust system would wrap each email in a try/except and continue the loop.

**Synchronous and single-threaded**
Emails are processed one at a time. Each email involves 3 API calls (Gmail fetch,
GPT-4o, Sheets write). For 10 emails this is fine. For 100 emails, the run takes
several minutes. A production system would process emails concurrently.

**Cargo matching depends on GPT-4o consistency**
The upsert logic matches on `cargo_description`. If GPT-4o describes the same
cargo differently across two emails, a new row is created instead of updating
the existing one. There is no fuzzy matching.

**No monitoring or alerting**
You only know something went wrong if you look at the terminal output. A
production system would send notifications (email, Slack) when errors occur or
when emails enter the pending review queue.

**Manual entry point**
You have to remember to run `python3 main.py`. A missed run means emails pile
up. A cron job or cloud function would eliminate this dependency on human memory.

**Single-tenant by design**
The agent is built for one Gmail account and one set of Google Sheets. Supporting
multiple users or companies would require a significant redesign — separate
credentials, separate label management, separate sheet namespacing per user.

---

## 7. Known Flaws and How to Fix Them

| Flaw | Fix |
|---|---|
| One crash stops the whole batch | Wrap the `for email in emails` loop body in `try/except`, print the error, and continue to the next email |
| `maxResults=50` silently drops emails | Implement pagination using `nextPageToken` from the list response |
| `token.json` in project root | Move to `~/.config/lqa/token.json` — out of the codebase entirely |
| Drive query injection via client name | Escape single quotes in the title before building the query string |
| No prompt injection defence | Strip or sanitise email body before including in the GPT-4o prompt |
| `SUPABASE_ANON_KEY` unused in `.env` | Delete it — dead credentials are unnecessary exposure |
| No tests | Add `pytest` tests for `_domain_from_email()`, `_map_fees()` dedup, and `_upsert_rows()` logic |
| No alerting for pending_quotes | Add a step in `main.py` to print a summary of how many items are in pending review |
| Cargo description matching is exact | Use fuzzy string matching (e.g. `rapidfuzz` library) for the upsert item lookup |
| No partial write protection | Collect all rows to write first, then write once — reduces the window for partial failures |
