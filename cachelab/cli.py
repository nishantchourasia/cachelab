"""Command-line entry point for CacheLab.

    python -m cachelab.cli export     # safe copy from the gem5 research tree
    python -m cachelab.cli build      # ingest, validate, write dataset + reports
    python -m cachelab.cli status     # summarise the current dataset
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from cachelab.export import export
from cachelab.ingest import default_export_root, load_dataset, write_csv
from cachelab.report import results_tables, validity_report
from cachelab.validate import validate_dataset

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DOCS_DIR = PROJECT_ROOT / "docs"


def cmd_export(args: argparse.Namespace) -> int:
    result = export(source=args.source, force=args.force)
    print(f"exported {result['runs_exported']} runs to {result['export_root']}")
    print(f"  files copied  : {result['files_copied']}")
    print(f"  files reused  : {result['files_reused']}")
    print(f"  still running : {result['runs_skipped_unfinished']} (skipped, will export when finished)")
    return 0


def cmd_build(args: argparse.Namespace) -> int:
    records = load_dataset(args.export_root)
    if not records:
        print("no runs found. Run `python -m cachelab.cli export` first.", file=sys.stderr)
        return 1

    report = validate_dataset(records)

    dataset_path = write_csv(records, DATA_DIR / "dataset.csv")
    valid_path = write_csv(
        [r for r in records if r.valid], DATA_DIR / "dataset_valid.csv"
    )

    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    (DOCS_DIR / "VALIDITY.md").write_text(validity_report(records, report))
    (DOCS_DIR / "RESULTS.md").write_text(results_tables(records))

    print(f"ingested {report.total} runs")
    print(f"  valid    : {report.valid} ({report.valid_fraction:.1%})")
    print(f"  excluded : {report.invalid}")
    if report.flag_counts:
        for flag, count in report.flag_counts.most_common():
            print(f"      {flag:28} {count}")
    print()
    print(f"wrote {dataset_path.relative_to(PROJECT_ROOT)}")
    print(f"wrote {valid_path.relative_to(PROJECT_ROOT)}")
    print(f"wrote docs/VALIDITY.md")
    print(f"wrote docs/RESULTS.md")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    root = Path(args.export_root or default_export_root())
    if not root.is_dir():
        print(f"no export at {root}. Run `python -m cachelab.cli export`.")
        return 1

    records = load_dataset(root)
    report = validate_dataset(records)

    print(f"export   : {root}")
    print(f"runs     : {report.total}")
    print(f"valid    : {report.valid} ({report.valid_fraction:.1%})")
    print(f"excluded : {report.invalid}")
    for cores, benchmark, reasons in report.cells_excluded:
        print(f"    {cores}core {benchmark:14} {reasons}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="cachelab", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_export = sub.add_parser("export", help="copy finished gem5 runs into CacheLab")
    p_export.add_argument("--source", help="gem5 research tree (read-only)")
    p_export.add_argument("--force", action="store_true", help="re-copy everything")
    p_export.set_defaults(func=cmd_export)

    p_build = sub.add_parser("build", help="ingest, validate and write reports")
    p_build.add_argument("--export-root", help="override export location")
    p_build.set_defaults(func=cmd_build)

    p_status = sub.add_parser("status", help="summarise the current dataset")
    p_status.add_argument("--export-root", help="override export location")
    p_status.set_defaults(func=cmd_status)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
