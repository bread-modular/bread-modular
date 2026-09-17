#!/usr/bin/python3
"""Build production/cost-estimate.json: a sourced per-board component estimate.

The estimate is deliberately narrow. It prices the parts from the JLCPCB BOM and
the two builder-supplied hand-solder parts from live LCSC tier prices; it does
NOT invent a PCB-fabrication or SMT-assembly charge, which only the JLCPCB quote
for a concrete board count can give.

Usage::

    tools/estimate_cost.py --batch 50            # recompute from the cached prices
    tools/estimate_cost.py --batch 50 --refresh  # re-fetch LCSC prices first

The output file doubles as the price cache, so the documented release path stays
offline: without --refresh nothing is fetched.
"""
from __future__ import annotations

import argparse
import csv
import datetime
import json
import math
import re
import subprocess
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
PROD = BASE / 'production'
OUT = PROD / 'cost-estimate.json'
SPEC = json.loads((PROD / 'hand-solder.json').read_text())
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--batch', type=int, default=50, help='board count used for the tier choice')
parser.add_argument('--attrition', type=float, default=0.05, help='spare fraction on top of the placement count')
parser.add_argument('--refresh', action='store_true', help='re-fetch LCSC prices (network)')
args = parser.parse_args()

LADDER = re.compile(r'role="button">([\d,]+)<!-- -->\+</td><td[^>]*><span class="[^"]*">\$<!-- --> <!-- -->([\d.]+)</span>')
STOCK = re.compile(r'In-Stock : ([\d,]+)')
URL = 'https://www.lcsc.com/product-detail/{}.html'


def fetch(code: str) -> dict:
    html = subprocess.run(['curl', '-s', '-m', '30', '-A', 'Mozilla/5.0', URL.format(code)],
                          capture_output=True, text=True, check=True).stdout
    ladder = sorted((int(q.replace(',', '')), float(p)) for q, p in LADDER.findall(html))
    stock = STOCK.search(html)
    if not ladder:
        raise LookupError(f'{code}: no price ladder found at {URL.format(code)}')
    return {'unit_price_usd': ladder[0][1], 'ladder': ladder,
            'stock': int(stock.group(1).replace(',', '')) if stock else None,
            'source': URL.format(code), 'checked': datetime.date.today().isoformat()}


def tier(ladder: list, need: int) -> tuple[int, float]:
    """Largest published tier whose quantity we can reach, cheapest price we qualify for."""
    ordered = sorted(ladder)
    best = ordered[0]
    for qty, price in ordered:
        if need >= qty:
            best = (qty, price)
        else:
            break
    return best


HAND_SOLDER_PARTS = (('slot_socket', 25), ('shunt', 12), ('rail_select_header', 12))
parts = {}
unpriced_codes = {}
rows = list(csv.DictReader((BASE / 'jlcpcb/base/bom.csv').open(encoding='utf-8-sig')))
if args.refresh or not OUT.is_file():
    for row in rows:
        code = row['LCSC Part #'].strip()
        if code in parts or code in unpriced_codes:
            continue
        try:
            parts[code] = fetch(code)
        except LookupError as error:
            unpriced_codes[code] = str(error)
    for key in ('slot_socket', 'shunt', 'rail_select_header'):
        code = SPEC['recommended_parts'][key]['lcsc']
        try:
            parts[code] = fetch(code)
        except LookupError as error:
            unpriced_codes[code] = str(error)
    fetched_at = datetime.datetime.now().isoformat(timespec='seconds')
else:
    cached = json.loads(OUT.read_text())
    parts = cached['prices']
    unpriced_codes = cached.get('unpriced_codes', {})
    fetched_at = cached['fetched_at']

items, assembled_total, unmatched = [], 0.0, []
for row in rows:
    code = row['LCSC Part #'].strip()
    qty = int(row['Quantity'])
    if code not in parts:
        unmatched.append({'designator': row['Designator'], 'lcsc': code, 'comment': row['Comment']})
        continue
    need = math.ceil(qty * args.batch * (1 + args.attrition))
    qty_tier, price = tier(parts[code]['ladder'], need)
    buy = max(need, qty_tier)
    cost = buy * price
    assembled_total += cost
    items.append({'designator': row['Designator'], 'comment': row['Comment'], 'lcsc': code, 'mpn': row['MPN'],
                  'qty_per_board': qty, 'need_for_batch': buy, 'tier_qty': qty_tier, 'unit_price_usd': price,
                  'extended_usd': round(cost, 4), 'per_board_usd': round(cost / args.batch, 5)})

hand = []
hand_total = 0.0
for key, per_board in HAND_SOLDER_PARTS:
    code = SPEC['recommended_parts'][key]['lcsc']
    if code not in parts:
        unmatched.append({'designator': key, 'lcsc': code, 'comment': 'hand-solder part'})
        continue
    need = math.ceil(per_board * args.batch * (1 + args.attrition))
    qty_tier, price = tier(parts[code]['ladder'], need)
    buy = max(need, qty_tier)
    cost = buy * price
    hand_total += cost
    hand.append({'used_for': key, 'lcsc': code, 'mpn': SPEC['recommended_parts'][key]['mpn'],
                 'qty_per_board': per_board, 'need_for_batch': buy, 'tier_qty': qty_tier,
                 'unit_price_usd': price, 'extended_usd': round(cost, 4), 'per_board_usd': round(cost / args.batch, 5)})

# Hand-solder references that cannot be priced here, listed explicitly so the
# subtotal is never mistaken for the whole board.
hand_unpriced = [
    {'refs': SPEC['groups'][3]['refs'], 'qty_per_board': 1, 'group': SPEC['groups'][3]['id'],
     'reason': 'straight 2x05 2.54 mm female socket - part number not selected in this pass (C2897425 is the right-angle variant and was rejected)'},
    {'refs': SPEC['groups'][5]['refs'], 'qty_per_board': 4, 'group': SPEC['groups'][5]['id'],
     'reason': 'WQP-PJ366ST 3.5 mm jack has no LCSC number (schematic LCSC field is NOT-JLC); buy from the jack supplier'},
    {'refs': SPEC['groups'][6]['refs'], 'qty_per_board': 2, 'group': SPEC['groups'][6]['id'],
     'reason': 'RV09-50K has no LCSC number (schematic LCSC field is NOT-JLC); every RV09 variant was out of JLCPCB stock'},
]
unpriced_refs = [r for row in hand_unpriced for r in row['refs']] + [r.strip() for row in unmatched for r in row['designator'].split(',')]
total_refs = len({ref.strip() for row in rows for ref in row['Designator'].split(',')}) + sum(len(g['refs']) for g in SPEC['groups'])
priced_refs = total_refs - len(unpriced_refs)
assert total_refs == 163, total_refs

doc = {
    'schema': 'bread-modular/base/cost-estimate/1',
    'hand_maintained': False,
    'generated_by': 'tools/estimate_cost.py',
    'fetched_at': fetched_at,
    'method': {
        'batch_boards': args.batch,
        'attrition_fraction': args.attrition,
        'tier_policy': 'buy max(needed, MOQ) at the unit price of the largest published tier whose quantity is reached',
        'scope': 'components only (JLCPCB-assembled parts + the two builder-supplied hand-solder parts)',
        'excluded': ['bare PCB fabrication', 'JLCPCB SMT assembly and setup charge', 'stencil', 'shipping, duty and VAT',
                     'yield loss beyond the stated attrition', 'wastage rules that JLCPCB applies at order time'],
        'caveat': 'DISPOSABLE ESTIMATE. LCSC/JLCPCB prices and stock change daily; request a real quote before ordering.',
    },
    'prices': parts,
    'unpriced_codes': unpriced_codes,
    'jlcpcb_assembled_parts': items,
    'hand_solder_parts': hand,
    'totals': {
        'partial': True,
        'partial_note': 'Components only, and not every component: the parts in hand_solder_not_priced are missing from this subtotal, so it is a floor, not the board cost.',
        'jlcpcb_assembled_per_board_usd': round(assembled_total / args.batch, 2),
        'hand_solder_per_board_usd': round(hand_total / args.batch, 2),
        'components_per_board_usd': round((assembled_total + hand_total) / args.batch, 2),
        'components_for_batch_usd': round(assembled_total + hand_total, 2),
        'quote_required': ['bare 2-layer PCB 223.52 x 160.02 mm (357.6 cm2)',
                           'JLCPCB SMT assembly charge for 119 placements / 32 BOM rows + setup/stencil',
                           'shipping and taxes'],
    },
    'parts_not_priced': unmatched,
    'hand_solder_not_priced': hand_unpriced,
    'counts': {'designators_total': 163, 'designators_priced_roughly': 163 - len(unpriced_refs),
               'designators_not_priced': len(unpriced_refs),
               'not_priced_designators': unpriced_refs},
}
OUT.write_text(json.dumps(doc, indent=2) + '\n')
print(f'batch {args.batch}: {doc["totals"]["components_per_board_usd"]} $/board components '
      f'({doc["totals"]["jlcpcb_assembled_per_board_usd"]} assembled + {doc["totals"]["hand_solder_per_board_usd"]} hand-solder); '
      f'{len(items)}/{len(rows)} BOM rows priced' + (f'; NOT PRICED: {unmatched}' if unmatched else ''))
