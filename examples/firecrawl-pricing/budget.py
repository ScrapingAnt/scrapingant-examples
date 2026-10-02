"""Illustrative monthly USD model, not an observed invoice or cash measurement."""
import argparse
import json
from math import ceil

PLANS={'Free':(0,1000,0),'Hobby':(19,5000,1000),'Standard':(99,100000,2000),'Growth':(399,500000,2500),'Scale':(749,1000000,5000)}

def model(plan, credits, accepted):
    if credits<0 or accepted<0: raise ValueError('Counts must be nonnegative')
    base,allowance,increment=PLANS[plan]
    excess=max(0,credits-allowance)
    if excess and not increment: raise ValueError('Free allowance exceeded')
    increments=ceil(excess/increment) if excess else 0
    bill=base+5*increments
    return {'plan':plan,'mode':'modeled_monthly_USD','credits_needed':credits,'accepted_outputs':accepted,'base_bill_usd':base,'top_up_increments':increments,'bill_usd':bill,'unused_plan_credits':max(0,allowance-credits),'unused_purchased_credits':increments*increment-excess,'usd_per_accepted':bill/accepted if accepted else None}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--plan',choices=PLANS,default='Standard')
    p.add_argument('--urls',type=int,default=1000)
    p.add_argument('--runs',type=int,default=30)
    p.add_argument('--retry-attempts',type=int,default=0)
    p.add_argument('--credits-per-attempt',type=int,default=1)
    p.add_argument('--accepted',type=int,default=27000,help='Hypothetical accepted scheduled outputs; retries are not extra unique outputs')
    a=p.parse_args()
    if min(a.urls,a.runs,a.retry_attempts,a.accepted)<0 or a.credits_per_attempt<1 or a.accepted>a.urls*a.runs:
        p.error('Invalid workload or accepted count')
    credits=(a.urls*a.runs+a.retry_attempts)*a.credits_per_attempt
    print(json.dumps(model(a.plan,credits,a.accepted),indent=2))

if __name__=='__main__': main()
