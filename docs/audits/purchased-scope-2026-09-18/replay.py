"""Fixed-input policy replay, parallel batches with identical per-notice semantics."""
import argparse
import gzip
import json
import sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

def initialise(code, at_text, public_ids):
    global config, at, public, threshold, discovery, translations_module
    sys.path[:0] = [str(Path(code) / 'pipeline'), str(Path(code) / 'scripts')]
    from anthrion_signal.config import load_config
    import anthrion_signal.discovery as d
    from anthrion_signal.utils import parse_date
    config, at, public, discovery = load_config(Path(code)), parse_date(at_text), set(public_ids), d
    threshold = config['capabilities']['discovery']['minimum_candidate_score']

def evaluate(payload):
    batch, translations = payload
    discovery.prefilter(batch, config['company_profile'], config['search_terms'], config['capabilities'], translations)
    rows = []
    for s in batch:
        candidate = not s.exclusion_reasons and s.prefilter_score >= threshold
        overlay = translations.get(s.id, {})
        rows.append(dict(id=s.id, title=overlay.get('title', s.title), original_title=s.title,
            description=overlay.get('description', s.description), original_description=s.description,
            hash=s.content_hash, source=s.source, type=s.signal_type, cpv=s.cpv_codes, countries=s.countries,
            url=s.primary_source_url, existing=s.id in public, candidate=candidate,
            public=candidate and discovery.is_public_opportunity(s, at),
            award=candidate and discovery.is_public_award(s, at), lifecycle=discovery.lifecycle(s, at)[0],
            score=s.prefilter_score, tags=s.matched_capabilities, tier=s.delivery_priority,
            evidence=s.capability_evidence, matches=s.prefilter_matches, scope_evidence=s.scope_evidence,
            reasons=s.exclusion_reasons))
    return rows

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--code', type=Path, required=True)
    parser.add_argument('--data', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--workers', type=int, default=4)
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding='utf-8')
    sys.path[:0] = [str(args.code / 'pipeline'), str(args.code / 'scripts')]
    from audit_relevance import retained_records
    from anthrion_signal.config import load_config
    from anthrion_signal.discovery import discovery_signature
    from anthrion_signal.translation import available_translations
    snapshot = json.loads((args.data / 'data/current.json').read_text(encoding='utf-8'))
    signals, locations = retained_records(args.data)
    translations = available_translations(args.data, signals)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    batches = [(signals[i:i+1000], {s.id: translations[s.id] for s in signals[i:i+1000] if s.id in translations})
               for i in range(0, len(signals), 1000)]
    counts = Counter()
    with ProcessPoolExecutor(max_workers=args.workers, initializer=initialise,
            initargs=(str(args.code), snapshot['generated_at'], [s['id'] for s in snapshot['signals']])) as pool:
        with gzip.open(args.output, 'wt', encoding='utf-8') as handle:
            for rows in pool.map(evaluate, batches):
                for row in rows:
                    handle.write(json.dumps(row, ensure_ascii=False) + '\n')
                    counts['retained'] += 1
                    for key in ('candidate','public','award'):
                        counts[key] += row[key]
                    if row['public']:
                        counts[row['tier']] += 1
                print(f"{args.output.stem}: {counts['retained']}/{len(signals)}", flush=True)
    summary = dict(at=snapshot['generated_at'], code=str(args.code), data=str(args.data),
                   signature=discovery_signature(load_config(args.code)), counts=dict(counts), partitions=locations)
    args.output.with_suffix('.summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    print(json.dumps(summary['counts']))

if __name__ == '__main__':
    main()
