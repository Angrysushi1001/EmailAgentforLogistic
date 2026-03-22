# Logistics Quote Agent (LQA)

## WHAT (Project Context)
This is an AI-powered logistics automation tool that extracts pricing data from emails into client-specific Google Sheets. It uses a Human-in-the-Loop (HITL) system with a 50% confidence threshold.

## HOW (Tech Stack & Architecture)
- **Language:** Python 3.12+
- **Database:** Supabase (tables: `pending_quotes`, `fee_dictionary`)
- **APIs:** Gmail (peek/read), Sheets (upsert), OpenAI (GPT-4o)
- **Rules:** Follow `VIBE-CODE-RULES.md` for all implementations.

## COMMANDS (Useful for Claude)
- Run sanity check: `python3 auth_test.py`
- Start agent: `python3 main.py`
- Run tests: `pytest`

## USER CONTEXT
- **User:** Raphael Yeong (`raphael.yeong@lxpantos.com`) — logistics/freight forwarder at lxpantos.
- Raphael receives quote emails FROM warehouse/logistics providers (e.g. GKE Group).
- These quotes are FOR a client — the company that **requested** the service.
- If Raphael himself sent the original request, the client is **lxpantos** (`lxpantos`).
- If a third party (e.g. Barry Callebaut) sent the original request, the client is that company.

## ARCHITECTURE DECISIONS
- **Confidence Threshold:** If extraction score <= 0.5, write to `pending_quotes` only.
- **Self-Learning:** Use `fee_dictionary` to map messy email names to master terms.
- **Sheet Naming:** `Logistics_Quotes_[domain]` where domain = first part of the client's email (e.g. `eugene@barry-callebaut.com` → `barry-callebaut`, `raphael.yeong@lxpantos.com` → `lxpantos`). Never use CC'd addresses for naming.
- **Storage:** One Google Sheet per client domain; append new quotes as rows. Multiple cargo items for the same client go in the same sheet, distinguished by the Item column.
- **Upsert Logic:** If a cargo item already exists in the sheet (matched by Item column), overwrite those rows. If new, append.
