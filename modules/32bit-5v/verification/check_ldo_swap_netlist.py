#!/usr/bin/env python3
"""Netlist acceptance proof for the 32bit-5v 1.1.1 regulator swap (AP7361C-33E -> AP2112K-3.3).

Schematic-only change: the board (*.kicad_pcb) is deliberately NOT updated, so this
proof is about the schematic netlist only.

Usage (from the module directory, KiCad 10 toolchain):

    kicad-cli sch export netlist --format kicadsexpr -o /tmp/pre.net \
        verification/netlist-32bit-5v-1.1.0.kicadsexpr   # (or the 1.1.0 artefact)
    kicad-cli sch export netlist --format kicadsexpr -o /tmp/post.net 32bit-5v.kicad_sch
    python3 verification/check_ldo_swap_netlist.py /tmp/pre.net /tmp/post.net

Writes verification/netlist-proof-ldo-swap.json and exits non-zero if any check fails.
"""

import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BASE_SCH = os.path.join(HERE, '..', '..', 'base', 'base.kicad_sch')

# What the +5V / +3V3 / GND nets must look like after the swap (netlist node notation).
EXPECT_PLUS5V = {('V_SUPPLY1', p) for p in '12345'} | {('U5', '1'), ('U5', '3'), ('C40', '1'), ('C42', '1')}
EXPECT_PLUS5V_GAINED = {('U5', '3'), ('C42', '1')}          # vs 1.1.0: EN pin + new input HF cap
EXPECT_3V3_PIN_SWAP = {('U5', '3'): ('U5', '5')}            # old VO pin 3 -> new VOUT pin 5
MUST_BE_UNCHANGED = ['+3V3_ESP32', '+3V3_8388']
BASE_U5_FIELDS = ['Value', 'Footprint', 'Datasheet', 'Description', 'LCSC', 'MPN', 'Manufacturer']


def tokenize(s):
    i, n = 0, len(s)
    while i < n:
        c = s[i]
        if c in '()':
            yield c
            i += 1
        elif c == '"':
            j, buf = i + 1, []
            while j < n:
                if s[j] == '\\':
                    buf.append(s[j + 1])
                    j += 2
                    continue
                if s[j] == '"':
                    break
                buf.append(s[j])
                j += 1
            yield ('str', ''.join(buf))
            i = j + 1
        elif c.isspace():
            i += 1
        else:
            j = i
            while j < n and not s[j].isspace() and s[j] not in '()"':
                j += 1
            yield ('atom', s[i:j])
            i = j


def parse(tokens):
    stack = [[]]
    for t in tokens:
        if t == '(':
            new = []
            stack[-1].append(new)
            stack.append(new)
        elif t == ')':
            stack.pop()
        else:
            stack[-1].append(t[1])
    return stack[0]


def child(node, key):
    for ch in node:
        if isinstance(ch, list) and ch and ch[0] == key:
            return ch
    return None


def children(node, key):
    return [ch for ch in node if isinstance(ch, list) and ch and ch[0] == key]


def read_netlist(path):
    root = parse(tokenize(open(path, encoding='utf-8').read()))[0]
    comps = {}
    for c in children(child(root, 'components'), 'comp'):
        ref = child(c, 'ref')[1]
        val = child(c, 'value')
        fp = child(c, 'footprint')
        fields = {}
        cf = child(c, 'fields')
        if cf:
            for f in children(cf, 'field'):
                nm = child(f, 'name')
                fields[nm[1]] = f[2] if len(f) > 2 else ''
        comps[ref] = {'value': val[1] if val else None,
                      'footprint': fp[1] if fp else None,
                      'fields': fields}
    nets = {}
    for n in children(child(root, 'nets'), 'net'):
        name = child(n, 'name')[1]
        nets[name] = {(child(nd, 'ref')[1], child(nd, 'pin')[1])
                      for nd in children(n, 'node')}
    return comps, nets


def base_u5_fields():
    """Read U5's properties straight out of the base schematic (the authority)."""
    txt = open(BASE_SCH, encoding='utf-8').read().split('\n')
    i = 0
    while i < len(txt):
        if txt[i].startswith('\t(symbol'):
            depth = txt[i].count('(') - txt[i].count(')')
            j, blk = i, [txt[i]]
            while depth > 0:
                j += 1
                blk.append(txt[j])
                depth += txt[j].count('(') - txt[j].count(')')
            body = '\n'.join(blk)
            if '(lib_id "Regulator_Linear:AP2112K-3.3")' in body:
                props = dict(re.findall(r'\(property "([^"]+)" "([^"]*)"', body))
                return props
            i = j + 1
            continue
        i += 1
    raise SystemExit('base U5 not found')


def main():
    pre_path, post_path = sys.argv[1], sys.argv[2]
    pre_comps, pre_nets = read_netlist(pre_path)
    post_comps, post_nets = read_netlist(post_path)
    results = []

    def check(name, ok, detail=''):
        results.append({'check': name, 'pass': bool(ok), 'detail': detail})

    plus5 = post_nets.get('+5V', set())
    check("net '+5V' exists", '+5V' in post_nets)
    check("net '+5V' == {V_SUPPLY1.1-5, U5.VIN(1), U5.EN(3), C40.1, C42.1}",
          plus5 == EXPECT_PLUS5V,
          'extra=%s missing=%s' % (sorted(plus5 - EXPECT_PLUS5V), sorted(EXPECT_PLUS5V - plus5)))
    check("net '+5V' gained only U5.EN(3) and C42.1 vs 1.1.0",
          plus5 - pre_nets.get('+5V', set()) == EXPECT_PLUS5V_GAINED,
          'gained=%s lost=%s' % (sorted(plus5 - pre_nets.get('+5V', set())),
                                 sorted(pre_nets.get('+5V', set()) - plus5)))
    v3 = post_nets.get('+3V3', set())
    pre_v3 = pre_nets.get('+3V3', set())
    lost = pre_v3 - v3
    check("net '+3V3' lost only the old regulator VO pin",
          lost == {('U5', '3')}, 'lost=%s' % sorted(lost))
    check("net '+3V3' gained only the new regulator VOUT pin",
          v3 - pre_v3 == {('U5', '5')}, 'gained=%s' % sorted(v3 - pre_v3))
    check("net '+3V3' still drives every 1.1.0 load",
          all(l in v3 for l in pre_v3 if l[0] != 'U5' and l != ('V_SUPPLY1', '1')),
          'nodes=%d' % len(v3))
    for net in MUST_BE_UNCHANGED:
        check("net '%s' unchanged" % net, pre_nets.get(net, set()) == post_nets.get(net, set()),
              'lost=%s gained=%s' % (sorted(pre_nets.get(net, set()) - post_nets.get(net, set())),
                                     sorted(post_nets.get(net, set()) - pre_nets.get(net, set()))))
    check("net 'GND' gained only C42.2 (no losses)",
          post_nets['GND'] - pre_nets['GND'] == {('C42', '2')} and not (pre_nets['GND'] - post_nets['GND']),
          'gained=%s lost=%s' % (sorted(post_nets['GND'] - pre_nets['GND']),
                                 sorted(pre_nets['GND'] - post_nets['GND'])))
    # every 1.1.0 3.3 V load that does not hang off the supply socket is still fed
    check("no 1.1.0 3.3 V consumer lost its rail",
          not any(l[0] not in ('V_SUPPLY1', 'U5') for l in lost),
          'lost consumers=%s' % sorted(l for l in lost if l[0] not in ('V_SUPPLY1', 'U5')))

    raw_post = open(post_path, encoding='utf-8').read()
    check("'AP7361C' appears nowhere in the netlist", 'AP7361C' not in raw_post)
    u5 = post_comps['U5']
    check("U5 value == AP2112K-3.3", u5['value'] == 'AP2112K-3.3', repr(u5['value']))
    b = base_u5_fields()
    for f in BASE_U5_FIELDS:
        got = {'Value': u5['value'], 'Footprint': u5['footprint']}.get(f, u5['fields'].get(f))
        check('base U5 %s matches (%s)' % (f, got), got == b.get(f),
              'base=%r module=%r' % (b.get(f), got))

    out = os.path.join(HERE, 'netlist-proof-ldo-swap.json')
    with open(out, 'w', encoding='utf-8') as fh:
        json.dump(results, fh, indent=1)
        fh.write('\n')
    fails = [r for r in results if not r['pass']]
    for r in results:
        print('%-4s %s%s' % ('PASS' if r['pass'] else 'FAIL', r['check'],
                             ('  [' + r['detail'] + ']') if r['detail'] and not r['pass'] else ''))
    print('%d/%d checks pass -> %s' % (len(results) - len(fails), len(results), out))
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
