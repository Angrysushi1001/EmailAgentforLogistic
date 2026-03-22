# Logistics Quote Agent (LQA)

An AI-powered automation tool that reads logistics quote emails from Gmail and extracts pricing data into client-specific Google Sheets using GPT-4o.

## What It Does

1. Reads unread emails from a Gmail label called `quotes`
2. Uses GPT-4o to extract structured pricing data (fees, amounts, units)
3. Writes the data into a Google Sheet named after the client (`Logistics_Quotes_[domain]`)
4. If the AI confidence score is ≤ 0.5, routes the email to a human review queue in Supabase instead

## Project Structure

```
.
├── main.py                  # Entry point — orchestrates the pipeline
├── auth/
│   ├── google_client.py     # Google OAuth2 singleton (Gmail + Sheets + Drive)
│   └── supabase_client.py   # Supabase singleton
├── gmail/
│   └── reader.py            # Fetch unread emails, mark as processed
├── extractor/
│   └── ai_extractor.py      # GPT-4o extraction + fee_dictionary mapping
├── sheets/
│   └── writer.py            # Find/create sheet, upsert rows
├── auth_test.py             # Sanity check — verifies all API connections
└── supabase_schema.sql      # Database table definitions
```

## Setup

### 1. Prerequisites

- Python 3.12+
- A Google Cloud project with Gmail, Sheets, and Drive APIs enabled
- A Supabase project
- An OpenAI API key

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment variables

Create a `.env` file in the project root:

```env
GMAIL_OAUTH_CONFIG=credentials.json
GOOGLE_TOKEN_PATH=token.json
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
OPENAI_API_KEY=sk-proj-...
CONFIDENCE_THRESHOLD=0.5
```

### 4. Google credentials

Download your OAuth2 credentials from Google Cloud Console and save as `credentials.json` in the project root.

### 5. Set up the database

Run the schema file against your Supabase project:

```bash
psql your-supabase-connection-string < supabase_schema.sql
```

This creates two tables:
- `pending_quotes` — holds low-confidence extractions for human review
- `fee_dictionary` — maps raw fee names from emails to normalised master names

### 6. Set up Gmail label

In Gmail, create a label called `quotes`. Then create a filter (Settings → Filters) to automatically apply it to incoming quote emails (e.g. subject contains "quote").

### 7. First run — Google authentication

On first run, a browser window will open asking you to authorise the app. After approving, a `token.json` file is saved and used for all future runs silently.

## Usage

**Verify all connections are working:**
```bash
python3 auth_test.py
```

**Run the agent:**
```bash
python3 main.py
```

**Run tests:**
```bash
pytest
```

## How Sheets Are Named

Sheets are named `Logistics_Quotes_[domain]` where domain is derived from the client's email address:

- `eugene@barry-callebaut.com` → `Logistics_Quotes_barry-callebaut`
- `raphael.yeong@lxpantos.com` → `Logistics_Quotes_lxpantos`

One sheet per client. Multiple cargo items for the same client appear as separate rows distinguished by the Item column.

## Confidence Threshold & Human Review

GPT-4o rates its own extraction confidence from 0.0 to 1.0. If the score is ≤ 0.5 (configurable via `CONFIDENCE_THRESHOLD`), the email is written to the `pending_quotes` Supabase table for manual review instead of directly to the Google Sheet.

## Fee Dictionary

The `fee_dictionary` table maps inconsistent fee names from different providers to a single master name. For example:
- "Forklift Handling In Fee" → "Handling In"
- "H/I charge" → "Handling In"

Populate this table manually as you encounter new variations. Future extractions will use the master name automatically.

## Tech Stack

| Component | Technology |
|---|---|
| Language | Python 3.12+ |
| AI extraction | OpenAI GPT-4o |
| Email | Gmail API |
| Spreadsheets | Google Sheets API + Drive API |
| Database | Supabase (PostgreSQL) |
| Auth | Google OAuth2 |
