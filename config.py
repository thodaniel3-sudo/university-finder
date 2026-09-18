import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")

    # Supabase (will be used from Phase 5 onward)
    SUPABASE_URL = os.getenv("SUPABASE_URL", "")
    SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")
    SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

    # Email (will be used from Phase 16 onward)
    EMAIL_API_KEY = os.getenv("EMAIL_API_KEY", "")
    EMAIL_FROM = os.getenv("EMAIL_FROM", "")