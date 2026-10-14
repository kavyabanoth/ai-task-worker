import os, random, sqlite3
from flask import Flask, request, redirect, render_template_string, jsonify

app = Flask(__name__)
DB = os.path.join(os.path.dirname(__file__), "company.db")
FLAKY_MODE = os.getenv("FLAKY", "0")
FLAKY = FLAKY_MODE in ("1", "2")
state = {"failed_once": False}

def db():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c

def init():
    with db() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS invoices(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vendor TEXT, amount REAL, due_date TEXT,
            status TEXT DEFAULT 'pending')""")

PAGE = """
<h1>Internal Finance System</h1>
<a href="/">Invoices</a> | <a href="/new">New Invoice</a>
{% block %}{% endblock %}
"""

LIST = PAGE.replace("{% block %}{% endblock %}", """
<table border=1 id="invoice-table">
<tr><th>ID</th><th>Vendor</th><th>Amount</th><th>Due</th><th>Status</th><th></th></tr>
{% for i in rows %}
<tr><td>{{i.id}}</td><td>{{i.vendor}}</td><td>{{i.amount}}</td>
<td>{{i.due_date}}</td><td>{{i.status}}</td>
<td>{% if i.status=='pending' %}
<form method=post action="/pay/{{i.id}}"><button id="pay-{{i.id}}">Mark Paid</button></form>
{% endif %}</td></tr>
{% endfor %}</table>""")

FORM = PAGE.replace("{% block %}{% endblock %}", """
{% if error %}<p id="error" style="color:red">{{error}}</p>{% endif %}
<form method=post action="/new">
Vendor: <input name="vendor" id="vendor"><br>
Amount: <input name="amount" id="amount"><br>
Due date (YYYY-MM-DD): <input name="due_date" id="due_date"><br>
<button id="{{btn}}" type="submit">Save Invoice</button>
</form>""")

@app.route("/")
def index():
    rows = db().execute("SELECT * FROM invoices ORDER BY id").fetchall()
    return render_template_string(LIST, rows=rows)

@app.route("/new", methods=["GET", "POST"])
def new():
    # flaky mode: button id changes (always in FLAKY=2, randomly in FLAKY=1),
    # and the first save after startup or reset fails with a 500
    btn = "save-btn"
    if FLAKY and (FLAKY_MODE == "2" or random.random() < 0.5):
        btn = "submit-invoice-btn"
    if request.method == "GET":
        return render_template_string(FORM, btn=btn, error=None)
    if FLAKY and not state["failed_once"]:
        state["failed_once"] = True
        return "Internal Server Error", 500
    v, a, d = request.form["vendor"], request.form["amount"], request.form["due_date"]
    try:
        a = float(a)
    except ValueError:
        return render_template_string(FORM, btn=btn, error="Amount must be a number")
    with db() as c:
        c.execute("INSERT INTO invoices(vendor,amount,due_date) VALUES(?,?,?)", (v, a, d))
    return redirect("/")

@app.route("/pay/<int:i>", methods=["POST"])
def pay(i):
    with db() as c:
        c.execute("UPDATE invoices SET status='paid' WHERE id=?", (i,))
    return redirect("/")

@app.route("/api/invoices")
def api():  # used by the verifier, not by the agent
    return jsonify([dict(r) for r in db().execute("SELECT * FROM invoices")])

@app.route("/api/reset", methods=["POST"])
def reset():  # used by eval.py between tasks
    with db() as c:
        c.execute("DELETE FROM invoices")
    state["failed_once"] = False
    return "ok"

if __name__ == "__main__":
    init()
    app.run(port=5000)