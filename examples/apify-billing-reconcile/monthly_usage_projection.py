"""PRIVATE, pure projection of two documented read-only account responses.

No transport, execution, environment, token, profile, payment or file handling.
Sources read 2026-10-03:
https://docs.apify.com/api/v2/users-me-usage-monthly-get
https://docs.apify.com/api/v2/users-me-limits-get
Native run-usage field names: reviewed examples/apify-study/billing_projection.py.
Raw responses belong only in memory; persist this explicit projection encrypted.
"""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, localcontext
import json
import re

EXECUTION_READY = False
REQUESTED_DATE = '2026-10-03'
RESPONSE_LIMIT = 131072
MAX_SERVICE_FIELDS = 128
MAX_CYCLE_SPAN = timedelta(days=32)  # Closed review bound for a monthly snapshot.
MAX_NUMBER = Decimal('1e18')
SERVICES = {
    'ACTOR_COMPUTE_UNITS': 'CU',
    'DATASET_READS': 'reported_operation_count',
    'DATASET_WRITES': 'reported_operation_count',
    'KEY_VALUE_STORE_READS': 'reported_operation_count',
    'KEY_VALUE_STORE_WRITES': 'reported_operation_count',
    'KEY_VALUE_STORE_LISTS': 'reported_operation_count',
    'REQUEST_QUEUE_READS': 'reported_operation_count',
    'REQUEST_QUEUE_WRITES': 'reported_operation_count',
    'DATA_TRANSFER_INTERNAL_GBYTES': 'API_Gbytes',
    'DATA_TRANSFER_EXTERNAL_GBYTES': 'API_Gbytes',
    'PROXY_RESIDENTIAL_TRANSFER_GBYTES': 'API_Gbytes',
    'PROXY_SERPS': 'reported_SERP_count',
}
MAXIMUM_FIELDS = ('maxMonthlyUsageUsd', 'maxActorMemoryGbytes',
                  'maxConcurrentActorJobs', 'dataRetentionDays')
CURRENT_FIELDS = ('monthlyUsageUsd', 'actorMemoryGbytes', 'activeActorJobCount')
INTEGER_FIELDS = ('maxConcurrentActorJobs', 'activeActorJobCount', 'dataRetentionDays')


class ProjectionError(ValueError):
    def __init__(self):
        super().__init__('monthly_usage_projection_invalid')


def parse_response(blob):
    """Bounded strict UTF-8 JSON; decimal text is preserved before projection."""
    if not isinstance(blob, bytes) or not 1 <= len(blob) <= RESPONSE_LIMIT:
        raise ProjectionError()

    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ProjectionError()
            result[key] = value
        return result

    def integer(text):
        if len(text) > 96:
            raise ProjectionError()
        value = int(text)
        if abs(value) > MAX_NUMBER:
            raise ProjectionError()
        return value

    def fractional(text):
        if len(text) > 96:
            raise ProjectionError()
        value = Decimal(text)
        if (not value.is_finite() or abs(value) > MAX_NUMBER
                or not -64 <= value.as_tuple().exponent <= 18):
            raise ProjectionError()
        return value

    def constant(_):
        raise ProjectionError()

    try:
        value = json.loads(blob.decode('utf-8'), object_pairs_hook=pairs,
            parse_int=integer, parse_float=fractional, parse_constant=constant)
        if not isinstance(value, dict):
            raise ProjectionError()
        return value
    except (ValueError, UnicodeError, RecursionError, InvalidOperation):
        raise ProjectionError() from None


def presence(parent, key):
    if not isinstance(parent, dict) or key not in parent:
        return {'state': 'absent'}
    return {'state': 'null' if parent[key] is None else 'present'}


def object_field(parent, key):
    state = presence(parent, key)
    if state['state'] != 'present':
        return state, {}
    value = parent[key]
    if not isinstance(value, dict):
        return {'state': 'invalid'}, {}
    return {'state': 'object'}, value


def numeric(parent, key, *, integer=False):
    """Reject already rounded binary floats; never coerce strings or booleans."""
    state = presence(parent, key)
    if state['state'] != 'present':
        return state
    value = parent[key]
    if type(value) not in (int, Decimal):
        return {'state': 'invalid'}
    try:
        if len(str(value)) > 96:
            return {'state': 'invalid'}
        number = Decimal(value)
        if (not number.is_finite() or not 0 <= number <= MAX_NUMBER
                or not -64 <= number.as_tuple().exponent <= 18):
            return {'state': 'invalid'}
        if integer and (number != number.to_integral_value() or number > 1000000):
            return {'state': 'invalid'}
        return {'state': 'number', 'value': str(int(number)) if integer else format(number, 'f')}
    except (ValueError, InvalidOperation, OverflowError):
        return {'state': 'invalid'}


def selected_day(value):
    if type(value) is not str or re.fullmatch(r'\d{4}-\d{2}-\d{2}', value) is None:
        raise ProjectionError()
    try:
        day = date.fromisoformat(value)
        return datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
    except ValueError:
        raise ProjectionError() from None


def timestamp(value):
    if (type(value) is not str or re.fullmatch(
            r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|\+00:00)', value) is None):
        return None
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        return None


def cycle(parent, key, target):
    state, source = object_field(parent, key)
    if state['state'] != 'object':
        return state
    start, end = timestamp(source.get('startAt')), timestamp(source.get('endAt'))
    if (start is None or end is None or not start <= target <= end or start >= end
            or end - start > MAX_CYCLE_SPAN):
        return {'state': 'invalid'}
    return {'state': 'valid',
        'start_at': start.isoformat(timespec='microseconds').replace('+00:00', 'Z'),
        'end_at': end.isoformat(timespec='microseconds').replace('+00:00', 'Z')}


def service(parent, name, unit):
    state, source = object_field(parent, name)
    result = {**state, 'quantity_unit': unit, 'monetary_currency': 'USD',
        'unit_price_denominator': 'one_reported_native_quantity_unit'}
    for field in ('quantity', 'baseAmountUsd', 'baseUnitPriceUsd', 'amountAfterVolumeDiscountUsd'):
        result[field] = numeric(source, field)
    result['schema_complete'] = (state['state'] == 'object'
        and all(result[field]['state'] == 'number' for field in ('quantity', 'baseAmountUsd'))
        and all(result[field]['state'] in ('absent', 'null', 'number')
                for field in ('baseUnitPriceUsd', 'amountAfterVolumeDiscountUsd')))
    return result


def project(monthly, limits, *, requested_date=REQUESTED_DATE):
    """Authoritative account totals and a bounded native-unit private allowlist.

    Missing service keys remain absent. No daily/service/run sum replaces totals;
    no prepaid allowance, tier, billed payment or per-run ancillary is inferred.
    """
    target = selected_day(requested_date)
    monthly_state, source = object_field(monthly, 'data')
    limit_state, account = object_field(limits, 'data')
    mcycle, lcycle = cycle(source, 'usageCycle', target), cycle(account, 'monthlyUsageCycle', target)
    before = numeric(source, 'totalUsageCreditsUsdBeforeVolumeDiscount')
    after = numeric(source, 'totalUsageCreditsUsdAfterVolumeDiscount')
    service_state, values = object_field(source, 'monthlyServiceUsage')
    if service_state['state'] == 'object' and len(values) > MAX_SERVICE_FIELDS:
        service_state, values = {'state': 'invalid'}, {}
    services = {name: service(values, name, unit) for name, unit in SERVICES.items()}
    unknown_count = sum(name not in SERVICES for name in values) if service_state['state'] == 'object' else None
    monthly_complete = (monthly_state['state'] == 'object' and mcycle['state'] == 'valid'
        and before['state'] == after['state'] == 'number' and service_state['state'] == 'object'
        and all(record['state'] == 'absent' or record['schema_complete'] for record in services.values()))
    max_state, maximum = object_field(account, 'limits')
    cur_state, current = object_field(account, 'current')
    max_fields = {name: numeric(maximum, name, integer=name in INTEGER_FIELDS) for name in MAXIMUM_FIELDS}
    cur_fields = {name: numeric(current, name, integer=name in INTEGER_FIELDS) for name in CURRENT_FIELDS}
    limits_complete = (limit_state['state'] == 'object' and lcycle['state'] == 'valid'
        and max_state['state'] == cur_state['state'] == 'object'
        and all(value['state'] == 'number' for value in (*max_fields.values(), *cur_fields.values())))
    match = (mcycle == lcycle) if mcycle['state'] == lcycle['state'] == 'valid' else None
    headroom, has_headroom = {'state': 'unknown'}, None
    if limits_complete and monthly_complete and match is True:
        with localcontext() as context:
            context.prec = 100
            remaining = Decimal(max_fields['maxMonthlyUsageUsd']['value']) - Decimal(cur_fields['monthlyUsageUsd']['value'])
            headroom = {'state': 'number', 'value': format(remaining, 'f')}
            has_headroom = remaining >= Decimal('3.10')
    return {'schema_version': 1, 'evidence_type': 'private_monthly_usage_projection',
        'requested_date': requested_date, 'monetary_currency': 'USD',
        'monthly': {'data_state': monthly_state['state'], 'cycle': mcycle,
            'total_before_volume_discount_usd': before, 'total_after_volume_discount_usd': after,
            'service_map_state': service_state['state'], 'services': services,
            'unprojected_service_count': unknown_count,
            'all_service_names_projected': unknown_count == 0 if unknown_count is not None else None,
            'schema_complete': monthly_complete},
        'limits': {'data_state': limit_state['state'], 'cycle': lcycle,
            'maximum': max_fields, 'current': cur_fields, 'schema_complete': limits_complete,
            'memory_unit': 'API_Gbytes_no_conversion_inferred',
            'retention_unit': 'reported_days_not_store_specific_guarantee',
            'monthly_limit_headroom_usd': headroom, 'has_3_10_usd_headroom': has_headroom,
            'monthly_limit_is_prepaid_allowance': False},
        'cycles_match': match, 'schema_complete': monthly_complete and limits_complete and match is True,
        'execution_ready': False, 'invoice_finality': False,
        'account_total_is_study_only': False, 'individual_run_ancillary_reconciled': False,
        'console_account_association_verified': False,
        'historical_applied_account_tier_verified': False,
        'limits_vs_monthly_amount_basis_verified': False,
        'two_responses_are_atomic_snapshot': False,
        'service_or_daily_totals_added_to_account_total': False,
        'unit_price_inferred_from_amount_quantity': False,
        'prepaid_allowance_subtracted_from_usage': False}


def public_projection(private):
    """Fresh fixed public booleans only; no amount, timestamp, unit, tier or ID."""
    private = private if isinstance(private, dict) else {}
    _, monthly = object_field(private, 'monthly')
    _, limits = object_field(private, 'limits')

    def boolean(value):
        return value if type(value) is bool else None

    return {'schema_version': 1, 'evidence_type': 'encrypted_monthly_usage_projection',
        'monthly_complete': boolean(monthly.get('schema_complete')),
        'limits_complete': boolean(limits.get('schema_complete')),
        'association_valid': boolean(private.get('cycles_match')),
        'execution_ready': False, 'invoice_finality': False}
