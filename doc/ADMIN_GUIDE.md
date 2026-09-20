# Admin Guide

This guide explains how to manage University Finder as an administrator.

---

## Becoming an admin

Admin access is controlled by the `is_admin` column on your
`student_profiles` row.

### To promote yourself (development)

1. Log into the app so a profile row is created for you.
2. Open Supabase -> SQL Editor.
3. Run:

```sql
update public.student_profiles
set is_admin = true
where user_id = '<your-user-id>';