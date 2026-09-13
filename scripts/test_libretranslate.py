"""Evaluate the real LibreTranslate API locally, without changing production data."""
import importlib.metadata
import json
import os
import time
from collections import Counter
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1]
    work = root / "tmp/libre-benchmark"
    work.mkdir(parents=True, exist_ok=True)
    output = root / "artifacts/translation-benchmark/libretranslate"
    output.mkdir(parents=True, exist_ok=True)
    for name, folder in (("XDG_DATA_HOME", "data"), ("XDG_CONFIG_HOME", "config"),
                         ("XDG_CACHE_HOME", "cache")):
        os.environ[name] = str(work / folder)
    os.environ["ARGOS_PACKAGES_DIR"] = str(root / "tmp/argos-benchmark/packages")
    os.environ["MINISBD_MODEL_DIR"] = str(root / "tmp/argos-benchmark/minisbd")
    os.environ["ARGOS_DEVICE_TYPE"] = "cpu"
    os.environ["ARGOS_INTRA_THREADS"] = "2"
    os.environ["ARGOS_INTER_THREADS"] = "1"
    os.environ["ARGOS_COMPUTE_TYPE"] = "float32"
    os.environ["ARGOS_CHUNK_TYPE"] = "MINISBD"
    os.chdir(work)

    from argostranslate import package
    from libretranslate.main import get_parser
    from libretranslate.app import create_app

    corpus = [json.loads(line) for line in
              (root / "artifacts/translation-benchmark/float32/results.jsonl").read_text().splitlines()]
    package.update_package_index()
    installed = {p.from_code: p.package_version for p in package.get_installed_packages() if p.to_code == "en"}
    available = {p.from_code: p.package_version for p in package.get_available_packages() if p.to_code == "en"}
    changed_models = {lang: available.get(lang) for lang, version in installed.items() if available.get(lang) != version}
    if changed_models:
        raise RuntimeError(f"Review updated models before running: {changed_models}")
    args = get_parser().parse_args(["--disable-web-ui", "--disable-files-translation", "--req-limit", "0"])
    app = create_app(args)
    client = app.test_client()
    manifest = {
        "versions": {name: importlib.metadata.version(name) for name in ["libretranslate", "argos-translate-lt", "ctranslate2"]},
        "models": installed,
        "compute_type": "float32",
        "api": "Flask test client POST /translate, explicit source, target=en",
        "languages": client.get("/languages").get_json(),
        "input_characters": sum(len(row["source"]) for row in corpus),
        "passages": len(corpus),
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2))
    results_path = output / "results.jsonl"
    cached = {json.loads(line)["hash"] for line in results_path.read_text().splitlines()} if results_path.exists() else set()
    started, counts, failures = time.monotonic(), Counter(), 0
    with results_path.open("a", encoding="utf-8") as stream:
        for index, row in enumerate(corpus):
            if row["hash"] in cached:
                counts[row["language"]] += len(row["source"])
                continue
            begin = time.monotonic()
            response = client.post("/translate", json={"q": row["source"], "source": row["language"], "target": "en", "format": "text"})
            payload = response.get_json()
            result = {key: row[key] for key in ("id", "url", "language", "source", "hash")}
            result.update(status=response.status_code, english=payload.get("translatedText"),
                          error=payload.get("error"), seconds=time.monotonic() - begin)
            stream.write(json.dumps(result, ensure_ascii=True) + "\n")
            stream.flush()
            failures += int(response.status_code != 200)
            counts[row["language"]] += len(row["source"])
            if index % 10 == 0:
                print(json.dumps({"passages": index + 1, "characters": sum(counts.values()), "failures": failures}), flush=True)
    manifest.update(completed_characters=sum(counts.values()), by_language=dict(counts),
                    failures=failures, elapsed_seconds=time.monotonic() - started)
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(json.dumps(manifest, indent=2), flush=True)


if __name__ == "__main__":
    main()
