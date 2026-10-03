"""Synthetic monthly/limits inputs only; no account, credential or transport access."""
import copy
from decimal import Decimal as D
import json
import unittest

import monthly_usage_projection as m

CANARY = 'SYNTHETIC_PRIVATE_PROVIDER_VALUE'
START = '2026-10-02T00:00:00.000Z'
END = '2026-11-01T23:59:59.999Z'


def monthly():
    return {'data': {'usageCycle': {'startAt': START, 'endAt': END},
        'totalUsageCreditsUsdBeforeVolumeDiscount': D('0.5837419281736100123'),
        'totalUsageCreditsUsdAfterVolumeDiscount': D('0.5787419281736100123'),
        'monthlyServiceUsage': {'ACTOR_COMPUTE_UNITS': {
            'quantity': D('2.1234567890123456789'), 'baseAmountUsd': D('0.42469135780246913578'),
            'baseUnitPriceUsd': D('0.2000000000000000000'),
            'amountAfterVolumeDiscountUsd': D('0.42469135780246913578')}},
        'dailyServiceUsages': [{'date': START, 'totalUsageCreditsUsd': 99999}],
        'userId': CANARY, 'payment': {'password': CANARY}}}


def limits():
    return {'data': {'monthlyUsageCycle': {'startAt': START, 'endAt': END},
        'limits': {'maxMonthlyUsageUsd': 19, 'maxActorMemoryGbytes': 64,
            'maxConcurrentActorJobs': 32, 'dataRetentionDays': 90},
        'current': {'monthlyUsageUsd': D('0.5787419281736100123'),
            'actorMemoryGbytes': 0, 'activeActorJobCount': 0},
        'id': CANARY, 'proxy': {'password': CANARY}}}


class ProjectionTests(unittest.TestCase):
    def test_decimal_digits_and_current_limits_survive_without_float_rounding(self):
        result = m.project(monthly(), limits())
        self.assertEqual(result['monthly']['total_before_volume_discount_usd'],
            {'state': 'number', 'value': '0.5837419281736100123'})
        self.assertEqual(result['monthly']['total_after_volume_discount_usd']['value'], '0.5787419281736100123')
        self.assertEqual(result['limits']['current']['monthlyUsageUsd']['value'], '0.5787419281736100123')
        self.assertEqual(result['limits']['monthly_limit_headroom_usd']['value'], '18.4212580718263899877')
        self.assertIs(result['limits']['has_3_10_usd_headroom'], True)
        self.assertTrue(result['schema_complete'])
        self.assertFalse(result['execution_ready'])

    def test_raw_numeric_json_uses_decimal_and_duplicate_keys_are_not_accepted(self):
        parsed = m.parse_response(b'{"data":{"precise":0.13660374560593733001,"integer":32}}')
        self.assertEqual(parsed['data']['precise'], D('0.13660374560593733001'))
        self.assertIs(type(parsed['data']['integer']), int)
        for blob in (b'{"data":{},"data":{}}', b'{"a":NaN}', b'{"a":Infinity}',
                     b'{"a":1e999}', b'[]', b'\xff', b'{', b'{"a":' + b'9' * 97 + b'}'):
            with self.subTest(blob_length=len(blob)), self.assertRaisesRegex(m.ProjectionError, '^monthly_usage_projection_invalid$'):
                m.parse_response(blob)

    def test_body_limit_rejects_before_parsing(self):
        with self.assertRaises(m.ProjectionError):
            m.parse_response(b' ' * (m.RESPONSE_LIMIT + 1))

    def test_missing_null_zero_invalid_are_four_distinct_states(self):
        key = 'totalUsageCreditsUsdAfterVolumeDiscount'
        for value, state in ((None, 'null'), (0, 'number'), (True, 'invalid'),
                ('0', 'invalid'), (0.1, 'invalid'), (-1, 'invalid'), (D('NaN'), 'invalid'),
                (D('1e-65'), 'invalid'), (D('1e19'), 'invalid')):
            source = monthly(); source['data'][key] = value
            result = m.project(source, limits())
            self.assertEqual(result['monthly']['total_after_volume_discount_usd']['state'], state)
            self.assertEqual(result['schema_complete'], state == 'number')
        source = monthly(); del source['data'][key]
        self.assertEqual(m.project(source, limits())['monthly']['total_after_volume_discount_usd'], {'state': 'absent'})

    def test_account_total_is_not_sum_of_services_daily_values_or_run_meters(self):
        source = monthly()
        source['data']['monthlyServiceUsage']['ACTOR_COMPUTE_UNITS']['baseAmountUsd'] = 99999
        source['data']['usageTotalUsd'] = 88888
        result = m.project(source, limits())
        self.assertEqual(result['monthly']['total_after_volume_discount_usd']['value'], '0.5787419281736100123')
        self.assertFalse(result['invoice_finality'])
        self.assertFalse(result['individual_run_ancillary_reconciled'])
        self.assertFalse(result['account_total_is_study_only'])
        self.assertNotIn('dailyServiceUsages', json.dumps(result))
        self.assertNotIn('88888', json.dumps(result))

    def test_only_documented_units_and_observed_unit_prices_no_price_inference(self):
        source = monthly(); usage = source['data']['monthlyServiceUsage']['ACTOR_COMPUTE_UNITS']
        del usage['baseUnitPriceUsd']; usage['quantity'] = 2; usage['baseAmountUsd'] = 10
        source['data']['monthlyServiceUsage']['DATA_TRANSFER_EXTERNAL_GBYTES'] = {'quantity': D('0.01'), 'baseAmountUsd': 1}
        result = m.project(source, limits())['monthly']['services']
        self.assertEqual(result['ACTOR_COMPUTE_UNITS']['quantity_unit'], 'CU')
        self.assertEqual(result['ACTOR_COMPUTE_UNITS']['baseUnitPriceUsd'], {'state': 'absent'})
        self.assertEqual(result['DATA_TRANSFER_EXTERNAL_GBYTES']['quantity_unit'], 'API_Gbytes')
        self.assertEqual(result['DATASET_READS']['state'], 'absent')

    def test_unknown_service_labels_tiers_and_provider_values_never_survive(self):
        source = monthly(); source['data']['monthlyServiceUsage'][CANARY] = {'quantity': 7, 'title': CANARY}
        source['data']['monthlyServiceUsage']['ACTOR_COMPUTE_UNITS']['priceTiers'] = [{'id': CANARY}]
        source['data']['monthlyServiceUsage']['ACTOR_COMPUTE_UNITS']['url'] = CANARY
        account = limits(); account['data']['limits']['creditCard'] = CANARY
        result = m.project(source, account)
        self.assertEqual(result['monthly']['unprojected_service_count'], 1)
        self.assertFalse(result['monthly']['all_service_names_projected'])
        self.assertNotIn(CANARY, json.dumps(result))
        self.assertNotIn('priceTiers', json.dumps(result))

    def test_cycle_validation_matches_instants_and_checks_selected_date(self):
        account = limits(); account['data']['monthlyUsageCycle']['startAt'] = '2026-10-02T00:00:00+00:00'
        result = m.project(monthly(), account)
        self.assertTrue(result['cycles_match'])
        self.assertTrue(result['schema_complete'])
        self.assertEqual(result['monthly']['cycle']['start_at'], '2026-10-02T00:00:00.000000Z')
        for start, end in ((END, START), ('2026-10-04T00:00:00Z', END),
                ('2026-10-02T00:00:00', END), ('2026-10-02T00:00:00+02:00', END), (CANARY, END)):
            source = monthly(); source['data']['usageCycle'] = {'startAt': start, 'endAt': end}
            result = m.project(source, limits())
            self.assertEqual(result['monthly']['cycle']['state'], 'invalid')
            self.assertIsNone(result['cycles_match'])
            self.assertIsNone(result['limits']['has_3_10_usd_headroom'])

    def test_mismatched_cycle_blocks_comparison_but_keeps_independent_totals(self):
        account = limits(); account['data']['monthlyUsageCycle']['endAt'] = '2026-11-02T23:59:59.999Z'
        result = m.project(monthly(), account)
        self.assertFalse(result['cycles_match'])
        self.assertFalse(result['schema_complete'])
        self.assertIsNone(result['limits']['has_3_10_usd_headroom'])
        self.assertEqual(result['monthly']['total_after_volume_discount_usd']['state'], 'number')

    def test_partial_failure_keeps_safe_monthly_evidence_without_default_limits(self):
        result = m.project(monthly(), None)
        self.assertTrue(result['monthly']['schema_complete'])
        self.assertFalse(result['limits']['schema_complete'])
        self.assertIsNone(result['cycles_match'])
        self.assertIsNone(result['limits']['has_3_10_usd_headroom'])
        self.assertEqual(result['limits']['current']['monthlyUsageUsd'], {'state': 'absent'})
        self.assertEqual(result['monthly']['total_after_volume_discount_usd']['value'], '0.5787419281736100123')

    def test_integer_fields_and_negative_derived_headroom_are_handled_honestly(self):
        account = limits(); account['data']['limits']['maxConcurrentActorJobs'] = D('32.000')
        self.assertEqual(m.project(monthly(), account)['limits']['maximum']['maxConcurrentActorJobs']['value'], '32')
        account['data']['limits']['maxMonthlyUsageUsd'] = 0
        result = m.project(monthly(), account)
        self.assertEqual(result['limits']['monthly_limit_headroom_usd']['value'], '-0.5787419281736100123')
        self.assertFalse(result['limits']['has_3_10_usd_headroom'])
        for value in (True, -1, D('1.5'), D('1e9')):
            account = limits(); account['data']['current']['activeActorJobCount'] = value
            result = m.project(monthly(), account)
            self.assertEqual(result['limits']['current']['activeActorJobCount']['state'], 'invalid')
            self.assertFalse(result['schema_complete'])

    def test_public_projection_contains_no_financial_values_even_from_hostile_input(self):
        private = m.project(monthly(), limits()); private['profile'] = CANARY; private['execution_ready'] = True
        public = m.public_projection(private)
        encoded = json.dumps(public)
        for bad in ('Usd', 'usd', '19', '64', '32', '0.578', CANARY, 'cycle', 'quantity', 'services'):
            self.assertNotIn(bad, encoded)
        self.assertFalse(public['execution_ready'])
        self.assertFalse(public['invoice_finality'])

    def test_no_mutation_and_invalid_parent_map_are_fail_closed(self):
        source, account = monthly(), limits(); before = copy.deepcopy((source, account))
        m.project(source, account); self.assertEqual((source, account), before)
        for field, value in (('monthlyServiceUsage', []), ('usageCycle', None)):
            source = monthly(); source['data'][field] = value
            self.assertFalse(m.project(source, limits())['schema_complete'])
        source = monthly(); source['data']['monthlyServiceUsage'] = {str(i): {} for i in range(m.MAX_SERVICE_FIELDS + 1)}
        result = m.project(source, limits())
        self.assertFalse(result['monthly']['schema_complete'])
        self.assertIsNone(result['monthly']['unprojected_service_count'])

    def test_requested_date_has_fixed_safe_invalid_input_diagnostic(self):
        for value in (CANARY, None, '2026-02-30', '2026-10-03?token=' + CANARY):
            with self.assertRaisesRegex(m.ProjectionError, '^monthly_usage_projection_invalid$'):
                m.project(monthly(), limits(), requested_date=value)

    def test_implausibly_long_cycle_cannot_claim_monthly_schema_completeness(self):
        source = monthly(); source['data']['usageCycle']['endAt'] = '2026-12-01T23:59:59.999Z'
        account = limits(); account['data']['monthlyUsageCycle']['endAt'] = '2026-12-01T23:59:59.999Z'
        result = m.project(source, account)
        self.assertFalse(result['schema_complete'])
        self.assertIsNone(result['limits']['has_3_10_usd_headroom'])


if __name__ == '__main__':
    unittest.main()
