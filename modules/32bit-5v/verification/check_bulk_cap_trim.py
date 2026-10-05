#!/usr/bin/env python3
"""Acceptance proof for the 32bit-5v 1.1.2 bulk-cap trim (C9..C13 removed from +3V3_ESP32).

Schematic-only change: the board (*.kicad_pcb) is deliberately NOT updated, so this
proof is about the schematic netlist only.

What it proves
--------------
1. component delta: exactly {C9, C10, C11, C12, C13} left the BOM, nothing was added,
   and **every surviving component's value / footprint / fields are unchanged**
   (so no accidental re-value or re-footprint rode along with the trim);
2. net delta: for **every** net in the design, `post == pre` after subtracting only the
   pins of the removed capacitors — i.e. no net was re-wired, merged, split or renamed;
   `+3V3_ESP32` keeps `FB1.1`, `U1.2` (module 3V3), `C1.1` (0.1uF) and `C2.1` (10uF);
3. ERC delta: the ERC findings are compared *normalised* (severity + type + affected
   item descriptions + positions), not just by totals — so "56 -> 56" cannot hide a
   swapped finding;
4. chaining: the revision history is replayed link by link from the frozen 1.1.0
   artefact - 1.1.0 -> 1.1.1-as-released (the regulator swap) -> 1.1.1@1244ad0
   (where C41 was re-placed and accidentally left floating: a **pre-existing
   defect** that this revision neither causes nor fixes) -> 1.1.2 (this trim).
   Each link's model is compared against that revision's frozen netlist, so the
   chain is exact at every hop, not just at the ends.

Usage (from the module directory, KiCad 10 toolchain):

    python3 verification/check_bulk_cap_trim.py \
        verification/netlist-32bit-5v-1.1.1.kicadsexpr \
        verification/netlist-32bit-5v.kicadsexpr \
        verification/erc-32bit-5v-1.1.1.json \
        verification/erc-32bit-5v.json \
        --v110 verification/netlist-32bit-5v-1.1.0.kicadsexpr \
        --v111rel verification/netlist-32bit-5v-1.1.1-as-released.kicadsexpr

The four positional arguments are pre-netlist, post-netlist, pre-ERC, post-ERC.
--v110 (chain start, 1.1.0) and --v111rel (the 1.1.1-as-released hop) are
all-or-nothing: supplying one without the other fails the run, so a chain link can
never report PASS without having checked its fixture.

Writes verification/proof-bulk-cap-trim.json and exits non-zero if any check fails.
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

REMOVED = {'C9', 'C10', 'C11', 'C12', 'C13'}

# the 1.1.2 +3V3_ESP32 rail, node for node
EXPECT_ESP32_RAIL = {('C1', '1'), ('C2', '1'), ('FB1', '1'), ('U1', '2')}
ESP32_LOST = {(c, '1') for c in REMOVED}
GND_LOST = {(c, '2') for c in REMOVED}

# ---- the chain: 1.1.0 -> 1.1.1 (regulator swap) -> 1.1.2 (trim) -------------
# the regulator swap, exactly as proved by check_ldo_swap_netlist.py
LDO_GAINED_PLUS5V = {('U5', '3'), ('C42', '1')}     # EN pin wired to VIN + new input HF cap
LDO_3V3_PIN_SWAP = {('U5', '3'): ('U5', '5')}       # old VO pin 3 -> new VOUT pin 5
LDO_GAINED_GND = {('C42', '2')}
LDO_ADDED_REFS = {'C42'}                            # the only component 1.1.1 added
LDO_NEW_NET = ('unconnected-(U5-NC-Pad4)', {('U5', '4')})   # SOT-23-5 NC pin

# link 2 of the chain: rev 1244ad0 moved C41 and left its +3V3 stub floating.
# This is a PRE-EXISTING DEFECT that this revision neither introduces nor fixes
# (see POWER.md section 5 / verification/README.md); it is modelled here so the
# chain from 1.1.0 stays exact.
C41_DEFECT_LOST = {('C41', '1')}
C41_DEFECT_NEW_NET = ('unconnected-(C41-Pad1)', {('C41', '1')})


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


def read_erc(path):
    """Normalised ERC findings: (severity, type, tuple(item descriptions), tuple(item positions))."""
    if not path or not os.path.exists(path):
        return None
    d = json.load(open(path, encoding='utf-8'))
    out = []
    for sh in d.get('sheets', []):
        for v in sh.get('violations', []):
            items = tuple(sorted(
                '%s@%s' % (i.get('description', ''),
                           ','.join(str(i.get('pos', {}).get(k, ''))
                                    for k in ('x', 'y') if k in i.get('pos', {})))
                for i in v.get('items', [])))
            out.append((v.get('severity'), v.get('type'), items))
    return out


def main():
    argv = sys.argv[1:]
    pos = [a for a in argv if not a.startswith('--')]
    pre_net, post_net = pos[0], pos[1]
    pre_erc = pos[2] if len(pos) > 2 else None
    post_erc = pos[3] if len(pos) > 3 else None
    v110 = None
    v111rel = None
    if '--v110' in argv:
        v110 = argv[argv.index('--v110') + 1]
    if '--v111rel' in argv:
        v111rel = argv[argv.index('--v111rel') + 1]
    if bool(v110) != bool(v111rel):
        print('FAIL --v110 and --v111rel must be supplied together: the chain cannot be '
              'checked without every one of its fixtures')
        return 1

    pre_comps, pre_nets = read_netlist(pre_net)
    post_comps, post_nets = read_netlist(post_net)

    results = []

    def check(name, ok, detail=''):
        results.append({'check': name, 'pass': bool(ok), 'detail': detail})

    # ---- 1. component delta -------------------------------------------------
    gone = set(pre_comps) - set(post_comps)
    added = set(post_comps) - set(pre_comps)
    check('exactly 5 components removed', len(gone) == 5, 'removed=%s' % sorted(gone))
    check('removed set == {C9,C10,C11,C12,C13}', gone == REMOVED,
          'removed=%s' % sorted(gone))
    check('no component added', not added, 'added=%s' % sorted(added))
    check('every removed part was a 100uf C_1206 (the legacy bulk)',
          all(pre_comps[c]['value'] == '100uf' and
              (pre_comps[c]['footprint'] or '').endswith('C_1206_3216Metric') for c in gone),
          ' %s' % {c: (pre_comps[c]['value'], pre_comps[c]['footprint']) for c in sorted(gone)})
    drift = sorted(r for r in pre_comps if r in post_comps and pre_comps[r] != post_comps[r])
    check('every surviving component value/footprint/fields unchanged', not drift,
          'drifted=%s' % drift)

    # ---- 2. net delta -------------------------------------------------------
    check('net count unchanged (%d)' % len(pre_nets), len(pre_nets) == len(post_nets),
          'pre=%d post=%d' % (len(pre_nets), len(post_nets)))

    trimmed_all = {c for c in REMOVED}
    expect_nets = {n: {nd for nd in nodes if nd[0] not in trimmed_all}
                   for n, nodes in pre_nets.items()}
    expect_nets = {n: nodes for n, nodes in expect_nets.items() if nodes}
    check('every net == pre-nets minus only the C9..C13 pins', expect_nets == post_nets,
          'diff nets=%s' % sorted(n for n in set(expect_nets) | set(post_nets)
                                  if expect_nets.get(n) != post_nets.get(n)))

    changed = sorted(n for n in pre_nets if pre_nets[n] != post_nets.get(n))
    check('only +3V3_ESP32 and GND changed', changed == ['+3V3_ESP32', 'GND'],
          'changed=%s' % changed)
    check("'+3V3_ESP32' lost exactly C9..C13 pin 1",
          pre_nets['+3V3_ESP32'] - post_nets['+3V3_ESP32'] == ESP32_LOST,
          'lost=%s' % sorted(pre_nets['+3V3_ESP32'] - post_nets['+3V3_ESP32']))
    check("'+3V3_ESP32' gained nothing", not (post_nets['+3V3_ESP32'] - pre_nets['+3V3_ESP32']))
    check("'+3V3_ESP32' == {C1.1 0.1uF, C2.1 10uF, FB1.1, U1.2}",
          post_nets['+3V3_ESP32'] == EXPECT_ESP32_RAIL,
          'net=%s' % sorted(post_nets['+3V3_ESP32']))
    check("'GND' lost exactly C9..C13 pin 2",
          pre_nets['GND'] - post_nets['GND'] == GND_LOST,
          'lost=%s' % sorted(pre_nets['GND'] - post_nets['GND']))
    check("'GND' gained nothing", not (post_nets['GND'] - pre_nets['GND']))
    check("'+3V3_8388' untouched (this trim is ESP32-rail scoped)",
          pre_nets['+3V3_8388'] == post_nets['+3V3_8388'])
    check("'+3V3' / '+5V' untouched (regulator rail unaffected)",
          pre_nets['+3V3'] == post_nets['+3V3'] and pre_nets['+5V'] == post_nets['+5V'])

    # ---- 3. ERC delta (normalised, not just totals) -------------------------
    a, b = read_erc(pre_erc), read_erc(post_erc)
    if a is None or b is None:
        check('ERC before/after reports compared', False, 'missing report json')
    else:
        check('ERC findings identical (severity+type+items+positions), %d -> %d' % (len(a), len(b)),
              a == b,
              'only_before=%s only_after=%s' % (
                  sorted(set(a) - set(b))[:3], sorted(set(b) - set(a))[:3]))
        check('ERC has no net_conflict finding',
              not [v for v in b if v[1] == 'net_conflict'])

    # ---- 4. chain 1.1.0 -> 1.1.1-as-released -> 1.1.1@1244ad0 -> 1.1.2 -----
    # Every link is applied to the previous link's result and compared against the
    # frozen netlist of that revision, so the chain is verified link by link and
    # not just at its ends.
    if v110:
        c110, n110 = read_netlist(v110)

        # link 1: the 1.1.1 regulator swap (AP7361C-33E-13 -> AP2112K-3.3)
        s1 = {k: set(v) for k, v in n110.items()}
        s1['+5V'] |= LDO_GAINED_PLUS5V
        s1['+3V3'] = (s1['+3V3'] - set(LDO_3V3_PIN_SWAP)) | set(LDO_3V3_PIN_SWAP.values())
        s1['GND'] |= LDO_GAINED_GND
        s1[LDO_NEW_NET[0]] = set(LDO_NEW_NET[1])
        r1 = set(c110) | LDO_ADDED_REFS
        c_r, n_r = read_netlist(v111rel)
        ok = (s1 == n_r) and (r1 == set(c_r))
        detail = 'diff nets=%s refs=%s' % (
            sorted(n for n in set(s1) | set(n_r) if s1.get(n) != n_r.get(n))[:4],
            sorted(r1 ^ set(c_r)))
        check('chain link 1: 1.1.0 + regulator swap == 1.1.1-as-released', ok, detail)

        # link 2: rev 1244ad0 re-placed C41 and left its +3V3 stub floating.
        # PRE-EXISTING DEFECT - deliberately not fixed by this revision.
        s2 = {k: set(v) for k, v in s1.items()}
        s2['+3V3'] = s2['+3V3'] - C41_DEFECT_LOST
        s2[C41_DEFECT_NEW_NET[0]] = set(C41_DEFECT_NEW_NET[1])
        check('chain link 2: 1.1.1-as-released + C41 disconnect (PRE-EXISTING DEFECT, '
              'unchanged here) == 1.1.1@1244ad0',
              s2 == pre_nets and r1 == set(pre_comps),
              'diff nets=%s' % sorted(n for n in set(s2) | set(pre_nets)
                                      if s2.get(n) != pre_nets.get(n))[:4])

        # link 3: this revision's trim
        s3 = {k: {nd for nd in v if nd[0] not in REMOVED} for k, v in s2.items()}
        s3 = {k: v for k, v in s3.items() if v}
        check('chain link 3: 1.1.1@1244ad0 + trim == 1.1.2 (every net)',
              s3 == post_nets and (r1 - REMOVED) == set(post_comps),
              'diff nets=%s' % sorted(n for n in set(s3) | set(post_nets)
                                      if s3.get(n) != post_nets.get(n))[:4])

    out = os.path.join(HERE, 'proof-bulk-cap-trim.json')
    payload = {'revision': '1.1.2',
               'pre': os.path.basename(pre_net),
               'post': os.path.basename(post_net),
               'chain_from': os.path.basename(v110) if v110 else None,
               'chain_via': os.path.basename(v111rel) if v111rel else None,
               'erc_pre': os.path.basename(pre_erc) if pre_erc else None,
               'erc_post': os.path.basename(post_erc) if post_erc else None,
               'erc_findings_pre': len(a) if a is not None else None,
               'erc_findings_post': len(b) if b is not None else None,
               'components_removed': sorted(REMOVED),
               'nets_total': len(post_nets),
               'pre_existing_defect_not_fixed_by_this_revision':
                   ['C41 pin 1 is not on +3V3 from rev 1244ad0 onward '
                    '(net "unconnected-(C41-Pad1)"), see POWER.md section 5'],
               'checks': results}
    with open(out, 'w', encoding='utf-8') as fh:
        json.dump(payload, fh, indent=1)
        fh.write('\n')
    fails = [r for r in results if not r['pass']]
    for r in results:
        print('%-4s %s%s' % ('PASS' if r['pass'] else 'FAIL', r['check'],
                             ('  [' + r['detail'] + ']') if r['detail'] and not r['pass'] else ''))
    print('%d/%d checks pass -> %s' % (len(results) - len(fails), len(results), out))
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
