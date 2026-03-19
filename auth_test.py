"""
Sanity check: verifies all three external connections are functional.
Run with: python auth_test.py
"""

import sys

from auth import GoogleClient, SupabaseClient


def check_gmail() -> None:
    print("Checking Gmail...", end=" ")
    service = GoogleClient.get_instance().gmail
    result = service.users().labels().list(userId="me").execute()
    label_count = len(result.get("labels", []))
    print(f"OK ({label_count} labels found)")


def check_sheets() -> None:
    print("Checking Sheets...", end=" ")
    service = GoogleClient.get_instance().sheets
    # Calling spreadsheets.get with a non-existent ID returns a 404, not a 401.
    # A 401 would mean auth failed. We treat any non-auth error as a pass.
    try:
        service.spreadsheets().get(spreadsheetId="sanity-check-id").execute()
    except Exception as exc:
        error = str(exc)
        if "401" in error or "invalid_grant" in error:
            raise RuntimeError(f"Sheets auth failed: {error}") from exc
        print(f"OK (auth valid, expected API error: {error[:60]})")
        return
    print("OK")


def check_drive() -> None:
    print("Checking Drive...", end=" ")
    service = GoogleClient.get_instance().drive
    result = service.files().list(pageSize=1, fields="files(id,name)").execute()
    print(f"OK ({len(result.get('files', []))} file(s) visible)")


def check_supabase() -> None:
    print("Checking Supabase...", end=" ")
    client = SupabaseClient.get_instance()
    result = client.table("fee_dictionary").select("id").limit(1).execute()
    print(f"OK ({len(result.data)} row(s) returned from fee_dictionary)")


def main() -> None:
    checks = [check_gmail, check_sheets, check_drive, check_supabase]
    failed = False
    for check in checks:
        try:
            check()
        except Exception as exc:
            print(f"FAILED — {exc}")
            failed = True
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
