import json, os, time

LESSONS = "traces/lessons.json"

class Memory:
    def __init__(self, goal):
        self.goal, self.facts, self.steps = goal, {}, []
        self.lessons = json.load(open(LESSONS)) if os.path.exists(LESSONS) else []

    def log(self, step, tool, args, out):
        self.steps.append({"step": step, "tool": tool, "args": args, "out": str(out)[:400]})

    def add_lesson(self, text):
        if text not in self.lessons:
            self.lessons.append(text)
            json.dump(self.lessons[-20:], open(LESSONS, "w"), indent=1)

    def finish(self, summary):
        os.makedirs("traces", exist_ok=True)
        path = f"traces/run_{int(time.time())}.json"
        json.dump({"goal": self.goal, "facts": self.facts,
                   "summary": summary, "steps": self.steps}, open(path, "w"), indent=1)
        return {"summary": summary, "trace": path, "steps": len(self.steps)}