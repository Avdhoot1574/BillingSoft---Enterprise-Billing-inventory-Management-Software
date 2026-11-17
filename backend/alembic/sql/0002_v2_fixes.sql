-- 0002 - Schema v2 fixes on top of the baseline.
-- Works on PostgreSQL 13 or newer.
-- Error messages start with a stable CODE: prefix; the API maps these to structured errors.

------------------------------------------------------------------------
-- 1. Document numbering
------------------------------------------------------------------------
-- Baseline UNIQUE (company_id, document_type, financial_period_id) lets duplicates through when the
-- period is NULL (NULLs are distinct). Replace it with a unique index that treats NULL as one value
-- (COALESCE trick: works on every PostgreSQL version, unlike NULLS NOT DISTINCT which needs 15+).
DO $$
DECLARE c text;
BEGIN
    FOR c IN SELECT conname FROM pg_constraint
             WHERE conrelid = 'document_sequences'::regclass AND contype = 'u'
    LOOP
        EXECUTE format('ALTER TABLE document_sequences DROP CONSTRAINT %I', c);
    END LOOP;
END $$;
CREATE UNIQUE INDEX uq_document_sequences_scope ON document_sequences
    (company_id, document_type,
     COALESCE(financial_period_id, '00000000-0000-0000-0000-000000000000'::uuid));

-- Drafts must not consume a number: number is assigned at posting time.
ALTER TABLE sales_invoices  ALTER COLUMN invoice_number DROP NOT NULL;
ALTER TABLE purchase_bills  ALTER COLUMN bill_number    DROP NOT NULL;

------------------------------------------------------------------------
-- 2. Lifecycle status vs payment status
------------------------------------------------------------------------
-- 'status' = lifecycle only (draft | posted | cancelled).
-- 'payment_status' = derived from allocations (unpaid | partially_paid | paid).
-- 'overdue' is never stored: compute it from due_date + payment_status.
ALTER TABLE sales_invoices
    ADD COLUMN payment_status text NOT NULL DEFAULT 'unpaid'
        CHECK (payment_status IN ('unpaid','partially_paid','paid')),
    ADD COLUMN version integer NOT NULL DEFAULT 1,
    ADD COLUMN reverse_charge boolean NOT NULL DEFAULT false,
    ADD COLUMN einvoice_status text NOT NULL DEFAULT 'not_applicable'
        CHECK (einvoice_status IN ('not_applicable','pending','generated','cancelled','failed')),
    ADD COLUMN einvoice_irn text,
    ADD COLUMN einvoice_ack_no text,
    ADD COLUMN einvoice_ack_at timestamptz,
    ADD COLUMN einvoice_qr text,
    ADD CONSTRAINT chk_sales_invoice_status CHECK (status IN ('draft','posted','cancelled')),
    ADD CONSTRAINT chk_sales_invoice_number_when_posted CHECK (status = 'draft' OR invoice_number IS NOT NULL),
    ADD CONSTRAINT chk_sales_invoice_paid_le_total CHECK (paid_total <= grand_total);

ALTER TABLE purchase_bills
    ADD COLUMN payment_status text NOT NULL DEFAULT 'unpaid'
        CHECK (payment_status IN ('unpaid','partially_paid','paid')),
    ADD COLUMN version integer NOT NULL DEFAULT 1,
    ADD COLUMN reverse_charge boolean NOT NULL DEFAULT false,
    ADD CONSTRAINT chk_purchase_bill_status CHECK (status IN ('draft','posted','cancelled')),
    ADD CONSTRAINT chk_purchase_bill_number_when_posted CHECK (status = 'draft' OR bill_number IS NOT NULL),
    ADD CONSTRAINT chk_purchase_bill_paid_le_total CHECK (paid_total <= grand_total);

-- Optimistic locking for master data edited concurrently.
ALTER TABLE parties ADD COLUMN version integer NOT NULL DEFAULT 1;
ALTER TABLE items   ADD COLUMN version integer NOT NULL DEFAULT 1;

------------------------------------------------------------------------
-- 3. Ledger wiring tables
------------------------------------------------------------------------
-- Which ledger account each business event posts to (sales revenue, output CGST, receivables, ...).
-- Keys are defined in application code (app/modules/accounting, added in step 3).
CREATE TABLE account_mappings (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    mapping_key text NOT NULL,
    account_id uuid NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (company_id, mapping_key),
    FOREIGN KEY (company_id, account_id) REFERENCES accounts(company_id, id) ON DELETE RESTRICT
);

-- Cash/bank accounts must post to a ledger account.
ALTER TABLE payment_accounts ADD COLUMN ledger_account_id uuid;
ALTER TABLE payment_accounts
    ADD CONSTRAINT fk_payment_accounts_ledger
    FOREIGN KEY (company_id, ledger_account_id) REFERENCES accounts(company_id, id) ON DELETE RESTRICT;

-- E-way bill records (generation itself requires an approved provider integration).
CREATE TABLE eway_bills (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    sales_invoice_id uuid NOT NULL,
    eway_bill_number text,
    status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','generated','cancelled','failed')),
    vehicle_number text,
    transporter_id text,
    transporter_name text,
    distance_km integer CHECK (distance_km IS NULL OR distance_km >= 0),
    valid_until timestamptz,
    provider_reference text,
    raw_response jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (company_id, id),
    FOREIGN KEY (company_id, sales_invoice_id) REFERENCES sales_invoices(company_id, id) ON DELETE RESTRICT
);

------------------------------------------------------------------------
-- 4. Idempotent posting (double-post protection) and batch-ready movements
------------------------------------------------------------------------
ALTER TABLE stock_movements
    ADD COLUMN source_line_id uuid,
    ADD COLUMN batch_no text,
    ADD COLUMN expiry_date date;

-- One movement per (document, line, type): a retried post cannot write stock twice.
CREATE UNIQUE INDEX uq_stock_movements_source
    ON stock_movements (company_id, reference_type, reference_id, movement_type, source_line_id)
    WHERE reference_id IS NOT NULL AND source_line_id IS NOT NULL;

-- One journal entry per (document, event). Reversals are exempt (they point at the original).
ALTER TABLE journal_entries ADD COLUMN source_event text NOT NULL DEFAULT 'post';
CREATE UNIQUE INDEX uq_journal_entries_source
    ON journal_entries (company_id, source_type, source_id, source_event)
    WHERE source_type IS NOT NULL AND source_id IS NOT NULL AND reversal_of_id IS NULL;

------------------------------------------------------------------------
-- 5. Journal integrity
------------------------------------------------------------------------
-- Application contract: insert the entry as 'draft', insert its lines, then UPDATE status to 'posted'.
CREATE FUNCTION fn_assert_journal_balanced(p_entry uuid) RETURNS void
LANGUAGE plpgsql AS $$
DECLARE
    v_status journal_status;
    v_debit numeric;
    v_credit numeric;
    v_lines integer;
BEGIN
    SELECT status INTO v_status FROM journal_entries WHERE id = p_entry;
    IF NOT FOUND OR v_status = 'draft' THEN
        RETURN;
    END IF;
    SELECT COALESCE(SUM(debit), 0), COALESCE(SUM(credit), 0), COUNT(*)
      INTO v_debit, v_credit, v_lines
      FROM journal_lines WHERE journal_entry_id = p_entry;
    IF v_lines < 2 THEN
        RAISE EXCEPTION 'JOURNAL_NOT_BALANCED: posted journal entry % needs at least two lines', p_entry
            USING ERRCODE = '23514';
    END IF;
    IF v_debit <> v_credit THEN
        RAISE EXCEPTION 'JOURNAL_NOT_BALANCED: debits % <> credits % for entry %', v_debit, v_credit, p_entry
            USING ERRCODE = '23514';
    END IF;
END $$;

CREATE FUNCTION fn_journal_lines_balance_trg() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        PERFORM fn_assert_journal_balanced(OLD.journal_entry_id);
    ELSE
        PERFORM fn_assert_journal_balanced(NEW.journal_entry_id);
    END IF;
    RETURN NULL;
END $$;

CREATE FUNCTION fn_journal_entries_balance_trg() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    PERFORM fn_assert_journal_balanced(NEW.id);
    RETURN NULL;
END $$;

-- Deferred: checked at COMMIT, so lines can be inserted in any order inside the transaction.
CREATE CONSTRAINT TRIGGER trg_journal_lines_balanced
    AFTER INSERT OR UPDATE OR DELETE ON journal_lines
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
    EXECUTE FUNCTION fn_journal_lines_balance_trg();

CREATE CONSTRAINT TRIGGER trg_journal_entries_balanced
    AFTER INSERT OR UPDATE ON journal_entries
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
    EXECUTE FUNCTION fn_journal_entries_balance_trg();

-- Posted journal lines are immutable.
CREATE FUNCTION fn_journal_lines_guard() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    v_entry uuid;
    v_status journal_status;
BEGIN
    v_entry := CASE WHEN TG_OP = 'DELETE' THEN OLD.journal_entry_id ELSE NEW.journal_entry_id END;
    SELECT status INTO v_status FROM journal_entries WHERE id = v_entry;
    IF FOUND AND v_status <> 'draft' THEN
        RAISE EXCEPTION 'JOURNAL_IMMUTABLE: lines of a posted journal entry cannot be changed; post a reversal instead'
            USING ERRCODE = '23514';
    END IF;
    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;
    RETURN NEW;
END $$;

CREATE TRIGGER trg_journal_lines_guard
    BEFORE INSERT OR UPDATE OR DELETE ON journal_lines
    FOR EACH ROW EXECUTE FUNCTION fn_journal_lines_guard();

-- Posted journal entries: only posted -> reversed is allowed; nothing else may change.
CREATE FUNCTION fn_journal_entries_guard() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        IF OLD.status <> 'draft' THEN
            RAISE EXCEPTION 'JOURNAL_IMMUTABLE: posted journal entries cannot be deleted; post a reversal instead'
                USING ERRCODE = '23514';
        END IF;
        RETURN OLD;
    END IF;
    IF OLD.status = 'draft' THEN
        RETURN NEW;
    END IF;
    IF (to_jsonb(NEW) - 'status' - 'created_by' - 'posted_by')
       IS DISTINCT FROM (to_jsonb(OLD) - 'status' - 'created_by' - 'posted_by') THEN
        RAISE EXCEPTION 'JOURNAL_IMMUTABLE: posted journal entries cannot be edited; post a reversal instead'
            USING ERRCODE = '23514';
    END IF;
    IF NEW.status = OLD.status OR (OLD.status = 'posted' AND NEW.status = 'reversed') THEN
        RETURN NEW;
    END IF;
    RAISE EXCEPTION 'JOURNAL_IMMUTABLE: invalid status change % -> %', OLD.status, NEW.status
        USING ERRCODE = '23514';
END $$;

CREATE TRIGGER trg_journal_entries_guard
    BEFORE UPDATE OR DELETE ON journal_entries
    FOR EACH ROW EXECUTE FUNCTION fn_journal_entries_guard();

------------------------------------------------------------------------
-- 6. Append-only ledgers: stock movements and audit events
------------------------------------------------------------------------
-- Only the "who" foreign keys may be nulled (ON DELETE SET NULL when a user is removed).
CREATE FUNCTION fn_stock_movements_guard() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'RECORD_IMMUTABLE: stock movements are append-only; post a correcting movement instead'
            USING ERRCODE = '23514';
    END IF;
    IF (to_jsonb(NEW) - 'created_by') IS DISTINCT FROM (to_jsonb(OLD) - 'created_by') THEN
        RAISE EXCEPTION 'RECORD_IMMUTABLE: stock movements are append-only; post a correcting movement instead'
            USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END $$;

CREATE TRIGGER trg_stock_movements_guard
    BEFORE UPDATE OR DELETE ON stock_movements
    FOR EACH ROW EXECUTE FUNCTION fn_stock_movements_guard();

CREATE FUNCTION fn_audit_events_guard() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'RECORD_IMMUTABLE: audit events are append-only'
            USING ERRCODE = '23514';
    END IF;
    IF (to_jsonb(NEW) - 'tenant_id' - 'company_id' - 'actor_user_id')
       IS DISTINCT FROM (to_jsonb(OLD) - 'tenant_id' - 'company_id' - 'actor_user_id') THEN
        RAISE EXCEPTION 'RECORD_IMMUTABLE: audit events are append-only'
            USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END $$;

CREATE TRIGGER trg_audit_events_guard
    BEFORE UPDATE OR DELETE ON audit_events
    FOR EACH ROW EXECUTE FUNCTION fn_audit_events_guard();

------------------------------------------------------------------------
-- 7. Negative stock policy (per company setting)
------------------------------------------------------------------------
CREATE FUNCTION fn_stock_balance_non_negative() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE v_allow boolean;
BEGIN
    IF NEW.quantity_on_hand < 0 THEN
        SELECT allow_negative_stock INTO v_allow FROM company_settings WHERE company_id = NEW.company_id;
        IF COALESCE(v_allow, false) = false THEN
            RAISE EXCEPTION 'INSUFFICIENT_STOCK: stock for item % in warehouse % would become %',
                NEW.item_id, NEW.warehouse_id, NEW.quantity_on_hand
                USING ERRCODE = '23514';
        END IF;
    END IF;
    RETURN NEW;
END $$;

CREATE TRIGGER trg_stock_balance_non_negative
    BEFORE INSERT OR UPDATE OF quantity_on_hand ON stock_balances
    FOR EACH ROW EXECUTE FUNCTION fn_stock_balance_non_negative();

------------------------------------------------------------------------
-- 8. Payment allocation integrity
------------------------------------------------------------------------
-- Verified at COMMIT (deferred): direction matches the document type (in -> sales invoice,
-- out -> purchase bill), and neither the payment nor the document is over-allocated.
CREATE FUNCTION fn_check_payment_allocation() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    v_dir payment_direction;
    v_amount numeric;
    v_alloc numeric;
    v_doc_total numeric;
    v_doc_alloc numeric;
BEGIN
    SELECT direction, amount INTO v_dir, v_amount
      FROM payments WHERE company_id = NEW.company_id AND id = NEW.payment_id;
    IF NOT FOUND THEN
        RETURN NULL;   -- payment deleted in same transaction (cascade)
    END IF;

    IF v_dir = 'in' AND NEW.sales_invoice_id IS NULL THEN
        RAISE EXCEPTION 'ALLOCATION_DIRECTION_MISMATCH: a payment-in can only be allocated to sales invoices'
            USING ERRCODE = '23514';
    END IF;
    IF v_dir = 'out' AND NEW.purchase_bill_id IS NULL THEN
        RAISE EXCEPTION 'ALLOCATION_DIRECTION_MISMATCH: a payment-out can only be allocated to purchase bills'
            USING ERRCODE = '23514';
    END IF;

    SELECT COALESCE(SUM(amount), 0) INTO v_alloc
      FROM payment_allocations WHERE company_id = NEW.company_id AND payment_id = NEW.payment_id;
    IF v_alloc > v_amount THEN
        RAISE EXCEPTION 'PAYMENT_OVER_ALLOCATED: allocated % exceeds payment amount %', v_alloc, v_amount
            USING ERRCODE = '23514';
    END IF;

    IF NEW.sales_invoice_id IS NOT NULL THEN
        SELECT grand_total INTO v_doc_total
          FROM sales_invoices WHERE company_id = NEW.company_id AND id = NEW.sales_invoice_id;
        SELECT COALESCE(SUM(pa.amount), 0) INTO v_doc_alloc
          FROM payment_allocations pa
          JOIN payments p ON p.company_id = pa.company_id AND p.id = pa.payment_id
         WHERE pa.company_id = NEW.company_id AND pa.sales_invoice_id = NEW.sales_invoice_id
           AND p.status <> 'reversed';
    ELSE
        SELECT grand_total INTO v_doc_total
          FROM purchase_bills WHERE company_id = NEW.company_id AND id = NEW.purchase_bill_id;
        SELECT COALESCE(SUM(pa.amount), 0) INTO v_doc_alloc
          FROM payment_allocations pa
          JOIN payments p ON p.company_id = pa.company_id AND p.id = pa.payment_id
         WHERE pa.company_id = NEW.company_id AND pa.purchase_bill_id = NEW.purchase_bill_id
           AND p.status <> 'reversed';
    END IF;
    IF v_doc_alloc > v_doc_total THEN
        RAISE EXCEPTION 'DOCUMENT_OVER_ALLOCATED: allocated % exceeds document total %', v_doc_alloc, v_doc_total
            USING ERRCODE = '23514';
    END IF;
    RETURN NULL;
END $$;

CREATE CONSTRAINT TRIGGER trg_payment_allocation_check
    AFTER INSERT OR UPDATE ON payment_allocations
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
    EXECUTE FUNCTION fn_check_payment_allocation();

------------------------------------------------------------------------
-- 9. updated_at maintenance for every table that has the column
------------------------------------------------------------------------
CREATE FUNCTION fn_set_updated_at() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at := now();
    RETURN NEW;
END $$;

DO $$
DECLARE r record;
BEGIN
    FOR r IN
        SELECT c.table_name
          FROM information_schema.columns c
          JOIN information_schema.tables t
            ON t.table_schema = c.table_schema AND t.table_name = c.table_name
         WHERE c.table_schema = 'public' AND c.column_name = 'updated_at' AND t.table_type = 'BASE TABLE'
    LOOP
        EXECUTE format(
            'CREATE TRIGGER trg_%s_updated_at BEFORE UPDATE ON %I FOR EACH ROW EXECUTE FUNCTION fn_set_updated_at()',
            r.table_name, r.table_name);
    END LOOP;
END $$;
