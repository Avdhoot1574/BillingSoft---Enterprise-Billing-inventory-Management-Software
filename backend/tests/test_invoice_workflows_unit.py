"""Isolated service regressions. Run with python -m unittest tests.test_invoice_workflows_unit."""
import unittest
from datetime import date
from decimal import Decimal as D
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

from pydantic import ValidationError
from app.api.v1.invoice_schemas import InvoiceCreate, InvoiceUpdate
from app.api.v1.payment_schemas import PaymentCreateIn
from app.core.errors import AppError
from app.modules.invoices import service
from app.modules.payments import service as payments


class InvoiceWorkflows(unittest.TestCase):
    def setUp(self):
        self.ctx = SimpleNamespace(company_id=uuid4(), tenant_id=uuid4(), user=SimpleNamespace(id=uuid4()), is_owner=True)
        self.invoice = dict(id=uuid4(), status="draft", version=1, invoice_date=date(2026, 1, 1), due_date=None,
                            grand_total=D("100"), paid_total=D("20"), other_charges=D("0"), supply_type="intra_state")
        self.db = MagicMock()
        self.db.execute.return_value.mappings.return_value.first.return_value = self.invoice
        self.db.execute.return_value.rowcount = 1

    def update(self, data):
        with patch.object(service, "record_audit"), patch.object(service, "get_invoice", return_value={"invoice": self.invoice, "lines": []}):
            return service.update_invoice(self.db, None, self.ctx, self.invoice["id"], data)

    def test_creation_persists_partial_payment(self):
        data = InvoiceCreate(invoice_date="2026-01-01", customer_name="Customer", paid_amount="25",
                             lines=[dict(item_name="Service", unit_name="Nos", quantity="1", unit_price="100")]).model_dump()
        with patch.object(service, "record_audit"), patch.object(service, "get_invoice", return_value={"invoice": self.invoice, "lines": []}):
            service.create_invoice(self.db, None, self.ctx, data)
        params = next(c.args[1] for c in self.db.execute.call_args_list if "INSERT INTO sales_invoices" in str(c.args[0]))
        self.assertEqual(params["paid_total"], D("25.00"))
        self.assertEqual(params["payment_status"], "partially_paid")
        self.assertEqual(params["grand_total"], D("100.00"))
        self.db.commit.assert_called_once()

    def test_creation_overpayment_does_not_commit(self):
        data = InvoiceCreate(invoice_date="2026-01-01", customer_name="Customer", paid_amount="101",
                             lines=[dict(item_name="Service", unit_name="Nos", quantity="1", unit_price="100")]).model_dump()
        with self.assertRaises(AppError):
            service.create_invoice(self.db, None, self.ctx, data)
        self.db.commit.assert_not_called()
        self.db.rollback.assert_called_once()

    def test_total_reduction_below_payment_rolls_back(self):
        line = dict(item_id=None, item_name="Service", unit_name="Nos", quantity=D("1"), unit_price=D("10"))
        with self.assertRaises(AppError):
            self.update({"lines": [line]})
        self.db.commit.assert_not_called()
        self.db.rollback.assert_called_once()

    def test_cross_company_warehouse_is_rejected(self):
        self.db.execute.return_value.first.return_value = None
        with self.assertRaises(AppError) as error:
            service.validate_warehouse(self.db, self.ctx, uuid4())
        self.assertEqual(error.exception.code, "WAREHOUSE_NOT_FOUND")

    def test_partial_payment_uses_existing_total(self):
        self.assertEqual(self.update({"paid_amount": D("40")}), self.invoice)
        calls = [(str(c.args[0]), c.args[1]) for c in self.db.execute.call_args_list]
        params = next(p for sql, p in calls if "UPDATE sales_invoices" in sql)
        self.assertEqual(params["payment_status"], "partially_paid")
        self.assertEqual(params["paid_amount"], D("40"))
        self.db.commit.assert_called_once()

    def test_overpayment_rolls_back(self):
        with self.assertRaises(AppError):
            self.update({"paid_amount": D("101")})
        self.db.rollback.assert_called_once()
        self.db.commit.assert_not_called()

    def test_patch_date_compares_stored_invoice_date(self):
        with self.assertRaises(AppError):
            self.update({"due_date": date(2025, 12, 31)})

    def test_customer_name_and_nullable_fields_update(self):
        self.update({"customer_name": "New customer", "due_date": None, "party_id": None})
        sql, params = next((str(c.args[0]), c.args[1]) for c in self.db.execute.call_args_list if "UPDATE sales_invoices" in str(c.args[0]))
        self.assertIn("customer_name_snapshot = :customer_name", sql)
        self.assertIn("due_date = :due_date", sql)
        self.assertIsNone(params["party_id"])

    def test_tax_change_recalculates_lines_and_payment_status(self):
        line = dict(item_id=None, item_name_snapshot="Work", sku_snapshot=None, hsn_sac_snapshot=None,
                    unit_name_snapshot="Nos", quantity=D("1"), unit_price=D("100"), discount_percent=D("10"),
                    tax_rate_percent=D("18"), warehouse_id=None)
        with patch.object(service, "record_audit"), patch.object(service, "get_invoice", return_value={"invoice": self.invoice, "lines": [line]}):
            service.update_invoice(self.db, None, self.ctx, self.invoice["id"], {"supply_type": "inter_state", "other_charges": D("5")})
        params = next(c.args[1] for c in self.db.execute.call_args_list if "UPDATE sales_invoices" in str(c.args[0]))
        self.assertEqual(params["grand_total"], D("111.20"))
        self.assertEqual(params["igst_total"], D("16.20"))
        self.assertEqual(params["cgst_total"], D("0"))
        self.assertEqual(params["payment_status"], "partially_paid")

    def test_posted_invoice_cannot_be_edited(self):
        self.invoice["status"] = "posted"
        with self.assertRaises(AppError):
            self.update({"paid_amount": D("40")})

    def test_cancel_retains_document(self):
        self.invoice["paid_total"] = D("0")
        with patch.object(service, "record_audit"):
            result = service.delete_invoice(self.db, None, self.ctx, self.invoice["id"])
        self.assertEqual(result["status"], "cancelled")
        self.assertFalse(any("DELETE FROM" in str(c.args[0]) for c in self.db.execute.call_args_list))

    def test_paid_invoice_cannot_be_cancelled(self):
        with self.assertRaises(AppError):
            service.delete_invoice(self.db, None, self.ctx, self.invoice["id"])

    def test_payment_status_boundaries(self):
        for paid, total, expected in [(0, 100, "unpaid"), (25, 100, "partially_paid"), (100, 100, "paid"), (0, 0, "paid")]:
            self.assertEqual(service.payment_status(D(paid), D(total)), expected)

    def test_posted_payment_edit_updates_status(self):
        self.invoice["status"] = "posted"
        self.db.execute.return_value.first.return_value = None
        with patch.object(service, "record_audit"), patch.object(service, "get_invoice", return_value={"invoice": self.invoice}):
            service.update_invoice_payment(self.db, None, self.ctx, self.invoice["id"], D("45"))
        params = next(c.args[1] for c in self.db.execute.call_args_list if "UPDATE sales_invoices SET paid_total" in str(c.args[0]))
        self.assertEqual(params["paid"], D("45.00"))
        self.assertEqual(params["payment_status"], "partially_paid")

    def test_posted_payment_edit_rejects_linked_allocations(self):
        self.invoice["status"] = "posted"
        self.db.execute.return_value.first.return_value = (1,)
        with self.assertRaises(AppError) as error:
            service.update_invoice_payment(self.db, None, self.ctx, self.invoice["id"], D("45"))
        self.assertEqual(error.exception.code, "INVOICE_HAS_ALLOCATIONS")
        self.db.commit.assert_not_called()

    def test_permanent_delete_removes_invoice(self):
        self.invoice["invoice_number"] = "INV-1"
        self.db.execute.return_value.first.return_value = None
        with patch.object(service, "record_audit"):
            result = service.permanently_delete_invoice(self.db, None, self.ctx, self.invoice["id"])
        self.assertTrue(result["deleted"])
        self.assertTrue(any("DELETE FROM sales_invoices" in str(c.args[0]) for c in self.db.execute.call_args_list))
        self.db.commit.assert_called_once()

    def test_invalid_schema_fields(self):
        for data in [{"paid_amount": None}, {"lines": None}, {"customer_name": "   "}, {"supply_type": "invalid"}, {"paid_amount": "NaN"}, {"paid_amount": "0.001"}]:
            with self.subTest(data=data), self.assertRaises(ValidationError):
                InvoiceUpdate(**data)

    def test_payment_allocation_validation(self):
        base = dict(payment_account_id=uuid4(), direction="in", payment_date="2026-01-01", amount="100")
        target = uuid4()
        for allocations in [[dict(purchase_bill_id=target, amount="10")], [dict(sales_invoice_id=target, amount="101")], [dict(sales_invoice_id=target, amount="20")]*2]:
            with self.assertRaises(ValidationError):
                PaymentCreateIn(**base, allocations=allocations)

    def test_payment_updates_balance_in_same_transaction(self):
        self.invoice.update(status="posted", party_id=None)
        data = dict(payment_account_id=uuid4(), party_id=None, direction="in", payment_date=date.today(), amount=D("30"),
                    allocations=[dict(sales_invoice_id=self.invoice["id"], purchase_bill_id=None, amount=D("30"))])
        with patch.object(payments, "record_audit"), patch.object(payments, "get_payment", return_value={}):
            payments.create_payment(self.db, None, self.ctx, data)
        params = next(c.args[1] for c in self.db.execute.call_args_list if "UPDATE sales_invoices" in str(c.args[0]))
        self.assertEqual(params["paid"], D("50"))
        self.assertEqual(params["state"], "partially_paid")
        self.db.commit.assert_called_once()

    def test_payment_reversal_restores_initial_amount(self):
        self.invoice.update(status="posted", paid_total=D("50"))
        self.db.execute.return_value.mappings.return_value.one.return_value = self.invoice
        self.db.execute.return_value.mappings.return_value.all.return_value = [dict(sales_invoice_id=self.invoice["id"], purchase_bill_id=None, amount=D("30"))]
        with patch.object(payments, "record_audit"), patch.object(payments, "get_payment", return_value={}):
            payments.reverse_payment(self.db, None, self.ctx, uuid4())
        params = next(c.args[1] for c in self.db.execute.call_args_list if "UPDATE sales_invoices" in str(c.args[0]))
        self.assertEqual(params["paid"], D("20"))
        self.assertEqual(params["state"], "partially_paid")

if __name__ == "__main__":
    unittest.main()
