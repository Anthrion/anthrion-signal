"""Inspect fixed-input before/after policy decisions; no provider calls."""
import gzip
import json
from collections import Counter
from pathlib import Path

root = Path(__file__).resolve().parent

def read(name):
    with gzip.open(root / name, 'rt', encoding='utf-8') as handle:
        rows = [json.loads(line) for line in handle]
    assert len(rows) == len({r['id'] for r in rows}), name
    return {r['id']: r for r in rows}

before, after = read('baseline.jsonl.gz'), read('after.jsonl.gz')
assert before.keys() == after.keys()
for key, row in before.items():
    assert all(row[field] == after[key][field] for field in (
        'hash', 'original_title', 'original_description', 'title', 'description', 'cpv', 'url'))

groups = {
    'removed_candidates': [a for key, a in after.items() if before[key]['candidate'] and not a['candidate']],
    'recovered_candidates': [a for key, a in after.items() if not before[key]['candidate'] and a['candidate']],
    'removed_published': [a for key, a in after.items() if before[key]['existing'] and not a['public']],
    'removed_live': [a for key, a in after.items() if before[key]['public'] and not a['public']],
    'recovered_live': [a for key, a in after.items() if not before[key]['public'] and a['public']],
    'removed_awards': [a for key, a in after.items() if before[key]['award'] and not a['award']],
    'recovered_awards': [a for key, a in after.items() if not before[key]['award'] and a['award']],
    'changed_published_labels': [a for key, a in after.items() if before[key]['existing'] and a['public']
                               and (a['tags'], a['tier']) != (before[key]['tags'], before[key]['tier'])],
}
summary = {'retained': len(after), 'unchanged_source_and_translation_content': True}
for name, rows in groups.items():
    (root / (name + '.json')).write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf-8')
    summary[name] = {'count': len(rows), 'sources': dict(Counter(r['source'] for r in rows)),
                     'reasons': dict(Counter(reason for r in rows for reason in r['reasons']))}
(root / 'comparison.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
print(json.dumps(summary, indent=2))
