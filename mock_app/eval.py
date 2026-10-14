import sys, json, sqlite3, requests
from agent.loop import run
from agent.verifier import check

BASE, DB = "http://localhost:5000", "mock_app/company.db"

def seed(vendor, amount, due, status="pending"):
    with sqlite3.connect(DB) as c:
        c.execute("INSERT INTO invoices(vendor,amount,due_date,status) VALUES(?,?,?,?)",
                  (vendor, amount, due, status))

TASKS = [
 {"name": "enter_latest_companyx",
  "goal": "Find the latest invoice from Company X in data/invoices, extract the amount and due date, enter it in the finance system, and tell me when it is done.",
  "expect": {"vendor": "Company X", "amount": 48750, "due_date": "2026-11-01", "status": "pending"}},
 {"name": "enter_acme",
  "goal": "Enter the Acme invoice from data/invoices into the finance system and confirm it is saved.",
  "expect": {"vendor": "Acme Corp", "amount": 9200, "due_date": "2026-11-04", "status": "pending"}},
 {"name": "mark_paid",
  "goal": "Mark the Company X invoice as paid in the finance system and confirm it.",
  "seed": [("Company X", 48750.0, "2026-11-01")],
  "expect": {"vendor": "Company X", "status": "paid"}},
]

def count_errors(trace):
    steps = json.load(open(trace))["steps"]
    return sum(1 for s in steps if s["out"].startswith("{'error'"))

label = sys.argv[1] if len(sys.argv) > 1 else "run"
results = []
only = sys.argv[2] if len(sys.argv) > 2 else None
for t in [x for x in TASKS if only in (None, x["name"])]:
    requests.post(BASE + "/api/reset", timeout=5)
    for s in t.get("seed", []):
        seed(*s)
    try:
        r = run(t["goal"], auto_approve=True)
        ok = bool(check(t["expect"])["verified"])   # independent of the agent's own claim
        results.append({"task": t["name"], "passed": ok, "steps": r["steps"],
                        "errors": count_errors(r["trace"])})
    except Exception as e:
        results.append({"task": t["name"], "passed": False, "steps": 0, "errors": 0,
                        "crash": str(e)[:100]})

print(f"\n=== EVAL: {label} ===")
print(f"{'task':26}{'pass':6}{'steps':7}{'errors':7}")
for r in results:
    print(f"{r['task']:26}{str(r['passed']):6}{r['steps']:<7}{r['errors']:<7}")
print(f"pass rate: {sum(r['passed'] for r in results)}/{len(results)}")
json.dump(results, open(f"docs/eval_{label}.json", "w"), indent=1)