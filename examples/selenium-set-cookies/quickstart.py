"""Run with: python quickstart.py. Only synthetic localhost data is used."""
import json
import tempfile
from pathlib import Path

from catalog_fixture import fixture_server
from browser_matrix import browser, extract
from cookie_state import save_snapshot, restore_snapshot


def main():
    with fixture_server() as (server, base), tempfile.TemporaryDirectory() as tmp:
        snapshot = Path(tmp) / 'cookies.json'
        with browser('chrome') as driver:
            # This fixture issues a demo session; no real login is performed.
            driver.get(base + '/seed')
            driver.get(base + '/catalog/')
            driver.delete_cookie('demo_region')
            driver.add_cookie({
                'name': 'demo_region', 'value': 'eu', 'path': '/',
                'secure': True, 'sameSite': 'Lax',
            })
            save_snapshot(driver, snapshot, base)

        with browser('chrome') as driver:
            driver.get(base + '/blank')
            restored = restore_snapshot(driver, snapshot, base)
            result = extract(driver, server, base, 'quickstart', 4)
            print(json.dumps({
                'restored': restored,
                'matching_records': result['matching_records'],
                'records': result['records'],
            }, indent=2))
            assert result['assertion_passed']


if __name__ == '__main__':
    main()
