"""Recompute the complete matrix against independent literal expectations."""
import argparse
import json
from pathlib import Path
from oracle import summarize


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    folder = Path(args.input_dir)
    documents = [json.loads((folder / (browser + ".json")).read_text()) for browser in ("chromium", "firefox")]
    result = summarize(documents)
    Path(args.output).write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: result[key] for key in ("extraction_observations", "diagnostic_observations", "passed", "failed")}))
