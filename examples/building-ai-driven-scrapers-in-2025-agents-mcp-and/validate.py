"""Offline validation. oracle.json is scoring data, never model input."""
import json
from collections import Counter
from pathlib import Path

from jsonschema import Draft202012Validator, validators

HERE = Path(__file__).resolve().parent
SCHEMA = json.loads((HERE / 'schema.json').read_text())
ORACLE = json.loads((HERE / 'oracle.json').read_text())
# JSON Schema normally permits 1.0 as an integer; this packet permits Python
# integers only (and excludes bool), so no numeric coercion occurs.
StrictValidator = validators.extend(
    Draft202012Validator,
    type_checker=Draft202012Validator.TYPE_CHECKER.redefine(
        'integer', lambda checker, value: type(value) is int),
)
RECORD_VALIDATOR = StrictValidator(SCHEMA['properties']['records']['items'])


def _result(case_id, emitted_count=0):
    expected = ORACLE[case_id]
    return {'case_id': case_id, 'accepted': [], 'quarantine': [],
            'omissions': [], 'errors': [], 'emitted_count': emitted_count,
            'expected_count': len(expected), 'schema_valid_count': 0,
            'exact_match_count': 0, 'oracle_value_match_count': 0, 'accepted_count': 0, 'duplicate_ids': [],
            'hallucinated_ids': [], 'complete_run_success': False}


def _finish(result, seen):
    expected_ids = {r['id'] for r in ORACLE[result['case_id']]}
    result['omissions'] = sorted(expected_ids - seen)
    result['accepted_count'] = len(result['accepted'])
    result['exact_match_count'] = result['oracle_value_match_count']
    result['schema_pass_rate'] = (result['schema_valid_count'] / result['emitted_count']
                                  if result['emitted_count'] else None)
    result['precision'] = (result['exact_match_count'] / result['emitted_count']
                           if result['emitted_count'] else None)
    result['recall'] = (result['exact_match_count'] / result['expected_count']
                        if result['expected_count'] else None)
    result['complete_run_success'] = (not result['errors'] and not result['quarantine']
                                      and not result['omissions'])
    return result


def validate_records(payload, markdown, source_url, case_id):
    """Validate parsed model JSON without repairing it.

    Schema counts describe individual records, even when the top-level envelope
    is invalid. Acceptance also requires the strict envelope, a unique known ID,
    exact oracle values, the acquisition URL, and an exact source excerpt that
    contains the oracle's product statement. Unavailable/ambiguous records
    always quarantine; their null values never become accepted records.
    oracle_value_match_count (also exact_match_count) scores source-value
    accuracy including correct nulls, independently of acceptance/provenance.
    Precision and recall use value matches; accepted_count counts safe records.
    """
    if case_id not in ORACLE:
        raise ValueError(f'Unknown fixture case: {case_id}')
    if not isinstance(markdown, str) or not isinstance(source_url, str):
        raise TypeError('markdown and source_url must be strings')
    records = payload.get('records') if isinstance(payload, dict) else None
    envelope_ok = isinstance(payload, dict) and set(payload) == {'records'} and isinstance(records, list)
    if not isinstance(records, list):
        result = _result(case_id)
        result['errors'].append('invalid_envelope: expected exactly {records: array}')
        return _finish(result, set())
    result = _result(case_id, len(records))
    if not envelope_ok:
        result['errors'].append('invalid_envelope: unexpected top-level keys')
    oracle = {r['id']: r for r in ORACLE[case_id]}
    counts = Counter(r['id'] for r in records if isinstance(r, dict) and isinstance(r.get('id'), str))
    result['duplicate_ids'] = sorted(k for k, n in counts.items() if n > 1)
    result['hallucinated_ids'] = sorted(set(counts) - set(oracle))
    for record in records:
        errors = sorted(RECORD_VALIDATOR.iter_errors(record), key=lambda e: str(list(e.path)))
        reasons = [f'schema:{"/".join(map(str, e.path)) or "$"}: {e.message}' for e in errors]
        if not errors:
            result['schema_valid_count'] += 1
        if not envelope_ok:
            reasons.append('invalid_envelope')
        rid = record.get('id') if isinstance(record, dict) else None
        expected = oracle.get(rid) if isinstance(rid, str) else None
        if isinstance(rid, str) and counts[rid] > 1:
            reasons.append('duplicate_id')
        if expected is None:
            reasons.append('unknown_or_missing_id')
        elif isinstance(record, dict):
            value_match = (not errors and counts[rid] == 1 and all(
                field in record and type(record[field]) is type(expected[field])
                and record[field] == expected[field]
                for field in ('id', 'title', 'price_minor', 'currency')))
            if value_match:
                result['oracle_value_match_count'] += 1
            if expected['status'] != 'available':
                reasons.append('oracle_' + expected['status'])
            for field in ('id', 'title', 'price_minor', 'currency'):
                if field not in record or type(record[field]) is not type(expected[field]) or record[field] != expected[field]:
                    reasons.append('oracle_mismatch:' + field)
            excerpt = record.get('evidence')
            if not isinstance(excerpt, str) or not excerpt or excerpt not in markdown:
                reasons.append('evidence_not_in_source')
            elif ' '.join(expected['evidence'].split()) not in ' '.join(excerpt.split()):
                reasons.append('evidence_does_not_support_record')
        if isinstance(record, dict) and record.get('source_url') != source_url:
            reasons.append('source_url_mismatch')
        if reasons:
            result['quarantine'].append({'record': record, 'reasons': reasons})
        else:
            result['accepted'].append(record)
    return _finish(result, set(counts))


def validate_json(text, markdown, source_url, case_id):
    """Reject malformed JSON, duplicate object keys and non-JSON constants."""
    def pairs(items):
        obj = {}
        for key, value in items:
            if key in obj:
                raise ValueError(f'duplicate JSON key: {key}')
            obj[key] = value
        return obj

    def constant(value):
        raise ValueError(f'invalid JSON constant: {value}')

    try:
        payload = json.loads(text, object_pairs_hook=pairs, parse_constant=constant)
    except (ValueError, TypeError) as error:
        result = _result(case_id)
        result['errors'].append('malformed_json: ' + str(error))
        return _finish(result, set())
    return validate_records(payload, markdown, source_url, case_id)
