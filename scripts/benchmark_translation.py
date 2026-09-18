"""Isolated Argos evaluation; never modifies public records or installs into the application."""
import argparse
import hashlib
import json
import os
import re
import time
from collections import Counter, defaultdict
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--characters", type=int, default=100_000)
    parser.add_argument("--compute-type", choices=["int8", "float32"], default="float32")
    args = parser.parse_args()
    root = args.root.resolve()
    work = root / "tmp/argos-benchmark"
    output = root / "artifacts/translation-benchmark" / args.compute_type
    output.mkdir(parents=True, exist_ok=True)
    for name, folder in (("XDG_DATA_HOME", "data"), ("XDG_CONFIG_HOME", "config"),
                         ("XDG_CACHE_HOME", "cache")):
        os.environ[name] = str(work / folder)
    os.environ["ARGOS_PACKAGES_DIR"] = str(work / "packages")
    os.environ["ARGOS_DEVICE_TYPE"] = "cpu"
    os.environ["ARGOS_INTRA_THREADS"] = "2"
    os.environ["ARGOS_INTER_THREADS"] = "1"
    os.environ["ARGOS_COMPUTE_TYPE"] = args.compute_type
    os.environ["ARGOS_CHUNK_TYPE"] = "MINISBD"
    os.environ["MINISBD_MODEL_DIR"] = str(work / "minisbd")
    import argostranslate.package as package
    import argostranslate.translate as translate
    from langid.langid import LanguageIdentifier, model

    detector = LanguageIdentifier.from_modelstring(model, norm_probs=True)
    detector.set_languages(["en", "de", "es", "it", "fi", "sv", "da", "el", "no", "nb", "is"])
    data = json.loads((root / "data/current.json").read_text(encoding="utf-8"))
    corpus, seen = defaultdict(list), set()
    for signal in sorted(data["signals"], key=lambda s: s["id"]):
        text = signal["title"] + "\n\n" + signal["description"]
        language, probability = detector.classify(text[:4000])
        if language == "en" or probability < 0.8:
            continue
        # Complete short passages allow review without truncating model output.
        pieces = re.split(r"(?<=[.!?])\s+|\n+", text)
        chunks, pending = [], ""
        for piece in pieces:
            if len(pending) + len(piece) > 1100 and pending:
                chunks.append(pending)
                pending = ""
            pending = (pending + " " + piece).strip()
        if pending:
            chunks.append(pending)
        for chunk in chunks:
            if len(chunk) < 80 or len(chunk) > 2500 or chunk in seen:
                continue
            seen.add(chunk)
            corpus[language].append({"id": signal["id"], "url": signal["primary_source_url"],
                                     "language": language, "source": chunk})
    package.update_package_index()
    available = {p.from_code: p for p in package.get_available_packages() if p.to_code == "en"}
    missing = sorted(set(corpus) - set(available))
    installed = {p.from_code for p in package.get_installed_packages() if p.to_code == "en"}
    supported = sorted(set(corpus) & set(available))
    print(json.dumps({"corpus_characters": {k: sum(len(r["source"]) for r in v) for k, v in corpus.items()},
                      "supported": supported, "missing_models": missing}), flush=True)
    selected, total = [], 0
    positions = Counter()
    while total < args.characters:
        progress = False
        for language in supported:
            if positions[language] < len(corpus[language]):
                entry = corpus[language][positions[language]]
                positions[language] += 1
                selected.append(entry)
                total += len(entry["source"])
                progress = True
            if total >= args.characters:
                break
        if not progress:
            break
    manifest = {"input_feed_digest": data["run"]["content_digest"], "compute_type": args.compute_type,
                "requested_characters": args.characters,
                "input_characters": total, "missing_models": missing, "records": len(selected),
                "models": {k: {"version": available[k].package_version, "urls": available[k].links} for k in supported}}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    results = output / "results.jsonl"
    cached = {r["hash"]: r for line in results.read_text(encoding="utf-8").split("\n")
              if line.strip() and (r := json.loads(line))} if results.exists() else {}
    for language in supported:
        if language not in installed:
            print(f"Installing {language} -> en model", flush=True)
            path = available[language].download()
            package.install_from_path(path)
    counts = Counter()
    started = time.monotonic()
    with results.open("a", encoding="utf-8") as stream:
        for index, entry in enumerate(selected):
            key = hashlib.sha256((entry["language"] + ":" + entry["source"]).encode()).hexdigest()
            if key in cached:
                counts[entry["language"]] += len(entry["source"])
                continue
            begin = time.monotonic()
            translated = translate.translate(entry["source"], entry["language"], "en")
            record = {**entry, "hash": key, "english": translated, "seconds": time.monotonic() - begin}
            stream.write(json.dumps(record, ensure_ascii=True) + "\n")
            stream.flush()
            counts[entry["language"]] += len(entry["source"])
            if index % 10 == 0:
                print(json.dumps({"passages": index + 1, "characters": sum(counts.values()),
                                  "seconds": round(time.monotonic() - started, 1)}), flush=True)
    manifest.update(completed_characters=sum(counts.values()), by_language=dict(counts),
                    elapsed_seconds=time.monotonic() - started)
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2), flush=True)


if __name__ == "__main__":
    main()
