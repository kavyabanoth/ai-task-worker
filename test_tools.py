from agent.tools import browser, list_files, read_file

print(list_files("data/invoices"))
print(read_file("data/invoices/Company_X_INV-143.pdf")["text"])

snap = browser().goto("http://localhost:5000/new")
print(snap["http_status"])
for e in snap["elements"]:
    print(e)
    