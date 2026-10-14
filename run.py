import sys, json
from agent.loop import run

auto = "--auto" in sys.argv
goal = " ".join(a for a in sys.argv[1:] if a != "--auto")
print(json.dumps(run(goal, auto_approve=auto), indent=2))