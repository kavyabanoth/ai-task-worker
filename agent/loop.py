import json, os, time
from openai import OpenAI
from agent.tools import TOOLS, execute
from agent.memory import Memory

client = OpenAI(api_key=os.environ["LLM_API_KEY"], base_url=os.environ["LLM_BASE_URL"])
MODEL = os.environ["LLM_MODEL"]

OPENAI_TOOLS = [{"type": "function", "function": {
    "name": t["name"], "description": t["description"],
    "parameters": t["input_schema"]}} for t in TOOLS]

SYSTEM = """You are an autonomous task worker operating a computer.
Internal finance system: http://localhost:5000 (pages: /, /new). Invoice files: data/invoices/.
Rules:
1. Plan briefly, then act with tools. Observe each result before the next step.
2. If a tool errors or the page looks wrong, adapt: re-read the page, try another selector (prefer visible text), or retry.
3. If the request is ambiguous or risky, use ask_human instead of guessing.
3b. Before choosing a "latest" file, read EVERY candidate file and compare issue dates. Never guess from file names.
3c. Do ONLY what the task asks. Never click Mark Paid, delete, or any other action the task did not request. New invoices must be saved with status "pending". The expected values you pass to verify must describe the outcome the USER requested, not extra actions you took.
4. Never claim success without calling verify with the exact expected values
   (keys: vendor, amount, due_date, status). If verify fails, fix the problem and verify again.
5. Finish with a short summary: what you did, evidence (values saved), any retries."""

def call_llm(messages):
    for attempt in range(6):
        try:
            return client.chat.completions.create(
                model=MODEL, messages=messages, tools=OPENAI_TOOLS, max_tokens=1500)
        except Exception as e:
            print(f"[LLM error attempt {attempt+1}] {str(e)[:300]}")
            if "429" in str(e) or "rate" in str(e).lower() or "quota" in str(e).lower():
                time.sleep(20 * (attempt + 1))
            else:
                raise
    raise RuntimeError("LLM rate limit not clearing")

def reflect(errors):
    prompt = ("A tool-using agent hit these errors and then recovered:\n- " + "\n- ".join(errors[:6]) +
              "\nWrite ONE general lesson, max 25 words, that helps a future agent avoid this. "
              "Do not mention specific ids that may change. Output only the lesson.")
    try:
        r = client.chat.completions.create(model=MODEL, max_tokens=80,
                                           messages=[{"role": "user", "content": prompt}])
        return r.choices[0].message.content.strip()
    except Exception:
        return "Re-read the page elements before clicking; ids can change between page loads."

def run(goal, max_steps=30, auto_approve=False):
    mem = Memory(goal)
    system = SYSTEM
    if mem.lessons:
        system += "\nLessons from earlier runs:\n- " + "\n- ".join(mem.lessons)
    msgs = [{"role": "system", "content": system},
            {"role": "user", "content": goal}]
    errors = []
    for step in range(max_steps):
        msg = call_llm(msgs).choices[0].message
        msgs.append(msg.model_dump(exclude_none=True))
        if not msg.tool_calls:
            if errors:
                mem.add_lesson(reflect(errors))
            return mem.finish(msg.content or "")
        for tc in msg.tool_calls:
            name = tc.function.name
            args = json.loads(tc.function.arguments or "{}")
            out = execute(name, args, mem, auto_approve=auto_approve)
            mem.log(step, name, args, out)
            print(f"[{step}] {name} {args} -> {str(out)[:120]}")
            if isinstance(out, dict) and "error" in out:
                errors.append(f"{name}{args} -> {str(out['error'])[:100]}")
            msgs.append({"role": "tool", "tool_call_id": tc.id,
                         "content": json.dumps(out)[:6000]})
        time.sleep(13)
    return mem.finish("Stopped: step limit reached without completing")