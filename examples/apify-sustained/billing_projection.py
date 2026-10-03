"""Bounded PRIVATE projection of documented Get-run billing fields.

Official schema: https://docs.apify.com/api/v2/actor-run-get (2026-10-02).
Keep presence and numeric values; never infer an invoice, account tier, migration,
or inclusion from a Store label. Unknown provider strings are deliberately omitted.
Public callers must not print this projection. No network or credential handling.
"""
from decimal import Decimal, InvalidOperation
import re

PRICING_MODELS=('PAY_PER_EVENT','PRICE_PER_DATASET_ITEM','FLAT_PRICE_PER_MONTH','FREE')
# Documented examples, not a claim that these exhaust future platform tiers.
TIER_NAMES=('FREE','BRONZE','SILVER','GOLD','PLATINUM','DIAMOND')
USAGE_FIELDS=('ACTOR_COMPUTE_UNITS','DATASET_READS','DATASET_WRITES','KEY_VALUE_STORE_READS',
             'KEY_VALUE_STORE_WRITES','KEY_VALUE_STORE_LISTS','REQUEST_QUEUE_READS','REQUEST_QUEUE_WRITES',
             'DATA_TRANSFER_INTERNAL_GBYTES','DATA_TRANSFER_EXTERNAL_GBYTES',
             'PROXY_RESIDENTIAL_TRANSFER_GBYTES','PROXY_SERPS')


def presence(parent,key):
    if not isinstance(parent,dict) or key not in parent:return {'state':'absent'}
    return {'state':'null' if parent[key] is None else 'present'}


def numeric(parent,key):
    result=presence(parent,key)
    if result['state']!='present':return result
    value=parent[key]
    if type(value) not in (int,float,Decimal):return {'state':'invalid'}
    try:
        number=Decimal(str(value))
        if (not number.is_finite() or not 0<=number<=Decimal('1e18') or len(str(value))>96
                or number.as_tuple().exponent < -64):
            return {'state':'invalid'}
        return {'state':'number','value':int(number) if number==number.to_integral_value() else format(number,'f')}
    except (InvalidOperation,ValueError):return {'state':'invalid'}


def enumeration(parent,key,allowed):
    result=presence(parent,key)
    if result['state']!='present':return result
    value=parent[key]
    if not isinstance(value,str):return {'state':'invalid'}
    return {'state':'recognized','value':value} if value in allowed else {'state':'unrecognized'}


def object_field(parent,key):
    result=presence(parent,key)
    if result['state']=='present':result={'state':'object' if isinstance(parent[key],dict) else 'invalid'}
    return result, parent[key] if result['state']=='object' else {}


def numbers(parent,key,fields):
    result,value=object_field(parent,key)
    result['fields']={name:numeric(value,name) for name in fields}
    return result


def boolean(parent,key):
    result=presence(parent,key)
    if result['state']!='present':return result
    return {'state':'boolean','value':parent[key]} if type(parent[key]) is bool else {'state':'invalid'}


def event_projection(parent,key):
    result,value=object_field(parent,key)
    tiers,tier_values=object_field(value,'eventTieredPricingUsd')
    tiers['fields']={name:numeric(tier_values.get(name),'tieredEventPriceUsd') for name in TIER_NAMES}
    flat=numeric(value,'eventPriceUsd')
    has_flat=flat['state'] not in ('absent','null')
    has_tier=tiers['state'] not in ('absent','null')
    result.update(flat_price_usd=flat,tier_prices_usd=tiers,
        price_shape='conflicting' if has_flat and has_tier else 'flat' if has_flat else 'tiered' if has_tier else 'unknown',
        primary_event=boolean(value,'isPrimaryEvent'),one_time_event=boolean(value,'isOneTimeEvent'))
    return result


def project_run_billing(data,event_fields):
    if (not isinstance(data,dict) or not isinstance(event_fields,list) or len(event_fields)>16
            or any(not isinstance(name,str) or re.fullmatch(r'[a-zA-Z0-9_-]{1,64}',name) is None for name in event_fields)
            or len(set(event_fields))!=len(event_fields)):
        raise ValueError('invalid fixed billing projection input')
    pricing,values=object_field(data,'pricingInfo')
    per_event,per_values=object_field(values,'pricingPerEvent')
    events,event_values=object_field(per_values,'actorChargeEvents')
    events['fields']={name:event_projection(event_values,name) for name in event_fields}
    pricing.update(pricing_model=enumeration(values,'pricingModel',PRICING_MODELS),
                   minimum_run_cap_usd=numeric(values,'minimalMaxTotalChargeUsd'),
                   per_event_state=per_event['state'],events=events)
    return {'schema_version':1,'source_verified_at':'2026-10-02',
            'usage_total_usd':numeric(data,'usageTotalUsd'),
            'usage':numbers(data,'usage',USAGE_FIELDS),'usage_usd':numbers(data,'usageUsd',USAGE_FIELDS),
            'charged_event_counts':numbers(data,'chargedEventCounts',event_fields),'pricing_info':pricing,
            # USER is the official example. Other parties remain unrecognized
            # until independently sourced; do not save unknown free text.
            'platform_usage_billing_model':enumeration(data,'platformUsageBillingModel',('USER',)),
            'meters_state':'preliminary','invoice_finality':False,'all_in_cost_reconciled':False,
            'applied_account_tier_verified':False}
