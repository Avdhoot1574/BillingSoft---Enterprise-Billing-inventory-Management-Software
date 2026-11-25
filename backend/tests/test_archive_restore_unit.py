"""Archive recovery remains scoped to the current company."""

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

from app.modules.master_data import service as master_data
from app.modules.parties import service as parties


class ArchiveRestoreTests(unittest.TestCase):
    def setUp(self):
        self.ctx = SimpleNamespace(company_id=uuid4(), tenant_id=uuid4(), user=SimpleNamespace(id=uuid4()))
        self.record_id = uuid4()
        self.db = MagicMock()

    def test_restoring_party_updates_only_current_company_and_audits(self):
        before = {"id": self.record_id, "is_archived": True, "name": "Customer"}
        after = {**before, "is_archived": False}
        with patch.object(parties, "_party_or_404", side_effect=[before, after]), \
             patch.object(parties, "_party_detail", return_value={**after, "addresses": []}), \
             patch.object(parties, "record_audit") as audit:
            result = parties.restore_party(self.db, None, self.ctx, self.record_id)
        self.assertFalse(result["is_archived"])
        params = self.db.execute.call_args.args[1]
        self.assertEqual(params["company_id"], self.ctx.company_id)
        self.assertEqual(params["party_id"], self.record_id)
        self.assertFalse(params["archived"])
        self.assertEqual(audit.call_args.kwargs["action"], "party.restored")
        self.db.commit.assert_called_once()

    def test_restoring_item_updates_only_current_company_and_audits(self):
        before = {"id": self.record_id, "is_archived": True, "name": "Item"}
        self.db.execute.return_value.mappings.return_value.one.return_value = {**before, "is_archived": False}
        with patch.object(master_data, "_get_one", return_value=before), \
             patch.object(master_data, "record_audit") as audit:
            result = master_data.restore_item(self.db, None, self.ctx, self.record_id)
        self.assertFalse(result["is_archived"])
        params = self.db.execute.call_args.args[1]
        self.assertEqual(params["company_id"], self.ctx.company_id)
        self.assertEqual(params["id"], self.record_id)
        self.assertFalse(params["archived"])
        self.assertEqual(audit.call_args.kwargs["action"], "items.restore")
        self.db.commit.assert_called_once()

    def test_item_list_can_show_only_archived_records(self):
        self.db.execute.return_value.mappings.return_value.all.return_value = []
        master_data.list_records(self.db, self.ctx, "items", archived_only=True)
        query = str(self.db.execute.call_args.args[0])
        self.assertIn("is_archived = true", query)
        self.assertEqual(self.db.execute.call_args.args[1]["company_id"], self.ctx.company_id)

    def test_party_list_can_show_only_archived_records(self):
        self.db.execute.return_value.mappings.return_value.all.return_value = []
        parties.list_parties(self.db, self.ctx, search=None, kind=None, include_archived=False,
                            archived_only=True, limit=100, offset=0)
        self.assertTrue(self.db.execute.call_args.args[1]["archived_only"])
        self.assertEqual(self.db.execute.call_args.args[1]["company_id"], self.ctx.company_id)


if __name__ == "__main__":
    unittest.main()
