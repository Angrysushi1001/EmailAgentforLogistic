import os
import threading

from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

load_dotenv()

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


class GoogleClient:
    _instance: "GoogleClient | None" = None
    _lock = threading.Lock()

    def __init__(self, credentials: Credentials) -> None:
        self.gmail = build("gmail", "v1", credentials=credentials)
        self.sheets = build("sheets", "v4", credentials=credentials)
        self.drive = build("drive", "v3", credentials=credentials)

    @classmethod
    def get_instance(cls) -> "GoogleClient":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls._build()
        return cls._instance

    @classmethod
    def _build(cls) -> "GoogleClient":
        creds_path = os.environ["GMAIL_OAUTH_CONFIG"]
        token_path = os.environ["GOOGLE_TOKEN_PATH"]

        creds: Credentials | None = None

        if os.path.exists(token_path):
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(creds_path, SCOPES)
                creds = flow.run_local_server(port=0)
            with open(token_path, "w") as token_file:
                token_file.write(creds.to_json())

        return cls(creds)
