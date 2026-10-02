"""Synthetic offline run-response projection; no account or provider access."""
from decimal import Decimal
import json
import unittest
import billing_projection as b


class BillingProjectionTests(unittest.TestCase):
    def test_missing_null_zero_and_invalid_are_distinct(self):
        for raw, expected in (({}, 'absent'), ({'usageTotalUsd':None}, 'null'),
                              ({'usageTotalUsd':0}, 'number'), ({'usageTotalUsd':True}, 'invalid')):
            result=b.project_run_billing(raw, [])['usage_total_usd']
            self.assertEqual(result['state'],expected)
            self.assertEqual(result.get('value'),0 if expected=='number' else None)

    def test_parent_states_and_precision_survive_without_inventing_zero(self):
        result=b.project_run_billing({'usage':None,'usageUsd':{'ACTOR_COMPUTE_UNITS':Decimal('0.00000000000000000123')}}, [])
        self.assertEqual(result['usage']['state'],'null')
        self.assertEqual(result['usage']['fields']['ACTOR_COMPUTE_UNITS'],{'state':'absent'})
        self.assertEqual(result['usage_usd']['fields']['ACTOR_COMPUTE_UNITS']['value'],'0.00000000000000000123')

    def test_documented_models_and_user_party_only(self):
        for model in b.PRICING_MODELS:
            result=b.project_run_billing({'pricingInfo':{'pricingModel':model},'platformUsageBillingModel':'USER'}, [])
            self.assertEqual(result['pricing_info']['pricing_model'],{'state':'recognized','value':model})
            self.assertEqual(result['platform_usage_billing_model'],{'state':'recognized','value':'USER'})

    def test_unknown_text_ids_titles_and_event_names_never_survive(self):
        raw={'pricingInfo':{'pricingModel':'PRIVATE-MODEL','reasonForChange':'PRIVATE-REASON',
                          'pricingPerEvent':{'actorChargeEvents':{'fetch':{'eventTitle':'PRIVATE-TITLE','eventDescription':'PRIVATE-DESC',
                           'eventPriceUsd':.01},'PRIVATE-KEY':{'eventPriceUsd':42}}}},
             'platformUsageBillingModel':'PRIVATE-OWNER','usage':{'PRIVATE-USAGE':99},'id':'PRIVATE-RUN'}
        result=b.project_run_billing(raw,['fetch'])
        self.assertNotIn('PRIVATE',json.dumps(result))
        self.assertEqual(result['platform_usage_billing_model']['state'],'unrecognized')
        self.assertEqual(result['pricing_info']['pricing_model']['state'],'unrecognized')
        self.assertEqual(set(result['pricing_info']['events']['fields']),{'fetch'})

    def test_flat_and_tiered_prices_are_preserved_without_selecting_account_tier(self):
        events={'fetch':{'eventTieredPricingUsd':{'FREE':{'tieredEventPriceUsd':.002},'BRONZE':{'tieredEventPriceUsd':.0019},
                        'PRIVATE-TIER':{'tieredEventPriceUsd':123}},'isPrimaryEvent':True},
                'apify-actor-start':{'eventPriceUsd':Decimal('.000225'),'isOneTimeEvent':False}}
        result=b.project_run_billing({'pricingInfo':{'pricingModel':'PAY_PER_EVENT','minimalMaxTotalChargeUsd':.01,
                    'pricingPerEvent':{'actorChargeEvents':events}},'chargedEventCounts':{'fetch':1,'apify-actor-start':8}},list(events))
        pricing=result['pricing_info']
        self.assertEqual(pricing['minimum_run_cap_usd'],{'state':'number','value':'0.01'})
        self.assertEqual(pricing['events']['fields']['apify-actor-start']['flat_price_usd']['value'],'0.000225')
        self.assertEqual(pricing['events']['fields']['fetch']['tier_prices_usd']['fields']['BRONZE']['value'],'0.0019')
        self.assertNotIn('PRIVATE',json.dumps(result))
        self.assertFalse(result['invoice_finality'])
        self.assertFalse(result['applied_account_tier_verified'])

    def test_conflicting_flat_and_tier_fields_are_explicit(self):
        row={'eventPriceUsd':1,'eventTieredPricingUsd':{'FREE':{'tieredEventPriceUsd':2}}}
        result=b.project_run_billing({'pricingInfo':{'pricingPerEvent':{'actorChargeEvents':{'fetch':row}}}},['fetch'])
        self.assertEqual(result['pricing_info']['events']['fields']['fetch']['price_shape'],'conflicting')

    def test_invalid_numeric_nonfinite_negative_string_and_boolean_are_omitted(self):
        for value in (Decimal('NaN'),float('inf'),-1,'0.01',True,Decimal('1e19'),Decimal('1e-10000')):
            result=b.project_run_billing({'usageTotalUsd':value},[])['usage_total_usd']
            self.assertEqual(result,{'state':'invalid'})

    def test_no_double_count_or_derived_bill(self):
        result=b.project_run_billing({'usageTotalUsd':.0037,'usageUsd':{'ACTOR_COMPUTE_UNITS':.001},
                  'chargedEventCounts':{'fetch':1,'apify-actor-start':8}},['fetch','apify-actor-start'])
        self.assertEqual(result['usage_total_usd']['value'],'0.0037')
        self.assertNotIn('calculated_total_usd',result)
        self.assertFalse(result['all_in_cost_reconciled'])

    def test_invalid_event_allowlist_is_rejected_before_projection(self):
        for fields in (['fetch','fetch'],['PRIVATE/ID'],['a']*17,'fetch'):
            with self.assertRaises(ValueError):b.project_run_billing({},fields)


if __name__=='__main__':unittest.main()
