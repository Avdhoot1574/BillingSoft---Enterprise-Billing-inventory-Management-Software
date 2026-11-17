"""add billing and reporting indexes

Revision ID: 0005
Revises: 0004
"""

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_sales_invoices_company_date
        ON sales_invoices (company_id, invoice_date DESC)
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_sales_invoices_company_status
        ON sales_invoices (company_id, status)
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_sales_invoices_company_party
        ON sales_invoices (company_id, party_id)
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_payments_company_date
        ON payments (company_id, payment_date DESC)
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_payments_company_direction
        ON payments (company_id, direction, status)
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_payment_allocations_invoice
        ON payment_allocations (company_id, sales_invoice_id)
        WHERE sales_invoice_id IS NOT NULL
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_payment_allocations_bill
        ON payment_allocations (company_id, purchase_bill_id)
        WHERE purchase_bill_id IS NOT NULL
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_stock_movements_company_item_date
        ON stock_movements (company_id, item_id, occurred_at DESC)
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_stock_movements_company_warehouse_date
        ON stock_movements (company_id, warehouse_id, occurred_at DESC)
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_stock_movements_company_warehouse_date")
    op.execute("DROP INDEX IF EXISTS ix_stock_movements_company_item_date")
    op.execute("DROP INDEX IF EXISTS ix_payment_allocations_bill")
    op.execute("DROP INDEX IF EXISTS ix_payment_allocations_invoice")
    op.execute("DROP INDEX IF EXISTS ix_payments_company_direction")
    op.execute("DROP INDEX IF EXISTS ix_payments_company_date")
    op.execute("DROP INDEX IF EXISTS ix_sales_invoices_company_party")
    op.execute("DROP INDEX IF EXISTS ix_sales_invoices_company_status")
    op.execute("DROP INDEX IF EXISTS ix_sales_invoices_company_date")