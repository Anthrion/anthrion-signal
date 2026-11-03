"""Summarise two frozen corpus replays; no model calls or production data writes."""
import argparse
import csv
import gzip
import io
from collections import Counter
from pathlib import Path

from anthrion_signal.utils import atomic_json, digest, read_json


def compare(before, after, snapshot):
    old = {r['id']: r for r in before['records']}
    new = {r['id']: r for r in after['records']}
    if old.keys() != new.keys() or before['at'] != after['at']:
        raise ValueError('Compare the same retained IDs at the same observation time')
    if any(old[sid][field] != r[field] for sid, r in new.items() for field in ('original_title', 'source_hash', 'url')):
        raise ValueError('The retained source evidence changed between policy replays')
    def compact(r):
        return {key: r[key] for key in ('id', 'source', 'title', 'url', 'lifecycle', 'reasons')}
    losses = [compact(r) for r in new.values() if r['published_before'] and r['relevance'] != 'candidate']
    unavailable = [compact(r) for r in new.values() if r['published_before'] and r['relevance'] == 'candidate' and not r['available']]
    recoveries = [compact(r) for r in new.values() if not r['published_before'] and old[r['id']]['relevance'] != 'candidate'
                  and r['relevance'] == 'candidate' and r['available'] and r['lifecycle'] in ('OPEN', 'EARLY_ENGAGEMENT', 'FUTURE')]
    restored_windows = [compact(r) for r in new.values() if not r['published_before'] and old[r['id']]['relevance'] == 'candidate'
                        and not old[r['id']]['available'] and r['available'] and r['relevance'] == 'candidate'
                        and r['lifecycle'] in ('OPEN', 'EARLY_ENGAGEMENT', 'FUTURE')]
    transitions = Counter(f"{old[sid]['relevance']} -> {r['relevance']}" for sid, r in new.items())
    return {
        'observation_time': after['at'], 'policy': after['version'], 'signature': after.get('signature'), 'snapshot_hash': digest(snapshot),
        'counts_before': before['counts'], 'counts_after': after['counts'], 'transitions': dict(transitions),
        'source_counts': dict(Counter(r['source'] for r in new.values())),
        'source_health': [{k: s.get(k) for k in ('id', 'status', 'records', 'last_success', 'message')} for s in snapshot['sources'] if s['enabled']],
        'scope_removals': losses, 'availability_removals': unavailable, 'active_recoveries': recoveries,
        'availability_recoveries': restored_windows,
        'uncertain_published_windows': [compact(r) for r in new.values() if r['published_before'] and r['relevance'] == 'candidate'
                                        and r['lifecycle'] == 'UNKNOWN' and old[r['id']]['lifecycle'] != 'UNKNOWN'],
        'published_tag_changes': sum(r['published_before'] and old[sid]['tags'] != r['tags'] for sid, r in new.items()),
        'retained_published_tag_changes': sum(r['published_before'] and r['relevance'] == 'candidate' and old[sid]['tags'] != r['tags'] for sid, r in new.items()),
        'unpublished_unknown_candidates': sum(not r['published_before'] and r['relevance'] == 'candidate' and r['available'] and r['lifecycle'] == 'UNKNOWN' for r in new.values()),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, default=Path('artifacts/relevance-audit-2026-09-18'))
    args = parser.parse_args()
    before = read_json(args.directory / 'baseline-replay.json', {})
    after = read_json(args.directory / 'after-replay.json', {})
    summary = compare(before, after, read_json(args.directory / 'baseline-current.json', {}))
    atomic_json(args.directory / 'summary.json', summary)
    old = {r['id']: r for r in before['records']}
    buffer = io.StringIO(newline='')
    writer = csv.writer(buffer)
    writer.writerow(['id', 'source', 'countries', 'title', 'source_url', 'previously_published', 'previous_relevance', 'new_relevance', 'available', 'lifecycle', 'score', 'capabilities', 'reasons'])
    for r in after['records']:
        writer.writerow([r['id'], r['source'], '|'.join(r['countries']), r['title'], r['url'], r['published_before'], old[r['id']]['relevance'], r['relevance'], r['available'], r['lifecycle'], r['score'], '|'.join(r['tags']), '|'.join(r['reasons'])])
    (args.directory / 'decision-register.csv.gz').write_bytes(gzip.compress(buffer.getvalue().encode('utf-8'), mtime=0))
    print(f"Scope removals: {len(summary['scope_removals'])}; availability corrections: {len(summary['availability_removals'])}; active recoveries: {len(summary['active_recoveries'])}")


if __name__ == '__main__':
    main()
