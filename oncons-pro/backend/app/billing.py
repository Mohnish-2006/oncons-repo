from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP


def _pdf_escape(text: str) -> str:
    return str(text).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _money(value) -> str:
    amount = Decimal(str(value or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"{amount:,.2f}"


def _words_under_1000(n: int) -> str:
    ones = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten",
            "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen", "Seventeen",
            "Eighteen", "Nineteen"]
    tens = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]
    parts = []
    if n >= 100:
        parts.append(ones[n // 100] + " Hundred")
        n %= 100
    if n >= 20:
        parts.append(tens[n // 10])
        n %= 10
    if n:
        parts.append(ones[n])
    return " ".join(parts)


def amount_in_words(value) -> str:
    n = int(Decimal(str(value or 0)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    if n == 0:
        return "Zero Rupees Only"
    parts = []
    crore, n = divmod(n, 10000000)
    lakh, n = divmod(n, 100000)
    thousand, n = divmod(n, 1000)
    if crore:
        parts.append(_words_under_1000(crore) + " Crore")
    if lakh:
        parts.append(_words_under_1000(lakh) + " Lakh")
    if thousand:
        parts.append(_words_under_1000(thousand) + " Thousand")
    if n:
        parts.append(_words_under_1000(n))
    return "Rupees " + " ".join(parts) + " Only"


class PdfCanvas:
    def __init__(self):
        self.commands: list[str] = []

    def text(self, x, y, value, size=10, font="F1", color=(0.08, 0.12, 0.16)):
        r, g, b = color
        self.commands.append(f"{r} {g} {b} rg")
        self.commands.append("BT")
        self.commands.append(f"/{font} {size} Tf")
        self.commands.append(f"1 0 0 1 {x} {y} Tm")
        self.commands.append(f"({_pdf_escape(value)}) Tj")
        self.commands.append("ET")

    def rect(self, x, y, w, h, stroke=(0.84, 0.87, 0.9), fill=None, width=0.8):
        if fill:
            r, g, b = fill
            self.commands.append(f"{r} {g} {b} rg")
            self.commands.append(f"{x} {y} {w} {h} re f")
        if stroke:
            r, g, b = stroke
            self.commands.append(f"{width} w")
            self.commands.append(f"{r} {g} {b} RG")
            self.commands.append(f"{x} {y} {w} {h} re S")

    def line(self, x1, y1, x2, y2, color=(0.84, 0.87, 0.9), width=0.8):
        r, g, b = color
        self.commands.append(f"{width} w")
        self.commands.append(f"{r} {g} {b} RG")
        self.commands.append(f"{x1} {y1} m {x2} {y2} l S")

    def qr_like(self, x, y, seed: str, size=72):
        cell = size / 13
        self.rect(x, y, size, size, stroke=(0.1, 0.12, 0.15), fill=(1, 1, 1), width=0.7)
        for row in range(13):
            for col in range(13):
                val = (ord(seed[(row + col) % len(seed)]) + row * 7 + col * 11) % 5
                finder = (row < 4 and col < 4) or (row < 4 and col > 8) or (row > 8 and col < 4)
                if finder or val in (0, 3):
                    self.rect(x + col * cell, y + row * cell, cell * 0.88, cell * 0.88, stroke=None, fill=(0.02, 0.02, 0.02))

    def build(self) -> bytes:
        stream = "\n".join(self.commands).encode("latin-1", "replace")
        objects = [
            b"<< /Type /Catalog /Pages 2 0 R >>",
            b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R /F2 5 0 R >> >> /Contents 6 0 R >>",
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>",
            b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        ]
        pdf = b"%PDF-1.4\n"
        offsets = [0]
        for idx, obj in enumerate(objects, 1):
            offsets.append(len(pdf))
            pdf += f"{idx} 0 obj\n".encode() + obj + b"\nendobj\n"
        xref_at = len(pdf)
        pdf += f"xref\n0 {len(objects)+1}\n0000000000 65535 f \n".encode()
        for off in offsets[1:]:
            pdf += f"{off:010d} 00000 n \n".encode()
        pdf += f"trailer << /Size {len(objects)+1} /Root 1 0 R >>\nstartxref\n{xref_at}\n%%EOF\n".encode()
        return pdf


def booking_bill_pdf(customer, consultant, booking, payment, join_link):
    canvas = PdfCanvas()
    paid_at = payment.created_at.strftime("%d %b %Y | %I:%M %p") if hasattr(payment.created_at, "strftime") else str(payment.created_at)
    when = booking.scheduled_at.strftime("%d %b %Y | %I:%M %p") if hasattr(booking.scheduled_at, "strftime") else str(booking.scheduled_at)
    invoice_no = f"INV-{datetime.utcnow().strftime('%Y%m%d')}-{booking.id:04d}"
    payment_ref = payment.provider_ref or f"AUTO-{payment.id}"
    amount = Decimal(str(payment.amount or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    platform_fee = Decimal("0.00")
    tax = Decimal("0.00")
    total = amount
    mode = (getattr(booking, "mode", "video") or "video").title()

    canvas.rect(18, 18, 559, 806, stroke=(0.16, 0.18, 0.2), fill=(1, 1, 1), width=1)
    canvas.rect(18, 804, 559, 20, stroke=None, fill=(0.05, 0.49, 0.52))
    canvas.rect(18, 18, 559, 4, stroke=None, fill=(0.05, 0.49, 0.52))

    canvas.rect(38, 744, 34, 34, stroke=None, fill=(0.9, 0.98, 0.97))
    canvas.rect(44, 755, 13, 13, stroke=None, fill=(0.05, 0.49, 0.52))
    canvas.rect(55, 748, 13, 13, stroke=None, fill=(0.94, 0.54, 0.15))
    canvas.text(78, 762, "OnCons", 24, "F2", (0.05, 0.49, 0.52))
    canvas.text(79, 748, "ONLINE CONSULTATION", 7, "F2", (0.24, 0.35, 0.42))
    canvas.text(430, 758, "TAX INVOICE", 18, "F2", (0.02, 0.02, 0.02))

    meta_x = 326
    meta = [
        ("Invoice No.", invoice_no),
        ("Invoice Date", datetime.utcnow().strftime("%d %b %Y")),
        ("Booking ID", f"BK-{booking.id:04d}"),
        ("Payment Status", "PAID"),
        ("Payment Method", (payment.provider or "demo").replace("_", " ").title()),
    ]
    y = 710
    for label, value in meta:
        canvas.text(meta_x, y, label, 8, "F2")
        if value == "PAID":
            canvas.rect(meta_x + 92, y - 4, 42, 13, stroke=None, fill=(0.1, 0.7, 0.32))
            canvas.text(meta_x + 101, y - 1, value, 7, "F2", (1, 1, 1))
        else:
            canvas.text(meta_x + 92, y, value, 8, "F2")
        y -= 17

    canvas.line(38, 626, 557, 626)
    canvas.text(42, 604, "Billed To", 9, "F2")
    canvas.line(42, 598, 90, 598, (0.05, 0.49, 0.52), 1.1)
    canvas.text(42, 580, customer.name, 10, "F2")
    canvas.text(42, 563, customer.email, 8)
    canvas.text(42, 546, customer.phone or "Phone not provided", 8)

    canvas.text(300, 604, "Consultation Details", 9, "F2")
    canvas.line(300, 598, 398, 598, (0.05, 0.49, 0.52), 1.1)
    canvas.text(300, 580, consultant.name, 10, "F2")
    canvas.text(300, 563, consultant.category or "Consultant", 8)
    canvas.text(300, 546, f"{mode} Consultation", 8)
    canvas.text(300, 529, when, 8)
    canvas.text(300, 512, "One confirmed consultation session", 8)

    table_x, table_y, table_w = 38, 438, 519
    canvas.rect(table_x, table_y, table_w, 102, stroke=(0.77, 0.81, 0.86))
    canvas.rect(table_x, table_y + 78, table_w, 24, stroke=None, fill=(0.96, 0.98, 0.99))
    canvas.text(table_x + 12, table_y + 86, "Description", 8, "F2")
    canvas.text(table_x + 430, table_y + 86, "Amount (INR)", 8, "F2")
    rows = [
        ("Consultation Fee", amount),
        ("Platform Service Fee", platform_fee),
        ("GST / Tax", tax),
    ]
    y = table_y + 58
    for label, value in rows:
        canvas.line(table_x, y - 6, table_x + table_w, y - 6)
        canvas.text(table_x + 12, y, label, 8)
        canvas.text(table_x + 435, y, _money(value), 8, "F2")
        y -= 25

    canvas.rect(38, 394, 519, 32, stroke=None, fill=(0, 0, 0))
    canvas.text(50, 405, "TOTAL PAID", 10, "F2", (1, 1, 1))
    canvas.text(468, 405, f"INR {_money(total)}", 10, "F2", (1, 1, 1))
    canvas.text(42, 364, "Amount in Words", 8, "F2")
    canvas.text(42, 348, amount_in_words(total), 8)

    canvas.line(38, 324, 557, 324)
    canvas.qr_like(42, 238, f"{booking.id}-{payment.id}-{payment_ref}", 72)
    canvas.text(132, 292, "Transaction ID", 8, "F2")
    canvas.text(230, 292, payment_ref, 8)
    canvas.text(132, 270, "Payment Date", 8, "F2")
    canvas.text(230, 270, paid_at, 8)
    canvas.text(132, 248, "UPI / Method", 8, "F2")
    canvas.text(230, 248, (payment.provider or "demo").replace("_", " ").title(), 8)
    canvas.text(132, 226, "Join Link", 8, "F2")
    canvas.text(230, 226, join_link[:54], 7)

    canvas.text(200, 78, "Thank you for choosing OnCons", 10, "F2", (0.05, 0.49, 0.52))
    canvas.text(166, 58, "This invoice is generated automatically after verified payment.", 8, color=(0.4, 0.48, 0.55))
    return canvas.build()
