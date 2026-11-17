from fastapi import APIRouter

from app.api.v1 import (
    audit,
    auth,
    companies,
    inventory,
    invoices,
    master_data,
    members,
    parties,
    payments,
    purchase_bills,
    reports,
)

api_router = APIRouter()

api_router.include_router(auth.router)
api_router.include_router(companies.router)
api_router.include_router(members.router)
api_router.include_router(audit.router)
api_router.include_router(parties.router)
api_router.include_router(master_data.router)

api_router.include_router(invoices.router)
api_router.include_router(purchase_bills.router)
api_router.include_router(payments.router)
api_router.include_router(inventory.router)
api_router.include_router(reports.router)