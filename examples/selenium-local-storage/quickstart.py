"""Complete bootstrap → safe seed → navigate → wait for actual records example."""
import json
from browser_support import browser, wait_catalog
from catalog_fixture import fixture_server
from oracle import exact_dataset
from storage_state import set_item


def main():
    with fixture_server() as (_, origin), browser() as driver:
        driver.get(origin+'/blank')  # A document on the target origin, before application startup.
        set_item(driver, 'demo_region', 'eu')
        driver.get(origin+'/catalog')
        page = wait_catalog(driver, stored_region='eu', rendered_region='eu')
        assert exact_dataset(page['records'])
        print(json.dumps({'stored_region': page['stored_region'], 'request_path': page['request_path'],
                          'records': page['records'], 'matching_records': 4}, indent=2))


if __name__ == '__main__':
    main()
