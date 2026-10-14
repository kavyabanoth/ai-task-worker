from reportlab.pdfgen import canvas
import os

invoices = [
    ("Company_X_INV-101.pdf", "Company X", "INV-101", "2026-09-01", "12,500.00", "2026-09-30"),
    ("Company_X_INV-143.pdf", "Company X", "INV-143", "2026-10-02", "48,750.00", "2026-11-01"),
    ("Acme_INV-77.pdf",       "Acme Corp", "INV-77",  "2026-10-05", "9,200.00",  "2026-11-04"),
]
os.makedirs("data/invoices", exist_ok=True)
for fn, vendor, no, issued, amt, due in invoices:
    c = canvas.Canvas(f"data/invoices/{fn}")
    y = 800
    for line in [f"INVOICE {no}", f"Vendor: {vendor}", f"Issue date: {issued}",
                 f"Total amount due: INR {amt}", f"Payment due date: {due}"]:
        c.drawString(72, y, line); y -= 24
    c.save()
print("done")



