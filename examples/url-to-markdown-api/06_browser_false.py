"""browser=false on the static fixture: cost and whether the Markdown differs from the browser=true run."""
from _common import FIXTURE, cached, require_key

require_key()
i_true, md_true = cached("fixture", "markdown", FIXTURE, "true")
i_false, md_false = cached("fixture", "markdown", FIXTURE, "false")
print("browser=true : status", i_true["status"], "cost", i_true["cost"], "page", i_true["page_status"])
print("browser=false: status", i_false["status"], "cost", i_false["cost"], "page", i_false["page_status"])
print("markdown identical:", md_true == md_false)
if md_true != md_false:
    import difflib
    print("\n".join(list(difflib.unified_diff(md_true.splitlines(), md_false.splitlines(), "browser=true", "browser=false", lineterm="", n=0))[:20]))
