grant usage on schema public to service_role;
grant select, insert, update on table public.students to service_role;
grant select on table public.admins to service_role;
grant select, insert on table public.transactions to service_role;
grant delete on table public.students to service_role;