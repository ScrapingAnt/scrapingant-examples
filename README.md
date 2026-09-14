# scrapingant-examples

Runnable evidence behind articles on the [ScrapingAnt blog](https://scrapingant.com/blog/). Every article that makes a technical claim points at a folder here containing the code, pinned dependencies, fixtures and the captured output from the run the article describes.

## Layout
```
examples/<article-slug>/
  README.md          what it demonstrates, how to run
  run.sh             runs every approach, writes expected_output/*.txt, exits non-zero on failure
  requirements.txt   pinned exactly as tested (or package.json)
  fixtures/          local inputs
  expected_output/   captured output from the recorded run
  evidence.yaml      manifest: versions, tested_at, measurements, claims
fixtures/            shared fixtures served via GitHub Pages
```

## Running an example
```bash
cd examples/<slug>
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
./run.sh
```
Steps that call the ScrapingAnt API read `SCRAPINGANT_API_KEY` from the environment (free key: https://app.scrapingant.com/signup).

## CI
`run-examples` runs monthly and on demand for every id in `examples.allowlist.json`. A failure opens an issue labelled `example-failed`; nothing is auto-fixed. The article is then reviewed and refreshed by a person.

## evidence.yaml contract
See `examples/_template/evidence.yaml`. `tested_at` is the date of the run whose output is committed; `claims[]` are the statements the article is allowed to make from this packet.
