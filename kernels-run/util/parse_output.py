import json
import re
import sys

from env import RESULT_FILE_FAASM

get_name = False
p = re.compile("prk/(.*):[0-9]*")
value = None
results = {}

for line in sys.stdin:
    if get_name:
        if "Finished prk/" in line:
            a = line.rstrip("\n").split(" ")[-1]
            result = p.search(line.rstrip("\n").split(" ")[-1])
            func = result.group(1)
            if func not in results:
                results[func] = []
            results[func].append(float(value))
            get_name = False
        else:
            # Sometimes an RPC error message gets between the time and the
            # output
            continue
    if "Avg time (s)" in line or get_name:
        value = line.rstrip("\n").split(" ")[-1]
        get_name = True
        continue

print(json.dumps(results))
with open(RESULT_FILE_FAASM, "w") as json_file:
    json.dump(results, json_file)
