"""Independent literal oracles and transparent, per-target summaries."""
import math
import random
import statistics

from bs4 import BeautifulSoup

TARGETS = {
    'static': {
        'file': 'html-tables.html',
        'url': 'https://scrapingant.github.io/scrapingant-examples/fixtures/html-tables.html',
        'selector': '#prices tbody tr',
        'expected': [
            ['Ant Farm Deluxe', '$1,234.50', '12,345', '45.5%'],
            ['Ant Farm Mini', '$99.00', '1,020', '3.8%'],
            ['Magnifier', '$12.25', '987,654', '50.7%'],
        ],
    },
    'delayed': {
        'file': 'dynamic-delayed.html',
        'url': 'https://scrapingant.github.io/scrapingant-examples/fixtures/dynamic-delayed.html',
        'selector': '#loaded',
        'expected': [['I ❤️ ScrapingAnt (after 1500 ms)']],
    },
}
ARMS = ('requests', 'playwright', 'api_raw', 'api_rendered')


def assess(target, html, status, target_status):
    doc = BeautifulSoup(html, 'html.parser')
    if target == 'static':
        records = [[cell.get_text(strip=True) for cell in row.select('td')]
                   for row in doc.select('#prices tbody tr')]
        ready = len(doc.select('#prices')) == 1
    elif target == 'delayed':
        records = [[node.get_text(strip=True)] for node in doc.select('#test')]
        ready = len(doc.select('#loaded')) == 1
    else:
        raise ValueError('Unknown target')
    valid = (status == 200 and target_status == 200 and ready
             and records == TARGETS[target]['expected'])
    outcome = 'valid' if valid else ('status_failure' if status != 200 or target_status != 200 else 'invalid_contract')
    return dict(valid=valid, valid_records=len(records) if valid else 0,
                records=records, ready=ready, outcome=outcome)


def schedule(arms, repeats, seed):
    rng = random.Random(seed)
    plan = []
    for round_id in range(repeats):
        targets = list(TARGETS); rng.shuffle(targets)
        for target in targets:
            order = list(arms); rng.shuffle(order)
            plan.extend((round_id, target, arm) for arm in order)
    return plan


def api_parameters(target, arm, url):
    if arm not in ('api_raw', 'api_rendered'):
        raise ValueError('Not an API arm')
    params = dict(url=url, browser='true' if arm == 'api_rendered' else 'false',
                  proxy_type='datacenter', timeout=10)
    if arm == 'api_rendered':
        params.update(return_page_source='false', wait_for_selector=TARGETS[target]['selector'])
    return params


def reserve(ceiling, spent, arm):
    expected = {'api_raw': 1, 'api_rendered': 10}[arm]
    if spent + expected > ceiling:
        raise ValueError('Insufficient remaining authorized credits')
    return expected


def wilson(successes, n):
    z = 1.959963984540054
    center = (successes/n + z*z/(2*n))/(1 + z*z/n)
    half = z*math.sqrt(successes/n*(1-successes/n)/n + z*z/(4*n*n))/(1 + z*z/n)
    return [max(0, center-half), min(1, center+half)]


def summary(rows):
    output = []
    for target in TARGETS:
        for arm in ARMS:
            group = [r for r in rows if r['target'] == target and r['arm'] == arm]
            if not group:
                continue
            accepted = [r for r in group if r['valid']]
            records = sum(r['valid_records'] for r in accepted)
            api = arm.startswith('api_')
            known = api and all(type(r['credits']) is int and r['credits'] >= 0 for r in group)
            credits = sum(r['credits'] for r in group) if known else None
            elapsed = [r['elapsed_ms'] for r in group if r['elapsed_ms'] is not None]
            output.append(dict(
                target=target, arm=arm, attempts=len(group), valid_attempts=len(accepted),
                valid_record_observations=records,
                unique_expected_records=len(TARGETS[target]['expected']) if accepted else 0,
                median_all_ms=statistics.median(elapsed) if len(elapsed) == len(group) else None,
                median_valid_ms=statistics.median(r['elapsed_ms'] for r in accepted) if accepted else None,
                observed_range_ms=[min(elapsed), max(elapsed)] if elapsed else None,
                known_elapsed_attempts=len(elapsed),
                wilson95_fixture_attempts=wilson(len(accepted), len(group)),
                credits_total=credits,
                credits_per_valid_record=credits/records if known and records else None,
                cost_status='receipted' if known else ('unknown_receipt' if api else 'local_usd_unmeasured'),
                failures={outcome: sum(r['outcome'] == outcome for r in group)
                          for outcome in sorted({r['outcome'] for r in group if not r['valid']})},
            ))
    return output
