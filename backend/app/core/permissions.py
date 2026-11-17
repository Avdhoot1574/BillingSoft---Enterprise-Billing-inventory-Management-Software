"""Permission catalogue and default system roles.

Permission keys follow `<area>.<object>.<action>`. They are checked in the API layer
(see app/api/deps.py: require_permission) - never only in the UI.
"""

PERMISSIONS: dict[str, str] = {
    # Company & users
    "settings.company.read": "View company profile and settings",
    "settings.company.manage": "Edit company profile and settings",
    "settings.users.manage": "Invite, change roles of, and remove staff",
    "audit.read": "View the audit trail",
    # Parties & items
    "parties.read": "View customers and suppliers",
    "parties.create": "Create customers and suppliers",
    "parties.update": "Edit customers and suppliers",
    "parties.archive": "Archive customers and suppliers",
    "items.read": "View items and sale prices",
    "items.cost.read": "View purchase cost / margin of items",
    "items.create": "Create items",
    "items.update": "Edit items",
    "items.archive": "Archive items",
    # Sales
    "sales.invoice.read": "View sales invoices",
    "sales.invoice.create": "Create sales invoice drafts",
    "sales.invoice.post": "Post sales invoices",
    "sales.invoice.cancel": "Cancel posted sales invoices",
    "sales.return.create": "Create sales returns / credit notes",
    "sales.quotation.manage": "Manage quotations, orders and delivery challans",
    # Purchases
    "purchase.bill.read": "View purchase bills",
    "purchase.bill.create": "Create purchase bill drafts",
    "purchase.bill.post": "Post purchase bills",
    "purchase.bill.cancel": "Cancel posted purchase bills",
    "purchase.return.create": "Create purchase returns / debit notes",
    "purchase.order.manage": "Manage purchase orders",
    # Payments & expenses
    "payments.read": "View payments and receipts",
    "payments.create": "Record payments and receipts",
    "payments.reverse": "Reverse payments and receipts",
    "expenses.read": "View expenses and other income",
    "expenses.create": "Record expenses and other income",
    "bank.balance.read": "View cash and bank balances",
    "bank.manage": "Manage cash/bank accounts and transfers",
    # Inventory
    "inventory.read": "View stock levels and movements",
    "inventory.adjust": "Post stock adjustments",
    "inventory.transfer": "Transfer stock between warehouses",
    "inventory.count": "Run and approve stock counts",
    # Accounting
    "accounting.read": "View ledgers, journals and chart of accounts",
    "accounting.journal.create": "Create manual journal entries",
    "accounting.period.close": "Close and reopen financial periods",
    # Reports & data
    "reports.sales.read": "Sales and purchase reports",
    "reports.party.read": "Party statements and balances",
    "reports.stock.read": "Stock reports and valuation",
    "reports.gst.read": "GST reports",
    "reports.profit_loss.read": "Profit and loss, balance sheet, trial balance",
    "exports.create": "Export data",
    "imports.create": "Import data",
}

ALL = frozenset(PERMISSIONS)
READ_ONLY = frozenset(p for p in ALL if p.endswith(".read"))

_OWNER_ONLY = {"accounting.period.close", "settings.users.manage"}

SYSTEM_ROLES: dict[str, tuple[str, frozenset[str]]] = {
    "Owner": ("Full access, including users and period close", ALL),
    "Administrator": ("Operational modules and configuration", ALL - _OWNER_ONLY),
    "Accountant": (
        "Accounting, payments, expenses, reports and GST data",
        frozenset(
            {
                "settings.company.read", "parties.read", "parties.create", "parties.update",
                "items.read", "items.cost.read", "sales.invoice.read", "sales.invoice.create",
                "sales.invoice.post", "sales.invoice.cancel", "sales.return.create",
                "purchase.bill.read", "purchase.bill.create", "purchase.bill.post",
                "purchase.bill.cancel", "purchase.return.create", "payments.read", "payments.create",
                "payments.reverse", "expenses.read", "expenses.create", "bank.balance.read",
                "bank.manage", "inventory.read", "accounting.read", "accounting.journal.create",
                "accounting.period.close", "reports.sales.read", "reports.party.read",
                "reports.stock.read", "reports.gst.read", "reports.profit_loss.read",
                "exports.create", "imports.create", "audit.read",
            }
        ),
    ),
    "Salesperson": (
        "Quick billing and receipts; no costs, profit or bank balances",
        frozenset(
            {
                "settings.company.read", "parties.read", "parties.create", "items.read",
                "sales.invoice.read", "sales.invoice.create", "sales.invoice.post",
                "sales.return.create", "payments.create", "inventory.read",
            }
        ),
    ),
    "Inventory Manager": (
        "Items, stock, transfers and purchase receipts; no financial reports",
        frozenset(
            {
                "settings.company.read", "parties.read", "items.read", "items.cost.read",
                "items.create", "items.update", "items.archive", "inventory.read",
                "inventory.adjust", "inventory.transfer", "inventory.count",
                "purchase.bill.read", "purchase.bill.create", "purchase.order.manage",
                "reports.stock.read", "imports.create",
            }
        ),
    ),
    "Auditor": ("Read-only access to reports and the audit trail", READ_ONLY),
}

assert all(perms <= ALL for _, perms in SYSTEM_ROLES.values()), "unknown permission in a system role"
