#!/usr/bin/python3
"""Build production/cost-estimate.json: a sourced PARTIAL component subtotal.

The estimate is deliberately narrow and deliberately partial. It prices the
surface-mount parts in the JLCPCB BOM plus the builder-supplied sockets, shunts
and jumper headers from live LCSC tier prices. It does NOT invent a
PCB-fabrication or SMT-assembly charge, and every designator it cannot price is
listed by its real references so the subtotal can never be mistaken for the
board cost.

Usage::

    tools/estimate_cost.py --batch 50            # recompute from the cached prices
    tools/estimate_cost.py --batch 50 --refresh  # re-fetch LCSC prices first
    tools/estimate_cost.py --selftest            # check the unpriced accounting

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
GROUPS = {group['id']: group for group in SPEC['groups']}

# recommended-part key -> the hand-solder groups that buy it
PRICED_HAND = (('slot_socket', ('slot-rail-socket', 'slot-ground-socket', 'aux-input-socket')),
               ('rail_select_header', ('rail-select-header',)))
# accessories are not board designators, so they are counted separately
ACCESSORIES = (('shunt', 12),)
# hand-solder groups with no LCSC part number at all
UNPRICED_HAND = ('power-expansion-socket', 'audio-jack', 'panel-pot')

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--batch', type=int, default=50, help='board count used for the tier choice')
parser.add_argument('--attrition', type=float, default=0.05, help='spare fraction on top of the placement count')
parser.add_argument('--refresh', action='store_true', help='re-fetch LCSC prices (network)')
parser.add_argument('--selftest', action='store_true', help='check the unpriced accounting and exit')
args = parser.parse_args()

LADDER = re.compile(r'role="button">([\d,]+)<!-- -->\+</td><td[^>]*><span class="[^"]*">\$<!-- --> <!-- -->([\d.]+)</span>')
STOCK = re.compile(r'In-Stock : ([\d,]+)')
URL = 'https://www.lcsc.com/product-detail/{}.html'
ROWS = list(csv.DictReader((BASE / 'jlcpcb/base/bom.csv').open(encoding='utf-8-sig')))
ALL_REFS = {ref.strip() for row in ROWS for ref in row['Designator'].split(',')}
ALL_REFS |= {ref for group in SPEC['groups'] for ref in group['refs']}


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
    best = sorted(ladder)[0]
    for qty, price in sorted(ladder):
        if need >= qty:
            best = (qty, price)
        else:
            break
    return best


def price(code: str, per_board: int, parts: dict, batch: int, attrition: float):
    """Return (row, extended_cost) or (None, 0.0) when the part could not be priced."""
    if code not in parts:
        return None, 0.0
    need = math.ceil(per_board * batch * (1 + attrition))
    qty_tier, unit = tier(parts[code]['ladder'], need)
    buy = max(need, qty_tier)
    cost = buy * unit
    return {'lcsc': code, 'qty_per_board': per_board, 'need_for_batch': buy, 'tier_qty': qty_tier,
            'unit_price_usd': unit, 'extended_usd': round(cost, 4), 'per_board_usd': round(cost / batch, 5)}, cost


def build(parts: dict, batch: int, attrition: float) -> dict:
    items, assembled, unpriced_rows = [], 0.0, []
    for row in ROWS:
        code = row['LCSC Part #'].strip()
        priced, cost = price(code, int(row['Quantity']), parts, batch, attrition)
        if priced is None:
            unpriced_rows.append({'refs': [r.strip() for r in row['Designator'].split(',')],
                                  'lcsc': code, 'comment': row['Comment'], 'mpn': row['MPN'],
                                  'reason': 'no price ladder on the LCSC product page'})
            continue
        assembled += cost
        items.append({**priced, 'designator': row['Designator'], 'comment': row['Comment'], 'mpn': row['MPN']})

    hand, hand_total, hand_unpriced = [], 0.0, []
    for key, group_ids in PRICED_HAND:
        refs = [ref for gid in group_ids for ref in GROUPS[gid]['refs']]
        part = SPEC['recommended_parts'][key]
        priced, cost = price(part['lcsc'], len(refs), parts, batch, attrition)
        if priced is None:
            hand_unpriced.append({'refs': refs, 'group': list(group_ids), 'lcsc': part['lcsc'],
                                  'reason': 'no price ladder on the LCSC product page'})
            continue
        hand_total += cost
        hand.append({**priced, 'used_for': key, 'groups': list(group_ids), 'mpn': part['mpn'], 'refs': refs})
    for gid in UNPRICED_HAND:
        group = GROUPS[gid]
        hand_unpriced.append({'refs': group['refs'], 'group': [gid],
                              'reason': group.get('recommended', group.get('part', 'no LCSC number'))})

    accessories, accessory_total, accessories_unpriced = [], 0.0, []
    for key, per_board in ACCESSORIES:
        part = SPEC['recommended_parts'][key]
        priced, cost = price(part['lcsc'], per_board, parts, batch, attrition)
        if priced is None:
            accessories_unpriced.append({'used_for': key, 'lcsc': part['lcsc'], 'qty_per_board': per_board,
                                         'reason': 'no price ladder on the LCSC product page'})
            continue
        accessory_total += cost
        accessories.append({**priced, 'used_for': key, 'mpn': part['mpn'],
                            'note': 'accessory, user-fit, not a board designator'})

    not_priced_refs = sorted({ref for row in unpriced_rows for ref in row['refs']} |
                             {ref for row in hand_unpriced for ref in row['refs']})
    priced_refs = sorted(ALL_REFS - set(not_priced_refs))
    return {
        'jlcpcb_assembled_parts': items,
        'hand_solder_parts': hand,
        'accessories': accessories,
        'parts_not_priced': unpriced_rows,
        'hand_solder_not_priced': hand_unpriced,
        'accessories_not_priced': accessories_unpriced,
        'counts': {'designators_total': len(ALL_REFS),
                   'designators_priced': len(priced_refs),
                   'designators_not_priced': len(not_priced_refs),
                   'not_priced_designators': not_priced_refs,
                   'priced_designators': priced_refs,
                   'accessories_total': sum(qty for _, qty in ACCESSORIES)},
        'totals': {
            'partial': True,
            'partial_note': 'Components only, and not every component: hand_solder_not_priced, '
                            'parts_not_priced and accessories_not_priced are missing from this subtotal, '
                            'so it is a floor, not the board cost.',
            'jlcpcb_assembled_per_board_usd': round(assembled / batch, 2),
            'hand_solder_per_board_usd': round(hand_total / batch, 2),
            'components_per_board_usd': round((assembled + hand_total) / batch, 2),
            'components_for_batch_usd': round(assembled + hand_total, 2),
            'accessories_per_board_usd': round(accessory_total / batch, 2),
            'quote_required': ['bare 2-layer PCB 223.52 x 160.02 mm (357.6 cm2)',
                               'JLCPCB SMT assembly charge for 119 placements / 32 BOM rows + setup/stencil',
                               'shipping and taxes'],
        },
    }


if args.selftest:
    # Accounting must stay correct when a price disappears: the references have to
    # move from "priced" to "explicitly not priced", never silently vanish.
    full = build({code: {'ladder': [(1, 1.0)], 'stock': 1, 'unit_price_usd': 1.0, 'source': 'synthetic', 'checked': 'selftest'}
                  for code in ['C2897368', 'C2905948', 'C5664'] + [r['LCSC Part #'].strip() for r in ROWS]},
                 10, 0.05)
    reduced = {code: table for code, table in
               {'C2897368': None, 'C2905948': None, 'C5664': None,
                **{r['LCSC Part #'].strip(): {'ladder': [(1, 1.0)]} for r in ROWS}}.items() if table}
    broken = build(reduced, 10, 0.05)
    socket_refs = {ref for gid in ('slot-rail-socket', 'slot-ground-socket', 'aux-input-socket')
                   for ref in GROUPS[gid]['refs']}
    header_refs = set(GROUPS['rail-select-header']['refs'])
    checks = [
        (full['counts']['designators_total'] == 163, 'designator total is not 163'),
        (full['counts']['designators_priced'] + full['counts']['designators_not_priced'] == 163,
         'priced + not priced does not add up to the total'),
        (broken['accessories_not_priced'] and not broken['accessories'],
         'an unpriced shunt accessory is not reported as an accessory'),
        (socket_refs <= set(broken['counts']['not_priced_designators']),
         'unpriced sockets are not reported by their real references'),
        (header_refs <= set(broken['counts']['not_priced_designators']),
         'unpriced jumper headers are not reported by their real references'),
        (set(broken['counts']['priced_designators']) | set(broken['counts']['not_priced_designators']) == ALL_REFS,
         'the priced/not-priced partition does not cover every reference'),
        (not (socket_refs & set(broken['counts']['priced_designators'])),
         'a reference is both priced and not priced'),
    ]
    for ok, message in checks:
        if not ok:
            raise SystemExit(f'SELFTEST FAILED: {message}')
    print(f'SELFTEST PASS: {len(checks)} accounting checks; unpriced parts move to the explicit '
          f'not-priced lists by reference and accessories stay separate.')
    raise SystemExit(0)

parts, unpriced_codes = {}, {}
if args.refresh or not OUT.is_file():
    for code in sorted({r['LCSC Part #'].strip() for r in ROWS} |
                       {SPEC['recommended_parts'][key]['lcsc'] for key, _ in PRICED_HAND + ACCESSORIES}):
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

doc = {'schema': 'bread-modular/base/cost-estimate/1',
       'hand_maintained': False,
       'generated_by': 'tools/estimate_cost.py',
       'fetched_at': fetched_at,
       'method': {
           'batch_boards': args.batch,
           'attrition_fraction': args.attrition,
           'tier_policy': 'buy max(needed, MOQ) at the unit price of the largest published tier whose quantity is reached',
           'scope': 'component subtotal only, and partial: the parts listed as not priced are excluded',
           'excluded': ['bare PCB fabrication', 'JLCPCB SMT assembly and setup charge', 'stencil',
                        'shipping, duty and VAT', 'yield loss beyond the stated attrition',
                        'wastage rules that JLCPCB applies at order time'],
           'caveat': 'DISPOSABLE ESTIMATE. LCSC/JLCPCB prices and stock change daily; request a real quote before ordering.',
       },
       'prices': parts, 'unpriced_codes': unpriced_codes, **build(parts, args.batch, args.attrition)}
OUT.write_text(json.dumps(doc, indent=2) + '\n')
counts, totals = doc['counts'], doc['totals']
print(f'batch {args.batch}: {totals["components_per_board_usd"]} $/board components '
      f'({totals["jlcpcb_assembled_per_board_usd"]} assembled + {totals["hand_solder_per_board_usd"]} hand-solder); '
      f'{counts["designators_priced"]}/{counts["designators_total"]} designators priced; '
      f'not priced: {counts["not_priced_designators"]}')
