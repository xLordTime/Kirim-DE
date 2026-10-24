"""Ein englisch/deutsches Paar offizieller .lang-Dateien zusammenführen."""
import argparse
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("kirim_localization", ROOT / "bot" / "localization.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def compile_pair(english, german, output):
    source = module.parse_lang(Path(english).read_bytes())
    target = module.parse_lang(Path(german).read_bytes())
    entries = {key: [en, target[key]] for key, en in source.items() if target.get(key)}
    payload = {"format": 1, "source": "Lokal bereitgestelltes .lang-Dateipaar", "entries": entries}
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    return len(entries)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("english", type=Path)
    parser.add_argument("german", type=Path)
    parser.add_argument("output", type=Path, help="Für eigene Ergänzungen: data/locales/NAME.json")
    args = parser.parse_args()
    print(f"{compile_pair(args.english, args.german, args.output)} Spracheinträge geschrieben.")


if __name__ == "__main__":
    main()
