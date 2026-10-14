import requests

def check(expected, base="http://localhost:5000"):
    rows = requests.get(f"{base}/api/invoices", timeout=5).json()
    for r in rows:
        ok = True
        for k, v in expected.items():
            if k == "amount":
                ok &= abs(float(r["amount"]) - float(str(v).replace(",", ""))) < 0.01
            else:
                ok &= str(r.get(k, "")).strip().lower() == str(v).strip().lower()
        if ok:
            return {"verified": True, "matching_row": r}
    return {"verified": False, "expected": expected, "db_rows": rows[-5:]}