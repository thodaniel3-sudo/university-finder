"""Service layer — all business logic that talks to external systems.

Routes call services; services talk to Supabase, the email provider, etc.
Keeping this boundary makes testing and swapping providers easier.
"""