import os
import threading

from dotenv import load_dotenv
from supabase import Client, create_client

load_dotenv()


class SupabaseClient:
    _instance: "Client | None" = None
    _lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> Client:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    url = os.environ["SUPABASE_URL"]
                    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
                    cls._instance = create_client(url, key)
        return cls._instance
