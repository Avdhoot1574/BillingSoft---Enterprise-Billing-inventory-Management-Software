"""Print-ready sales tax invoice, using only stored invoice and company data."""

import io
from decimal import Decimal

from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import simpleSplit
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas


PAGE_W, PAGE_H = A4
LEFT, RIGHT = 34, PAGE_W - 34
WIDTH = RIGHT - LEFT
INK = (0.10, 0.13, 0.16)
MUTED = (0.32, 0.36, 0.39)
RULE = (0.30, 0.33, 0.35)
PALE = (0.95, 0.97, 0.97)


def money(value):
    return f"{Decimal(str(value or 0)):,.2f}"


def date_text(value):
    return value.strftime("%d-%b-%Y") if hasattr(value, "strftime") else (str(value) if value else "-")


def label(c, text, x, y, size=8, bold=False):
    c.setFillColorRGB(*(INK if bold else MUTED))
    c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
    c.drawString(x, y, str(text))


def fitted(c, value, x, y, max_width, size=8, bold=False, right=False):
    value = str(value or "-")
    font = "Helvetica-Bold" if bold else "Helvetica"
    while stringWidth(value, font, size) > max_width and size > 6:
        size -= .25
    if stringWidth(value, font, size) > max_width:
        while stringWidth(value + "...", font, size) > max_width and value:
            value = value[:-1]
        value += "..."
    c.setFillColorRGB(*INK)
    c.setFont(font, size)
    (c.drawRightString if right else c.drawString)(x, y, value)


def rule(c, x1, y1, x2, y2, width=.55):
    c.setStrokeColorRGB(*RULE)
    c.setLineWidth(width)
    c.line(x1, y1, x2, y2)


def address_lines(address):
    if not isinstance(address, dict):
        return []
    lines = [address.get("line1"), address.get("line2")]
    location = ", ".join(str(address[k]) for k in ("city", "district", "state_code", "postal_code") if address.get(k))
    return [str(line) for line in [*lines, location, address.get("country_code")] if line]


def section_text(c, title, entries, x, top, width, max_bottom):
    label(c, title, x + 7, top - 12, 8.5, True)
    y = top - 25
    for entry in entries:
        for line in simpleSplit(str(entry), "Helvetica", 8, width - 16):
            if y < max_bottom + 8:
                return
            fitted(c, line, x + 7, y, width - 15)
            y -= 11


def page_heading(c, invoice, page):
    label(c, "TAX INVOICE", PAGE_W / 2 - 34, PAGE_H - 28, 11, True)
    if page > 1:
        label(c, f"Invoice {invoice.get('invoice_number') or 'Draft'} - continued", LEFT, PAGE_H - 48, 8)
    rule(c, LEFT, 26, RIGHT, 26)
    label(c, f"Page {page}", RIGHT - 36, 16, 7)
    label(c, "Computer generated invoice", LEFT, 16, 7)


def details(c, invoice, company):
    top = PAGE_H - 46
    bottom = top - 156
    mid = LEFT + WIDTH * .50
    rule(c, LEFT, top, RIGHT, top)
    rule(c, LEFT, bottom, RIGHT, bottom)
    rule(c, LEFT, top, LEFT, bottom)
    rule(c, mid, top, mid, bottom)
    rule(c, RIGHT, top, RIGHT, bottom)
    company_address = [company.get("legal_name") or company.get("name"), company.get("address_line1"), company.get("address_line2")]
    company_address += [", ".join(str(company[k]) for k in ("city", "district", "state_code", "postal_code") if company.get(k))]
    company_address += [f"GSTIN: {company['gstin']}" if company.get("gstin") else None,
                        f"PAN: {company['pan']}" if company.get("pan") else None,
                        f"Phone: {company['phone']}" if company.get("phone") else None,
                        f"Email: {company['email']}" if company.get("email") else None]
    section_text(c, "FROM", [v for v in company_address if v], LEFT, top, mid - LEFT, bottom + 70)
    customer = [invoice.get("customer_name_snapshot") or "Customer"]
    customer += address_lines(invoice.get("billing_address_snapshot"))
    if invoice.get("customer_gstin_snapshot"):
        customer.append(f"GSTIN: {invoice['customer_gstin_snapshot']}")
    section_text(c, "BILL TO", customer, LEFT, bottom + 69, mid - LEFT, bottom)
    rule(c, LEFT, bottom + 70, mid, bottom + 70)
    shipping = address_lines(invoice.get("shipping_address_snapshot"))
    if shipping:
        section_text(c, "SHIP TO", shipping, mid, bottom + 70, RIGHT - mid, bottom)
    fields = [("Invoice No.", invoice.get("invoice_number") or "Draft"),
              ("Invoice Date", date_text(invoice.get("invoice_date"))),
              ("Due Date", date_text(invoice.get("due_date"))),
              ("Supply Type", str(invoice.get("supply_type") or "-").replace("_", " ").title()),
              ("Place of Supply", invoice.get("place_of_supply_state_code") or "-"),
              ("Payment Status", str(invoice.get("payment_status") or "-").replace("_", " ").title())]
    cell_h = 26
    col = (RIGHT - mid) / 2
    for i, (name, value) in enumerate(fields):
        row, column = divmod(i, 2)
        x = mid + column * col
        y = top - row * cell_h
        label(c, name, x + 6, y - 9, 7)
        fitted(c, value, x + 6, y - 20, col - 12, 8, True)
        if column == 0:
            rule(c, mid + col, y, mid + col, y - cell_h)
        rule(c, mid, y - cell_h, RIGHT, y - cell_h)
    return bottom - 17


def table_header(c, y):
    c.setFillColorRGB(*PALE)
    c.rect(LEFT, y - 26, WIDTH, 26, fill=1, stroke=0)
    for x in (LEFT, LEFT + 28, LEFT + 234, LEFT + 284, LEFT + 340, LEFT + 400, RIGHT):
        rule(c, x, y, x, y - 26)
    rule(c, LEFT, y, RIGHT, y)
    rule(c, LEFT, y - 26, RIGHT, y - 26)
    for title, x in (("#", LEFT + 7), ("Description of goods / services", LEFT + 34),
                     ("HSN/SAC", LEFT + 238), ("Qty", LEFT + 289),
                     ("Rate", LEFT + 346), ("Amount", LEFT + 406)):
        label(c, title, x, y - 16, 7, True)
    return y - 26


def line_row(c, line, number, y):
    name = str(line.get("item_name_snapshot") or "Item")
    wrapped = simpleSplit(name, "Helvetica-Bold", 8, 193) or [""]
    row_h = max(29, 13 + 10 * len(wrapped))
    if number % 2 == 0:
        c.setFillColorRGB(.985, .985, .985)
        c.rect(LEFT, y - row_h, WIDTH, row_h, fill=1, stroke=0)
    columns = (LEFT, LEFT + 28, LEFT + 234, LEFT + 284, LEFT + 340, LEFT + 400, RIGHT)
    for x in columns:
        rule(c, x, y, x, y - row_h, .35)
    rule(c, LEFT, y - row_h, RIGHT, y - row_h, .35)
    label(c, number, LEFT + 7, y - 15, 8)
    for i, part in enumerate(wrapped):
        fitted(c, part, LEFT + 34, y - 15 - i * 10, 193, 8, i == 0)
    fitted(c, line.get("hsn_sac_snapshot") or "-", LEFT + 238, y - 15, 43, 7)
    fitted(c, f"{line.get('quantity') or 0:g} {line.get('unit_name_snapshot') or ''}", LEFT + 335, y - 15, 48, 7, right=True)
    fitted(c, money(line.get("unit_price")), LEFT + 396, y - 15, 52, 7, right=True)
    fitted(c, money(line.get("line_total")), RIGHT - 5, y - 15, 85, 8, True, True)
    return y - row_h


def summary(c, invoice, y):
    rows = [("Subtotal", invoice.get("subtotal")), ("Discount", invoice.get("discount_total")),
            ("Taxable value", invoice.get("taxable_total")), ("CGST", invoice.get("cgst_total")),
            ("SGST", invoice.get("sgst_total")), ("IGST", invoice.get("igst_total")),
            ("Cess", invoice.get("cess_total")), ("Other charges", invoice.get("other_charges")),
            ("Grand total", invoice.get("grand_total")), ("Paid", invoice.get("paid_total")),
            ("Balance due", Decimal(str(invoice.get("grand_total") or 0)) - Decimal(str(invoice.get("paid_total") or 0)))]
    for name, value in rows:
        highlight = name in ("Grand total", "Balance due")
        if highlight:
            c.setFillColorRGB(*PALE)
            c.rect(LEFT, y - 22, WIDTH, 22, fill=1, stroke=0)
        rule(c, LEFT, y - 22, RIGHT, y - 22)
        label(c, name, LEFT + 7, y - 15, 8, highlight)
        fitted(c, money(value), RIGHT - 7, y - 15, 110, 8, highlight, True)
        y -= 22
    return y


def render_invoice_pdf(invoice, lines, company):
    """Render a bordered tax invoice, automatically continuing long item tables."""
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    c.setTitle(f"Tax Invoice {invoice.get('invoice_number') or 'Draft'}")
    page = 1
    page_heading(c, invoice, page)
    y = table_header(c, details(c, invoice, company))
    for number, line in enumerate(lines, 1):
        row_height = max(29, 13 + 10 * len(simpleSplit(str(line.get("item_name_snapshot") or "Item"), "Helvetica-Bold", 8, 193)))
        if y - row_height < 350:
            c.showPage()
            page += 1
            page_heading(c, invoice, page)
            y = table_header(c, PAGE_H - 65)
        y = line_row(c, line, number, y)
    if y < 350:
        c.showPage()
        page += 1
        page_heading(c, invoice, page)
        y = PAGE_H - 65
    y = summary(c, invoice, y)
    notes = [("Notes", invoice.get("notes")), ("Terms", invoice.get("terms"))]
    for title, value in notes:
        if not value:
            continue
        if y < 110:
            c.showPage()
            page += 1
            page_heading(c, invoice, page)
            y = PAGE_H - 65
        label(c, f"{title}:", LEFT + 7, y - 18, 8, True)
        for line in simpleSplit(str(value), "Helvetica", 8, WIDTH - 80)[:3]:
            y -= 12
            label(c, line, LEFT + 55, y - 6, 8)
        y -= 45
    if y < 85:
        c.showPage()
        page += 1
        page_heading(c, invoice, page)
        y = PAGE_H - 90
    rule(c, RIGHT - 175, y - 38, RIGHT, y - 38)
    label(c, "Authorised signature", RIGHT - 115, y - 52, 8)
    c.save()
    return buffer.getvalue()
