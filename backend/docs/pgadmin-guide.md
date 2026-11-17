# Working with the database in pgAdmin

You use **pgAdmin to look at** the database and run queries, and **Alembic (from VS Code) to change** it.
Do not create or alter tables by clicking in pgAdmin: Alembic would not know about it, and the next
migration or `scripts/reset_db.py` would conflict with or erase your change. Need a change? Add a migration
(see "Changing the schema" in the README).

## 1. Connect pgAdmin to your local server (once)
1. pgAdmin -> right-click **Servers** -> Register -> Server.
2. General tab: Name = `Local`.
3. Connection tab: Host = `localhost`, Port = `5432`, Username = `postgres`, Password = the one you set
   during the PostgreSQL install. (Same values go into `DATABASE_URL` in `.env`.)
4. Check the version: open Tools -> Query Tool and run `SELECT version();`. It must say 13 or higher.

## 2. See the schema after `alembic upgrade head`
`Servers -> Local -> Databases -> billing -> Schemas -> public -> Tables` (right-click `Tables` -> Refresh, or press F5).
You should see about 80 tables. Also check:
- `public -> Functions` and each table's `Triggers` node: the integrity rules live here.
- Table `alembic_version`: one row with the migration number you are on.

```sql
SELECT version_num FROM alembic_version;        -- 0004 (or higher) when fully migrated
```

## 3. Draw the schema (ERD)
Right-click the `billing` database (or a single table) -> **ERD Tool**. Drag tables to arrange them; it is
read-only for our purposes (do not use "Generate SQL" to change the database).

## 4. Handy queries (Tools -> Query Tool)
```sql
-- Who exists, and what can they access?
SELECT u.email, c.name AS company, cm.is_owner, cm.status,
       COALESCE(string_agg(r.name, ', '), '') AS roles
FROM company_memberships cm
JOIN users u ON u.id = cm.user_id
JOIN companies c ON c.id = cm.company_id
LEFT JOIN company_member_roles cmr ON cmr.company_membership_id = cm.id
LEFT JOIN roles r ON r.id = cmr.role_id
GROUP BY u.email, c.name, cm.is_owner, cm.status;

-- Latest audit events
SELECT created_at, action, entity_type, request_id, after_data
FROM audit_events ORDER BY created_at DESC LIMIT 50;

-- Numbering set up for each company
SELECT c.name, ds.document_type, ds.prefix, ds.next_number
FROM document_sequences ds JOIN companies c ON c.id = ds.company_id ORDER BY c.name, ds.document_type;

-- Every integrity trigger the schema adds (the safety net)
SELECT event_object_table AS table_name, trigger_name
FROM information_schema.triggers WHERE trigger_schema = 'public' AND trigger_name NOT LIKE 'RI_%'
ORDER BY 1, 2;

-- Row count of every table
SELECT relname AS table_name, n_live_tup AS approx_rows
FROM pg_stat_user_tables ORDER BY relname;
```

## 5. Things that are normal
- **Tables look empty** except `permissions`: correct until you register and create a company.
- **Tests wipe `billing_test`**, never `billing`. You will see it appear/disappear tables while pytest runs.
- **Editing rows by hand is fine for experiments** (e.g. flip `allow_negative_stock` in `company_settings`).
  But posted journal lines, stock movements and audit events are protected by triggers on purpose:
  an `UPDATE`/`DELETE` on them fails with `JOURNAL_IMMUTABLE` / `RECORD_IMMUTABLE`.

## 6. Start over
`Terminal -> Run Task -> DB: RESET dev database` (or `python scripts/reset_db.py`) drops everything in `billing`
and rebuilds it from the migrations. Then press F5 on the Tables node in pgAdmin.
