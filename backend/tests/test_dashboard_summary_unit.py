"""Dashboard totals use all company records and only posted invoice value."""

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

from app.modules.dashboard import service


class DashboardSummaryTests(unittest.TestCase):
    def test_summary_uses_scoped_counts_and_posted_value(self):
        company_id = uuid4()
        ctx = SimpleNamespace(company_id=company_id, has=lambda permission: True)
        db = MagicMock()

        def execute(query, params):
            self.assertEqual(params["company_id"], company_id)
            sql = str(query)
            result = MagicMock()
            if "FROM sales_invoices" in sql:
                self.assertIn("status = 'posted'", sql)
                result.mappings.return_value.one.return_value = {
                    "invoice_count": 23,
                    "posted_invoice_value": 1200,
                }
            elif "FROM parties" in sql:
                self.assertIn("is_archived = false", sql)
                result.scalar_one.return_value = 12
            elif "FROM items" in sql:
                self.assertIn("is_archived = false", sql)
                result.scalar_one.return_value = 35
            else:
                self.fail(sql)
            return result

        db.execute.side_effect = execute
        with patch.object(service, "list_invoices", return_value=[{"id": "recent"}]) as recent:
            result = service.summary(db, ctx)

        self.assertEqual(result["invoice_count"], 23)
        self.assertEqual(result["party_count"], 12)
        self.assertEqual(result["item_count"], 35)
        self.assertEqual(result["posted_invoice_value"], 1200)
        self.assertEqual(result["recent_invoices"], [{"id": "recent"}])
        recent.assert_called_once_with(db, ctx, limit=5)

    def test_summary_does_not_expose_data_without_read_permissions(self):
        ctx = SimpleNamespace(company_id=uuid4(), has=lambda permission: False)
        db = MagicMock()
        result = service.summary(db, ctx)
        self.assertEqual(result, {
            "invoice_count": None,
            "party_count": None,
            "item_count": None,
            "posted_invoice_value": None,
            "recent_invoices": None,
        })
        db.execute.assert_not_called()


if __name__ == "__main__":
    unittest.main()
