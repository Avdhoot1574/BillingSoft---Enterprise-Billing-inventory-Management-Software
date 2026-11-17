# Schema v2 changes (migration 0002 + 0003)

The original schema is kept untouched as `0001_baseline.sql`. Everything below is applied on top, so the diff is reviewable.

| # | Problem in baseline | Fix | Enforced by |
|---|---|---|---|
| 1 | `document_sequences` unique key allowed duplicates when `financial_period_id` is NULL | Unique index on `COALESCE(financial_period_id, zero-uuid)` (works on PostgreSQL 13+) | unique index |
| 2 | Drafts had to consume an invoice/bill number | `invoice_number` / `bill_number` nullable; mandatory once status is not `draft` | CHECK |
| 3 | `status` mixed lifecycle and payment state | `status` limited to draft/posted/cancelled; new `payment_status` (unpaid/partially_paid/paid); `overdue` is computed, never stored | CHECK |
| 4 | Journal balance only described in a comment | Deferred constraint triggers: posted entry needs >= 2 lines and debits = credits, checked at COMMIT | trigger |
| 5 | Posted journals could be edited/deleted | Lines frozen once entry is posted; entry may only go posted -> reversed | trigger |
| 6 | Stock movements and audit events could be edited | Append-only (only "who" FKs may be nulled when a user is deleted) | trigger |
| 7 | Negative stock possible | `stock_balances` rejects negative quantity unless `company_settings.allow_negative_stock` | trigger |
| 8 | Payments could be over-allocated or allocated to the wrong document type | Direction check, payment-level and document-level over-allocation check at COMMIT | trigger |
| 9 | Retried posting could write twice | Unique (document, line, movement type) on stock movements; unique (document, event) on journal entries | partial unique index |
| 10 | No way to know which ledger account a sale/purchase/tax posts to | `account_mappings`; `payment_accounts.ledger_account_id` | new table / column |
| 11 | No optimistic locking | `version` on sales_invoices, purchase_bills, parties, items | column |
| 12 | `paid_total` could exceed `grand_total` | CHECK | constraint |
| 13 | E-invoice / e-way bill / reverse charge had nowhere to live | IRN, ack no/date, QR, status columns; `eway_bills` table; `reverse_charge` flag | columns / table |
| 14 | Batch/expiry would need a risky migration later | nullable `batch_no`, `expiry_date`, `source_line_id` on stock movements | columns |
| 15 | `updated_at` never changed | Trigger on every table that has the column | trigger |
| 16 | No sessions / invitations / lockout | `user_sessions`, `invitations`, `users.failed_login_count`, `users.locked_until` | 0003 |

## Correction to my earlier review
I said `party_opening_balances` was missing. It is not needed: `parties` already carries `opening_balance` and
`opening_balance_side`. What is still required (step 3/4) is that saving an opening balance writes a journal entry.

## Contract for the posting service (step 3)
1. Insert `journal_entries` as `draft`, insert all `journal_lines`, then `UPDATE ... SET status = 'posted'`.
   Inserting lines into an already-posted entry is rejected by design.
2. Set `source_type` / `source_id` / `source_event` so a retry cannot double-post.
3. Set `reference_type` / `reference_id` / `source_line_id` on stock movements for the same reason.
4. Update `stock_balances` only together with a `stock_movements` row, in the same transaction.

## Not done yet (deliberately)
- Row-level security (needs a session-variable design; API scoping is the primary control for now).
- Posted-invoice immutability trigger (depends on the posting service's exact update pattern).
- Allocation to credit notes / sales returns.
- Per-financial-year invoice number uniqueness (baseline is stricter: unique per company; fine while prefixes include the year).
