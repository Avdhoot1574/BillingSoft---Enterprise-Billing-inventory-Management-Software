"""Black-and-white, print-ready sales tax invoice."""

import io
from decimal import Decimal, ROUND_HALF_UP

from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import simpleSplit
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas


PAGE_W, PAGE_H = A4
LEFT, RIGHT = 34, PAGE_W - 34
WIDTH = RIGHT - LEFT
BLACK = (0, 0, 0)
WHITE = (1, 1, 1)
LIGHT = (0.91, 0.91, 0.91)
FAINT = (0.97, 0.97, 0.97)
COLS = [24, 126, 38, 43, 43, 43, 47, 39, 39, 39, WIDTH - 481]


def money(value):
    return f"{Decimal(str(value or 0)):,.2f}"


def date_text(value):
    return value.strftime("%d-%b-%Y") if hasattr(value, "strftime") else (str(value) if value else "-")


def text(c, value, x, y, size=8, bold=False, right=False, max_width=None):
    value = str(value if value is not None and value != "" else "-")
    font = "Helvetica-Bold" if bold else "Helvetica"
    if max_width is not None:
        while stringWidth(value, font, size) > max_width and size > 5.5:
            size -= .25
        if stringWidth(value, font, size) > max_width:
            while value and stringWidth(value + "...", font, size) > max_width:
                value = value[:-1]
            value += "..."
    c.setFillColorRGB(*BLACK)
    c.setFont(font, size)
    (c.drawRightString if right else c.drawString)(x, y, value)


def line(c, x1, y1, x2, y2, width=.6):
    c.setStrokeColorRGB(*BLACK)
    c.setLineWidth(width)
    c.line(x1, y1, x2, y2)


def box(c, x, top, width, height, fill=None, stroke=.7):
    if fill is not None:
        c.setFillColorRGB(*fill)
    c.setStrokeColorRGB(*BLACK)
    c.setLineWidth(stroke)
    c.rect(x, top - height, width, height, fill=int(fill is not None), stroke=1)


def band(c, title, x, top, width, height=19):
    box(c, x, top, width, height, LIGHT)
    c.setFillColorRGB(*BLACK)
    c.setFont("Helvetica-Bold", 8)
    c.drawCentredString(x + width / 2, top - 13, title)


def address_lines(address):
    if not isinstance(address, dict):
        return []
    values = [address.get("line1"), address.get("line2")]
    values.append(", ".join(str(address[k]) for k in ("city", "district", "state_code", "postal_code") if address.get(k)))
    return [str(v) for v in values if v]


def wrapped(c, value, x, y, width, max_lines=3, size=7.5, leading=10):
    for part in simpleSplit(str(value or ""), "Helvetica", size, width)[:max_lines]:
        text(c, part, x, y, size, max_width=width)
        y -= leading
    return y


def header(c, invoice, company, page):
    top = PAGE_H - 32
    box(c, LEFT, top, WIDTH, 76)
    company_name = company.get("legal_name") or company.get("name") or "Company"
    text(c, company_name, LEFT + 10, top - 20, 14, True, max_width=WIDTH - 120)
    address = [company.get("address_line1"), company.get("address_line2")]
    address.append(", ".join(str(company[k]) for k in ("city", "district", "state_code", "postal_code") if company.get(k)))
    address = [str(v) for v in address if v]
    if address:
        wrapped(c, ", ".join(address), LEFT + 10, top - 35, WIDTH - 128, 2, 7.5, 10)
    contact = [f"GSTIN: {company['gstin']}" if company.get("gstin") else None,
               f"Tel: {company['phone']}" if company.get("phone") else None,
               f"Email: {company['email']}" if company.get("email") else None]
    text(c, "   |   ".join(v for v in contact if v) or " ", LEFT + 10, top - 65, 7, max_width=WIDTH - 22)
    line(c, RIGHT - 99, top, RIGHT - 99, top - 76)
    c.setFont("Helvetica-Bold", 9)
    c.drawCentredString(RIGHT - 49.5, top - 29, "ORIGINAL")
    c.setFont("Helvetica", 8)
    c.drawCentredString(RIGHT - 49.5, top - 51, f"Page {page}")
    return top - 76


def title_and_meta(c, invoice, top):
    box(c, LEFT, top, WIDTH, 31, LIGHT)
    text(c, "TAX INVOICE", PAGE_W / 2 - 42, top - 21, 13, True)
    top -= 31
    half = WIDTH / 2
    row_h = 21
    rows = [
        (("Invoice No.", invoice.get("invoice_number") or "Draft"), ("Supply type", str(invoice.get("supply_type") or "-").replace("_", " ").title())),
        (("Invoice date", date_text(invoice.get("invoice_date"))), ("Due date", date_text(invoice.get("due_date")))),
        (("Reverse charge", "-" if invoice.get("reverse_charge") is None else ("Yes" if invoice["reverse_charge"] else "No")), ("Place of supply", invoice.get("place_of_supply_state_code") or "-")),
    ]
    for i, (left, right) in enumerate(rows):
        y = top - i * row_h
        box(c, LEFT, y, half, row_h)
        box(c, LEFT + half, y, half, row_h)
        for x, (name, value) in ((LEFT, left), (LEFT + half, right)):
            text(c, name + ":", x + 7, y - 14, 7.5, True)
            text(c, value, x + 100, y - 14, 8, max_width=half - 108)
    return top - len(rows) * row_h


def party_block(c, title, name, address, gstin, state_code, x, top, width):
    band(c, title, x, top, width)
    body_top = top - 19
    box(c, x, body_top, width, 94)
    text(c, "Name:", x + 7, body_top - 14, 7.5, True)
    text(c, name or "-", x + 43, body_top - 14, 8, True, max_width=width - 51)
    text(c, "Address:", x + 7, body_top - 29, 7.5, True)
    wrapped(c, ", ".join(address) or "-", x + 48, body_top - 29, width - 56, 3, 7, 10)
    line(c, x, body_top - 69, x + width, body_top - 69)
    text(c, "GSTIN:", x + 7, body_top - 82, 7.5, True)
    text(c, gstin or "-", x + 48, body_top - 82, 7.5, max_width=width - 102)
    text(c, "State:", x + width - 96, body_top - 82, 7.5, True)
    text(c, state_code or "-", x + width - 57, body_top - 82, 7.5)


def parties(c, invoice, top):
    half = WIDTH / 2
    billing = invoice.get("billing_address_snapshot") or {}
    shipping = invoice.get("shipping_address_snapshot") or billing
    name = invoice.get("customer_name_snapshot") or "Customer"
    gstin = invoice.get("customer_gstin_snapshot")
    party_block(c, "RECEIVER (BILLED TO)", name, address_lines(billing), gstin,
                billing.get("state_code") if isinstance(billing, dict) else None, LEFT, top, half)
    party_block(c, "CONSIGNEE (SHIPPED TO)", name, address_lines(shipping), gstin,
                shipping.get("state_code") if isinstance(shipping, dict) else None, LEFT + half, top, half)
    return top - 113


def table_header(c, top):
    headings = ["S. No.", "Product description", "HSN", "Qty / UOM", "Rate", "Discount", "Taxable", "CGST", "SGST", "IGST", "Total"]
    x = LEFT
    for width, heading in zip(COLS, headings):
        box(c, x, top, width, 30, LIGHT, .55)
        for i, part in enumerate(simpleSplit(heading, "Helvetica-Bold", 6.5, width - 6)[:2]):
            text(c, part, x + 3, top - 11 - i * 8, 6.5, True)
        x += width
    return top - 30


def line_height(item):
    description = str(item.get("item_name_snapshot") or "Item")
    return max(31, 14 + 10 * len(simpleSplit(description, "Helvetica", 7, COLS[1] - 8)))


def tax_cell(c, item, key, x, y, width):
    amount = Decimal(str(item.get(f"{key}_amount") or 0))
    if not amount:
        text(c, "-", x + width - 4, y - 17, 7, right=True)
        return
    taxable = Decimal(str(item.get("taxable_amount") or 0))
    rate = amount * 100 / taxable if taxable else Decimal(0)
    text(c, f"{rate.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP):g}%", x + width - 4, y - 11, 6.2, right=True)
    text(c, money(amount), x + width - 4, y - 22, 6.4, right=True, max_width=width - 7)


def item_row(c, item, number, top):
    height = line_height(item)
    if number % 2 == 0:
        c.setFillColorRGB(*FAINT)
        c.rect(LEFT, top - height, WIDTH, height, fill=1, stroke=0)
    x = LEFT
    for width in COLS:
        box(c, x, top, width, height, stroke=.45)
        x += width
    x = LEFT
    text(c, number, x + 4, top - 16, 7)
    x += COLS[0]
    wrapped(c, item.get("item_name_snapshot") or "Item", x + 4, top - 14, COLS[1] - 8, 6, 7, 10)
    x += COLS[1]
    text(c, item.get("hsn_sac_snapshot") or "-", x + 3, top - 16, 6.5, max_width=COLS[2] - 6)
    x += COLS[2]
    qty = f"{item.get('quantity') or 0:g} {item.get('unit_name_snapshot') or ''}"
    text(c, qty, x + COLS[3] - 3, top - 16, 6.5, right=True, max_width=COLS[3] - 6)
    x += COLS[3]
    for width, value in ((COLS[4], item.get("unit_price")), (COLS[5], item.get("discount_amount")),
                         (COLS[6], item.get("taxable_amount"))):
        text(c, money(value), x + width - 3, top - 16, 6.5, right=True, max_width=width - 6)
        x += width
    for key, width in zip(("cgst", "sgst", "igst"), COLS[7:10]):
        tax_cell(c, item, key, x, top, width)
        x += width
    text(c, money(item.get("line_total")), RIGHT - 3, top - 16, 6.5, True, True, COLS[-1] - 6)
    return top - height


_ONES = ("", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen")
_TENS = ("", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety")


def _under_thousand(number):
    words = []
    if number >= 100:
        words.extend((_ONES[number // 100], "hundred"))
        number %= 100
    if number >= 20:
        words.append(_TENS[number // 10])
        number %= 10
    if number:
        words.append(_ONES[number])
    return " ".join(words)


def amount_in_words(value):
    amount = Decimal(str(value or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    rupees = int(amount)
    paise = int((amount - rupees) * 100)
    if rupees == 0:
        words = "zero"
    else:
        groups = []
        for divisor, unit in ((10_000_000, "crore"), (100_000, "lakh"), (1_000, "thousand")):
            part, rupees = divmod(rupees, divisor)
            if part:
                groups.append(f"{_under_thousand(part)} {unit}")
        if rupees:
            groups.append(_under_thousand(rupees))
        words = " ".join(groups)
    result = f"Rupees {words}"
    if paise:
        result += f" and {_under_thousand(paise)} paise"
    return result.capitalize() + " only"


def totals(c, invoice, company, top):
    half = WIDTH * .55
    remaining = WIDTH - half
    rows = [
        ("Amount before tax", invoice.get("taxable_total")),
        ("CGST", invoice.get("cgst_total")),
        ("SGST", invoice.get("sgst_total")),
        ("IGST", invoice.get("igst_total")),
        ("Cess", invoice.get("cess_total")),
        ("Other charges", invoice.get("other_charges")),
        ("Grand total", invoice.get("grand_total")),
    ]
    row_h = 18
    total_h = len(rows) * row_h
    box(c, LEFT, top, half, total_h)
    band(c, "TOTAL INVOICE AMOUNT IN WORDS", LEFT, top, half, 20)
    wrapped(c, amount_in_words(invoice.get("grand_total")), LEFT + 7, top - 34, half - 14, 4, 8, 12)
    text(c, f"Subtotal: {money(invoice.get('subtotal'))}", LEFT + 7, top - 92, 7.5)
    text(c, f"Discount: {money(invoice.get('discount_total'))}", LEFT + 7, top - 107, 7.5)
    for index, (name, value) in enumerate(rows):
        y = top - index * row_h
        box(c, LEFT + half, y, remaining, row_h, LIGHT if name == "Grand total" else None)
        text(c, name, LEFT + half + 6, y - 12, 7.5, name == "Grand total")
        text(c, money(value), RIGHT - 6, y - 12, 7.5, name == "Grand total", True)
    top -= total_h
    box(c, LEFT, top, WIDTH, 80)
    line(c, LEFT + half, top, LEFT + half, top - 80)
    text(c, "NOTES / TERMS", LEFT + 7, top - 13, 8, True)
    notes = [v for v in (invoice.get("notes"), invoice.get("terms")) if v]
    wrapped(c, " | ".join(str(v) for v in notes), LEFT + 7, top - 27, half - 14, 4, 7.5, 11)
    text(c, f"For {company.get('legal_name') or company.get('name') or 'Company'}", LEFT + half + 8, top - 15, 8, True, max_width=remaining - 16)
    text(c, "Authorised signatory", RIGHT - 110, top - 68, 8)
    top -= 80
    box(c, LEFT, top, WIDTH, 21, LIGHT)
    text(c, "Computer generated invoice", LEFT + 7, top - 14, 7)
    balance = Decimal(str(invoice.get("grand_total") or 0)) - Decimal(str(invoice.get("paid_total") or 0))
    text(c, f"Paid: {money(invoice.get('paid_total'))}   |   Balance due: {money(balance)}", RIGHT - 7, top - 14, 7, right=True)
    return top - 21


def render_invoice_pdf(invoice, lines, company):
    """Render the stored invoice, continuing the item table across pages."""
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    c.setTitle(f"Tax Invoice {invoice.get('invoice_number') or 'Draft'}")
    page = 1
    top = parties(c, invoice, title_and_meta(c, invoice, header(c, invoice, company, page)))
    y = table_header(c, top)
    for number, item in enumerate(lines, 1):
        if y - line_height(item) < 58:
            c.showPage()
            page += 1
            y = table_header(c, title_and_meta(c, invoice, header(c, invoice, company, page)))
        y = item_row(c, item, number, y)
    if y < 260:
        c.showPage()
        page += 1
        y = title_and_meta(c, invoice, header(c, invoice, company, page))
    totals(c, invoice, company, y)
    c.save()
    return buffer.getvalue()
