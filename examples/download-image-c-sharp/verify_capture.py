"""Compare stable outcomes; platform exception names are diagnostic only."""
import json
import sys

def stable(path):
    data = json.load(open(path, encoding="utf-8"))
    for case in data["cases"]:
        case.pop("error_type")
    return data

assert stable(sys.argv[1]) == stable(sys.argv[2]), "Current outcomes differ from the captured byte/case oracle"
