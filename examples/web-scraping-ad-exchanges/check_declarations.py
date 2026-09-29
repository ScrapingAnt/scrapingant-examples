"""Offline diagnostic for owned fixtures, not a production IAB validator."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
DOMAIN = re.compile(r"(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")


def normalize_domain(value):
    value = value.lower()  # Do not strip www, reduce subdomains, or equate domains.
    if not DOMAIN.fullmatch(value):
        raise ValueError('unsupported domain')
    return value


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate JSON member')
        result[key] = value
    return result


def reject_constant(value):
    raise ValueError(f'non-JSON constant: {value}')


def load_sellers(path):
    """Reject the entire input on parse/schema errors before checking absence."""
    provenance = {'file': f'fixtures/{path.name}', 'sha256': None}
    try:
        body = path.read_bytes()
    except OSError:
        return None, 'input_unavailable', provenance
    provenance['sha256'] = hashlib.sha256(body).hexdigest()
    try:
        data = json.loads(body, object_pairs_hook=unique_object,
                          parse_constant=reject_constant)
    except (ValueError, UnicodeError):
        return None, 'invalid_json', provenance
    if (not isinstance(data, dict) or data.get('version') != '1.0'
            or not isinstance(data.get('sellers'), list)):
        return None, 'invalid_sellers_schema', provenance
    index = {}
    for offset, seller in enumerate(data['sellers']):
        if not isinstance(seller, dict):
            return None, 'invalid_sellers_schema', provenance
        sid = seller.get('seller_id')
        kind = seller.get('seller_type')
        confidential = seller.get('is_confidential', 0)
        if (not isinstance(sid, str) or not sid or sid != sid.strip()
                or not isinstance(kind, str)
                or kind.upper() not in {'PUBLISHER', 'INTERMEDIARY', 'BOTH'}
                or type(confidential) is not int or confidential not in (0, 1)
                or (confidential == 0 and (not isinstance(seller.get('name'), str)
                                           or not seller['name'].strip()))
                or ('domain' in seller and (not isinstance(seller['domain'], str)
                                            or not seller['domain'].strip()))):
            return None, 'invalid_sellers_schema', provenance
        # Domains are reported as supplied, not compared to the inventory domain.
        record = {'seller_index': offset, 'seller_id': sid,
                  'seller_type': kind.upper(), 'is_confidential': confidential,
                  'name': seller.get('name'), 'business_domain': seller.get('domain')}
        index.setdefault(sid, []).append(record)
    return index, None, provenance


def classify(index, error, seller_id):
    if error:
        return 'uncheckable', error, []
    matches = index.get(seller_id, [])
    if len(matches) > 1:
        return 'ambiguous', 'multiple_seller_records', matches
    if not matches:
        return 'absent', 'seller_id_not_in_complete_fixture', []
    if matches[0]['is_confidential'] == 1:
        return 'confidential', 'identity_withheld', matches
    return 'matching', 'seller_id_found', matches


def build_report(fixtures=ROOT / 'fixtures'):
    config = json.loads((fixtures / 'sources.json').read_text())
    if config.get('kind') != 'owned_synthetic' or config.get('complete_fixture_inputs') is not True:
        raise ValueError('This teaching runner accepts declared complete owned fixtures only')
    ads_path = fixtures / config['ads_file']
    ads_body = ads_path.read_bytes()
    sources = {'ads': {'file': f'fixtures/{ads_path.name}',
                       'sha256': hashlib.sha256(ads_body).hexdigest()}, 'sellers': {}}
    rows, variables, seen, loaded = [], [], {}, {}
    for line_number, raw in enumerate(ads_body.decode('utf-8').splitlines(), 1):
        line = raw.split('#', 1)[0].strip()
        if not line:
            continue
        if re.match(r'^[^\s,=]+\s*=', line):
            name, value = line.split('=', 1)
            variables.append({'line': line_number, 'name': name.strip(), 'value': value.strip(),
                              'interpreted': False})
            continue
        row = {'line': line_number, 'raw': raw, 'publisher': config['publisher'],
               'ads_source': sources['ads']['file']}
        rows.append(row)
        fields = [part.strip() for part in line.split(',')]
        try:
            if (len(fields) not in (3, 4) or not all(fields)
                    or any(re.search(r'\s|;', part) for part in fields)
                    or fields[2].upper() not in {'DIRECT', 'RESELLER'}):
                raise ValueError('unsupported ads row')
            domain = normalize_domain(fields[0])
        except ValueError:
            row.update(status='invalid', reason='invalid_ads_record')
            continue
        sid, relationship = fields[1], fields[2].upper()
        certificate = fields[3] if len(fields) == 4 else None
        row.update(advertising_system=domain, seller_id=sid,
                   relationship=relationship, certification_id=certificate)
        key = (domain, sid, relationship, certificate)
        if key in seen:
            row.update(status='duplicate', reason='repeated_ads_record', duplicate_of=seen[key])
            continue
        seen[key] = line_number
        if domain not in config['seller_files']:
            row.update(status='uncheckable', reason='domain_not_allowlisted', matches=[])
            continue
        if domain not in loaded:
            loaded[domain] = load_sellers(fixtures / config['seller_files'][domain])
        index, error, provenance = loaded[domain]
        sources['sellers'][domain] = provenance
        status, reason, matches = classify(index, error, sid)
        row.update(status=status, reason=reason, sellers_source=provenance['file'], matches=matches)
    counts = Counter(row['status'] for row in rows)
    totals = {'parsed_data_rows': len(rows),
              'valid_join_candidates': len(rows) - counts['invalid'] - counts['duplicate'],
              'invalid_rows': counts['invalid'], 'duplicate_rows': counts['duplicate'],
              'variable_rows': len(variables),
              'unavailable_sellers_inputs': sum(error == 'input_unavailable'
                                                for _, error, _ in loaded.values())}
    for status in ('matching', 'absent', 'confidential', 'ambiguous', 'uncheckable'):
        totals[status] = counts[status]
    return {'kind': 'owned_synthetic', 'diagnostic_only': True,
            'sources': sources, 'variables': variables, 'rows': rows, 'counts': totals}


def summary(report):
    lines = ['Owned synthetic fixture: declaration lookups, not transaction validation.',
             'line  system                seller_id   relationship  status        reason']
    for row in report['rows']:
        lines.append(f"{row['line']:>4}  {row.get('advertising_system', '-'):21} "
                     f"{row.get('seller_id', '-'):11} {row.get('relationship', '-'):13} "
                     f"{row['status']:13} {row['reason']}")
    lines.append('Counts: ' + json.dumps(report['counts'], sort_keys=True))
    return '\n'.join(lines)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--format', choices=['json', 'text'], default='json')
    args = parser.parse_args()
    report = build_report()
    print(json.dumps(report, indent=2) if args.format == 'json' else summary(report))
