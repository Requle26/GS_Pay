grant usage on schema public to service_role;
grant select, insert, update on table public.students to service_role;
grant select, insert, update on table public.admins to service_role;
grant select, insert on table public.transactions to service_role;
grant delete on table public.students to service_role;
grant select, insert, update, delete on table public.menus to service_role;
grant select, insert, update on table public.booths to service_role;

-- Harden: ensure anon/authenticated cannot touch money tables directly.
-- Run after enabling RLS on each table in the Supabase dashboard if not already on.
revoke all on table public.students from anon, authenticated;
revoke all on table public.admins from anon, authenticated;
revoke all on table public.transactions from anon, authenticated;
revoke all on table public.menus from anon, authenticated;
revoke all on table public.booths from anon, authenticated;
