import os, re, time, glob
from pypdf import PdfReader
from playwright.sync_api import sync_playwright

WRITE_WORDS = re.compile(r"save|submit|pay|paid|delete|remove|send|approve|confirm|mark", re.I)

class Browser:
    def __init__(self, headless=True):
        self.p = sync_playwright().start()
        self.page = self.p.chromium.launch(headless=headless).new_page()
        self.last_status = None
        self.page.on("response", self._on_response)

    def _on_response(self, r):
        if r.request.resource_type == "document":
            self.last_status = r.status

    def snapshot(self):
        els = self.page.evaluate("""() => [...document.querySelectorAll(
            'a,button,input,select,textarea')].map(e => ({
            tag: e.tagName.toLowerCase(), id: e.id, name: e.name || '',
            text: (e.innerText || e.value || '').trim().slice(0, 60)}))""")
        return {"url": self.page.url, "http_status": self.last_status,
                "page_text": self.page.inner_text("body")[:1500], "elements": els}

    def goto(self, url):
        self.page.goto(url, timeout=8000)
        return self.snapshot()

    def fill(self, target, value):
        self.page.locator(f"[id='{target}'], [name='{target}']").first.fill(value, timeout=3000)
        return {"filled": target}

    def click(self, target):
        loc = self.page.locator(f"[id='{target}']")
        if loc.count() == 0:
            loc = self.page.get_by_role("button", name=target)
        if loc.count() == 0:
            loc = self.page.get_by_text(target)
        loc.first.click(timeout=3000)
        self.page.wait_for_load_state()
        return self.snapshot()

BROWSER = None
def browser():
    global BROWSER
    if BROWSER is None:
        BROWSER = Browser(headless=os.getenv("HEADLESS", "1") == "1")
    return BROWSER

def read_file(path):
    if path.lower().endswith(".pdf"):
        return {"text": "\n".join(p.extract_text() for p in PdfReader(path).pages)}
    return {"text": open(path, errors="ignore").read()[:5000]}

def list_files(directory):
    return {"files": sorted(os.path.basename(f) for f in glob.glob(f"{directory}/*"))}

def ask_human(question):
    return {"answer": input(f"\n[AGENT NEEDS YOU] {question}\n> ")}

TOOLS = [
 {"name": "list_files", "description": "List files in a directory.",
  "input_schema": {"type": "object", "properties": {"directory": {"type": "string"}}, "required": ["directory"]}},
 {"name": "read_file", "description": "Read a PDF or text file.",
  "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}},
 {"name": "browser_goto", "description": "Open a URL; returns page text and elements.",
  "input_schema": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}},
 {"name": "browser_read", "description": "Re-read the current page.",
  "input_schema": {"type": "object", "properties": {}}},
 {"name": "browser_fill", "description": "Fill an input by id or name.",
  "input_schema": {"type": "object", "properties": {"target": {"type": "string"}, "value": {"type": "string"}}, "required": ["target", "value"]}},
 {"name": "browser_click", "description": "Click by element id or visible text. Prefer visible text; ids can change.",
  "input_schema": {"type": "object", "properties": {"target": {"type": "string"}}, "required": ["target"]}},
 {"name": "remember", "description": "Store a fact for later steps.",
  "input_schema": {"type": "object", "properties": {"key": {"type": "string"}, "value": {"type": "string"}}, "required": ["key", "value"]}},
 {"name": "ask_human", "description": "Ask the user for clarification or approval.",
  "input_schema": {"type": "object", "properties": {"question": {"type": "string"}}, "required": ["question"]}},
 {"name": "verify", "description": "Check the final outcome against expected values in the real system. Call before finishing.",
  "input_schema": {"type": "object", "properties": {"expected": {"type": "object"}}, "required": ["expected"]}},
]

def is_write(name, args):
    return name == "browser_click" and bool(WRITE_WORDS.search(args.get("target", "")))

def execute(name, args, mem, auto_approve=False, retries=2):
    if is_write(name, args) and not auto_approve:
        ans = ask_human(f"About to click '{args['target']}'. Facts: {mem.facts}. Approve? (y/n)")["answer"]
        if not ans.lower().startswith("y"):
            return {"error": "human denied this action"}
    if is_write(name, args):      # NEW: never auto-retry a write action
        retries = 0               # NEW: return the error and let the agent replan
    if name == "remember":
        mem.facts[args["key"]] = args["value"]
        return {"stored": args["key"]}
    if name == "verify":
        from agent.verifier import check
        return check(args["expected"])
    fn = {"list_files": list_files, "read_file": read_file, "ask_human": ask_human,
          "browser_goto": lambda url: browser().goto(url),
          "browser_read": lambda: browser().snapshot(),
          "browser_fill": lambda target, value: browser().fill(target, value),
          "browser_click": lambda target: browser().click(target)}[name]
    last = None
    for attempt in range(retries + 1):
        try:
            out = fn(**args)
            status = out.get("http_status") if isinstance(out, dict) else None
            if status and status >= 500:
                raise RuntimeError(f"server error {status}")
            return out
        except Exception as e:
            last = str(e)[:300]
            time.sleep(0.5 * (attempt + 1))
    snap = browser().snapshot() if name.startswith("browser") else None
    return {"error": last, "attempts": retries + 1, "page_state": snap}