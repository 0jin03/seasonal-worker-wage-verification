# -*- coding: utf-8 -*-
import json, os, sys, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from jsonschema import Draft202012Validator
from gen_engine import make
from specs import SPECS

ROOT = "/Users/kim-yeongjin/Desktop/비타민 플젝_NLP"
OUT = os.path.join(ROOT, "계절근로자_결함케이스_20세트")
schema = json.load(open(os.path.join(ROOT, "R00-R11_최종_JSON_Schema_v3.2.json"), encoding="utf-8"))
V = Draft202012Validator(schema)

TARGET = {}
for s in SPECS[:10]:
    TARGET[s['id']] = 3
for s in SPECS[10:15]:
    TARGET[s['id']] = 4
for s in SPECS[15:]:
    TARGET[s['id']] = 5

WRITE = '--write' in sys.argv
rows = []
allok = True
for spec in SPECS:
    try:
        case, ctx = make(spec)
    except Exception as e:
        import traceback
        print(f"[ERR] {spec['id']}: {e}")
        traceback.print_exc()
        allok = False
        continue
    rr = case['rule_results']
    bad = [(r, rr[r][r.lower() + '_result']) for r in rr if rr[r][r.lower() + '_result'] != 'PASS']
    errs = sorted(V.iter_errors(case), key=lambda e: list(e.path))
    tgt = TARGET[spec['id']]
    ok = (len(bad) == tgt and not errs)
    allok &= ok
    mark = "OK " if ok else "XX "
    print(f"{mark}{spec['id']} {spec['name']:<20} 목표{tgt} 실제{len(bad)} {bad}")
    for e in errs[:5]:
        print("     schema:", "/".join(map(str, e.path)), "->", e.message[:120])
    if not ok:
        for r in rr:
            print("     ", r, rr[r][r.lower() + '_result'], rr[r][r.lower() + '_reason'][:90])
    rows.append((spec, case, bad))

print("\n분포:", collections.Counter(len(b) for _, _, b in rows))
if WRITE and allok:
    os.makedirs(OUT, exist_ok=True)
    for spec, case, bad in rows:
        d = os.path.join(OUT, spec['id'])
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, spec['id'] + '.json'), 'w', encoding='utf-8') as f:
            json.dump(case, f, ensure_ascii=False, indent=2)
            f.write('\n')
    print(f"\n{len(rows)}세트 저장 완료 -> {OUT}")
elif WRITE:
    print("\n검증 실패로 저장하지 않음")
