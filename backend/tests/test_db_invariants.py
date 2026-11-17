"""Database-level accounting/stock integrity rules (alembic/sql/0002_v2_fixes.sql).

These run against real PostgreSQL triggers and constraints. They bypass the API on purpose:
the database must refuse bad data even if a future service has a bug.
"""
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from tests.helpers import create_company, signup


@pytest.fixture()
def cid(client):
    headers = signup(client, "owner@acme-tests.org")
    return create_company(client, headers, "Acme Traders")["id"]


def one(conn, sql, **params):
    return conn.execute(text(sql), params).scalar_one()


def make_accounts(conn, cid):
    cash = one(conn, "INSERT INTO accounts (company_id, code, name, account_type) VALUES (:c,'1000','Cash','asset') RETURNING id", c=cid)
    sales = one(conn, "INSERT INTO accounts (company_id, code, name, account_type) VALUES (:c,'4000','Sales','income') RETURNING id", c=cid)
    return cash, sales


def make_entry(conn, cid, number="JV-1", **extra):
    cols = {"entry_number": number, **extra}
    names = ", ".join(cols)
    values = ", ".join(f":{k}" for k in cols)
    return one(conn, f"INSERT INTO journal_entries (company_id, entry_date, {names}) VALUES (:c, current_date, {values}) RETURNING id",
               c=cid, **cols)


def add_line(conn, cid, entry, n, account, debit=0, credit=0):
    conn.execute(text(
        "INSERT INTO journal_lines (company_id, journal_entry_id, line_number, account_id, debit, credit) "
        "VALUES (:c,:e,:n,:a,:d,:cr)"), {"c": cid, "e": entry, "n": n, "a": account, "d": debit, "cr": credit})


# ------------------------------------------------------------------ journal
def test_unbalanced_posted_journal_is_rejected_at_commit(db_engine, cid):
    with pytest.raises(DBAPIError, match="JOURNAL_NOT_BALANCED"):
        with db_engine.begin() as conn:
            cash, sales = make_accounts(conn, cid)
            je = make_entry(conn, cid)
            add_line(conn, cid, je, 1, cash, debit=100)
            add_line(conn, cid, je, 2, sales, credit=90)
            conn.execute(text("UPDATE journal_entries SET status = 'posted' WHERE id = :e"), {"e": je})


def test_balanced_journal_commits_and_is_then_immutable(db_engine, cid):
    with db_engine.begin() as conn:
        cash, sales = make_accounts(conn, cid)
        je = make_entry(conn, cid)
        add_line(conn, cid, je, 1, cash, debit=100)
        add_line(conn, cid, je, 2, sales, credit=100)
        conn.execute(text("UPDATE journal_entries SET status = 'posted' WHERE id = :e"), {"e": je})

    with pytest.raises(DBAPIError, match="JOURNAL_IMMUTABLE"):
        with db_engine.begin() as conn:
            conn.execute(text("UPDATE journal_lines SET debit = 50 WHERE journal_entry_id = :e AND line_number = 1"), {"e": je})
    with pytest.raises(DBAPIError, match="JOURNAL_IMMUTABLE"):
        with db_engine.begin() as conn:
            conn.execute(text("DELETE FROM journal_entries WHERE id = :e"), {"e": je})
    with pytest.raises(DBAPIError, match="JOURNAL_IMMUTABLE"):
        with db_engine.begin() as conn:
            conn.execute(text("UPDATE journal_entries SET description = 'edited' WHERE id = :e"), {"e": je})

    # The one permitted change: posted -> reversed.
    with db_engine.begin() as conn:
        conn.execute(text("UPDATE journal_entries SET status = 'reversed' WHERE id = :e"), {"e": je})


def test_same_document_event_cannot_be_journaled_twice(db_engine, cid):
    source = uuid.uuid4()
    with pytest.raises(DBAPIError):
        with db_engine.begin() as conn:
            make_entry(conn, cid, "JV-1", source_type="sales_invoice", source_id=source)
            make_entry(conn, cid, "JV-2", source_type="sales_invoice", source_id=source)


# ------------------------------------------------------------------ append-only ledgers
def test_audit_events_are_append_only(db_engine, cid):
    with pytest.raises(DBAPIError, match="RECORD_IMMUTABLE"):
        with db_engine.begin() as conn:
            conn.execute(text("DELETE FROM audit_events"))
    with pytest.raises(DBAPIError, match="RECORD_IMMUTABLE"):
        with db_engine.begin() as conn:
            conn.execute(text("UPDATE audit_events SET action = 'tampered'"))


def make_stock_base(conn, cid):
    unit = one(conn, "INSERT INTO units (company_id, name, abbreviation) VALUES (:c,'Piece','pcs') RETURNING id", c=cid)
    item = one(conn, "INSERT INTO items (company_id, unit_id, name) VALUES (:c,:u,'Widget') RETURNING id", c=cid, u=unit)
    wh = one(conn, "INSERT INTO warehouses (company_id, name, is_default) VALUES (:c,'Main',true) RETURNING id", c=cid)
    return item, wh


def test_stock_movements_are_append_only(db_engine, cid):
    with db_engine.begin() as conn:
        item, wh = make_stock_base(conn, cid)
        mv = one(conn, "INSERT INTO stock_movements (company_id, item_id, warehouse_id, movement_type, quantity_delta) "
                       "VALUES (:c,:i,:w,'opening',10) RETURNING id", c=cid, i=item, w=wh)
    with pytest.raises(DBAPIError, match="RECORD_IMMUTABLE"):
        with db_engine.begin() as conn:
            conn.execute(text("UPDATE stock_movements SET quantity_delta = 99 WHERE id = :m"), {"m": mv})
    with pytest.raises(DBAPIError, match="RECORD_IMMUTABLE"):
        with db_engine.begin() as conn:
            conn.execute(text("DELETE FROM stock_movements WHERE id = :m"), {"m": mv})


def test_stock_movement_for_same_document_line_cannot_repeat(db_engine, cid):
    ref, line = uuid.uuid4(), uuid.uuid4()
    with pytest.raises(DBAPIError):
        with db_engine.begin() as conn:
            item, wh = make_stock_base(conn, cid)
            for _ in range(2):
                conn.execute(text(
                    "INSERT INTO stock_movements (company_id, item_id, warehouse_id, movement_type, quantity_delta, "
                    "reference_type, reference_id, source_line_id) "
                    "VALUES (:c,:i,:w,'sale_issue',-1,'sales_invoice',:r,:l)"),
                    {"c": cid, "i": item, "w": wh, "r": ref, "l": line})


def test_negative_stock_blocked_unless_company_allows_it(db_engine, cid):
    with db_engine.begin() as conn:
        item, wh = make_stock_base(conn, cid)

    insert = ("INSERT INTO stock_balances (company_id, item_id, warehouse_id, quantity_on_hand) "
              "VALUES (:c,:i,:w,-5)")
    with pytest.raises(DBAPIError, match="INSUFFICIENT_STOCK"):
        with db_engine.begin() as conn:
            conn.execute(text(insert), {"c": cid, "i": item, "w": wh})

    with db_engine.begin() as conn:
        conn.execute(text("UPDATE company_settings SET allow_negative_stock = true WHERE company_id = :c"), {"c": cid})
        conn.execute(text(insert), {"c": cid, "i": item, "w": wh})


# ------------------------------------------------------------------ numbering & documents
def test_document_sequence_unique_even_without_financial_period(db_engine, cid):
    insert = "INSERT INTO document_sequences (company_id, document_type) VALUES (:c, 'custom_doc')"
    with db_engine.begin() as conn:
        conn.execute(text(insert), {"c": cid})
    with pytest.raises(DBAPIError):
        with db_engine.begin() as conn:
            conn.execute(text(insert), {"c": cid})


def invoice_sql(status, number):
    return ("INSERT INTO sales_invoices (company_id, invoice_number, invoice_date, status, customer_name_snapshot, grand_total) "
            f"VALUES (:c, {number}, current_date, '{status}', 'Walk-in', 100) RETURNING id")


def test_draft_invoice_needs_no_number_but_posted_invoice_does(db_engine, cid):
    with db_engine.begin() as conn:
        one(conn, invoice_sql("draft", "NULL"), c=cid)
        one(conn, invoice_sql("draft", "NULL"), c=cid)  # many drafts without a number
    with pytest.raises(DBAPIError):
        with db_engine.begin() as conn:
            one(conn, invoice_sql("posted", "NULL"), c=cid)


# ------------------------------------------------------------------ payments
def make_payment_base(conn, cid):
    inv = one(conn, invoice_sql("posted", "'INV-0001'"), c=cid)
    acct = one(conn, "INSERT INTO payment_accounts (company_id, name, account_type) VALUES (:c,'Cash','cash') RETURNING id", c=cid)
    return inv, acct


def make_payment(conn, cid, acct, number, amount, direction="in"):
    return one(conn, "INSERT INTO payments (company_id, payment_account_id, direction, payment_number, payment_date, amount) "
                     "VALUES (:c,:a,:d,:n,current_date,:amt) RETURNING id",
               c=cid, a=acct, d=direction, n=number, amt=amount)


def allocate(conn, cid, payment, invoice, amount):
    conn.execute(text("INSERT INTO payment_allocations (company_id, payment_id, sales_invoice_id, amount) VALUES (:c,:p,:i,:a)"),
                 {"c": cid, "p": payment, "i": invoice, "a": amount})


def test_valid_allocations_commit(db_engine, cid):
    with db_engine.begin() as conn:
        inv, acct = make_payment_base(conn, cid)
        p1 = make_payment(conn, cid, acct, "RCT-1", 60)
        p2 = make_payment(conn, cid, acct, "RCT-2", 40)
        allocate(conn, cid, p1, inv, 60)
        allocate(conn, cid, p2, inv, 40)


def test_payment_cannot_be_over_allocated(db_engine, cid):
    with pytest.raises(DBAPIError, match="PAYMENT_OVER_ALLOCATED"):
        with db_engine.begin() as conn:
            inv, acct = make_payment_base(conn, cid)
            p = make_payment(conn, cid, acct, "RCT-1", 100)
            allocate(conn, cid, p, inv, 60)
            allocate(conn, cid, p, inv, 50)


def test_invoice_cannot_be_over_allocated_across_payments(db_engine, cid):
    with pytest.raises(DBAPIError, match="DOCUMENT_OVER_ALLOCATED"):
        with db_engine.begin() as conn:
            inv, acct = make_payment_base(conn, cid)
            p1 = make_payment(conn, cid, acct, "RCT-1", 100)
            p2 = make_payment(conn, cid, acct, "RCT-2", 100)
            allocate(conn, cid, p1, inv, 60)
            allocate(conn, cid, p2, inv, 60)


def test_payment_out_cannot_allocate_to_a_sales_invoice(db_engine, cid):
    with pytest.raises(DBAPIError, match="ALLOCATION_DIRECTION_MISMATCH"):
        with db_engine.begin() as conn:
            inv, acct = make_payment_base(conn, cid)
            p = make_payment(conn, cid, acct, "PAY-1", 50, direction="out")
            allocate(conn, cid, p, inv, 50)
