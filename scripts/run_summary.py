import json
import os
from pathlib import Path

path = Path("data/run_metadata.json")
if path.exists():
    run = json.loads(path.read_text(encoding="utf-8"))
    labels = {"sources_attempted": "Sources attempted", "sources_succeeded": "Sources succeeded", "raw_records": "Raw records fetched",
        "new_signals": "New canonical signals", "material_updates": "Materially updated signals", "duplicates_merged": "Duplicates merged",
        "public_signals": "Published candidates", "new_public_signals": "New public candidates",
        "suppressed_unavailable_signals": "Unavailable records excluded", "suppressed_scope_signals": "Out-of-scope records excluded"}
    body = "## Anthrion Signal\n\n"
    plan_path = Path("tmp/refresh-plan.json")
    if plan_path.exists():
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        body += f"{plan['collection_reason']}. Collection step: {os.getenv('COLLECTION_OUTCOME', 'not reported')}.\n\n"
        body += f"Pipeline verification planned: **{plan['test_mode']}**. Browser checks run in the publication job.\n\n"
    body += f"Latest completed collection statistics ({run.get('finished_at', 'unknown time')}):\n\n"
    body += "| Metric | Count |\n| --- | ---: |\n" + "\n".join(f"| {label} | {run.get(key, 0)} |" for key, label in labels.items())
    translation_path = Path("data/translation/summary.json")
    if translation_path.exists():
        translation = json.loads(translation_path.read_text(encoding="utf-8"))
        body += f"\n\n### English translation\n\nStep outcome: {os.getenv('TRANSLATION_OUTCOME', 'not reported')}. "
        body += f"Last completed pass: {translation.get('finished_at', 'not recorded')}.\n\n"
        body += f"Completed fields: {translation.get('completed_fields', 0)}; outstanding fields: {translation.get('pending_fields', 0)}; "
        body += f"HTTP attempts: {translation.get('api_calls', 0)}; stop reason: {translation.get('stop_reason', 'unknown')}.\n"
        for group, label in (("current", "Current opportunities"), ("awards", "Awarded records")):
            coverage = translation.get("notice_coverage", {}).get(group)
            if coverage:
                body += f"{label}: {coverage['complete']} / {coverage['records']} complete titles and descriptions.\n"
        body += "Original notices remain available for any outstanding translations.\n"
    body += "\n\nDeployment outcome is reported by the GitHub Pages deployment job.\n"
    print(body)
    if os.getenv("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as stream:
            stream.write(body)
