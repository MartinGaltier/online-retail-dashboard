"""Télécharge (si besoin) et prépare les données, puis écrit le Parquet et le rapport de qualité.

Usage : python scripts/prepare_data.py [--force-download]
"""

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from retail import config  # noqa: E402
from retail.prepare import download_raw, load_raw, prepare, write_outputs  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force-download", action="store_true", help="Retélécharge l'archive UCI.")
    args = parser.parse_args()

    started = time.perf_counter()
    xlsx_path = download_raw(force=args.force_download)
    print(f"Lecture de {xlsx_path.relative_to(config.ROOT_DIR)} (empreinte vérifiée)")
    raw = load_raw(xlsx_path)
    lines, report = prepare(raw)
    write_outputs(lines, report)

    print(f"{len(raw):,} lignes brutes -> {len(lines):,} lignes préparées")
    for rule in report["regles"]:
        print(f"  {rule['code']:<4} {rule['titre']:<48} {rule['lignes']:>8,} lignes")
    print(f"Écart de rapprochement : {report['controle_coherence']['ecart']:.2f} £")
    for path in (config.PROCESSED_FILE, config.QUALITY_JSON, config.QUALITY_MD):
        size = path.stat().st_size / 1e6
        print(f"Écrit : {path.relative_to(config.ROOT_DIR)} ({size:.1f} Mo)")
    print(f"Terminé en {time.perf_counter() - started:.0f} s")


if __name__ == "__main__":
    main()
