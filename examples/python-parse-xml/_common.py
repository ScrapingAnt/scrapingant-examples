def show(label, fn):
    """Run fn() and print one line: the result, or the exception instead of a traceback, so the script continues."""
    try:
        print(f"{label}: {fn()}")
    except Exception as e:  # noqa: BLE001
        mod = type(e).__module__
        name = type(e).__name__ if mod == "builtins" else f"{mod}.{type(e).__name__}"
        print(f"{label}: {name}: {str(e)[:300]}")
