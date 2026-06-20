#!/usr/bin/env python3
"""CLI: merge financial and product artifacts from a run directory into a consolidated JSON."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cdd.artifacts import artifact_kind, iter_structured  # noqa: E402
from cdd.merge import merge_financials, merge_products  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Merge financial and product artifacts in a run directory."
    )
    parser.add_argument("--run-dir", required=True, help="Path to the run directory.")
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    financials: list[dict[str, object]] = []
    products: list[dict[str, object]] = []

    for _path, doc in iter_structured(run_dir):
        kind = artifact_kind(doc)
        if kind == "financial":
            financials.append(doc)
        elif kind == "product":
            products.append(doc)

    financial_result = merge_financials(financials)
    product_result = merge_products(products)

    result: dict[str, object] = {
        "financial": financial_result,
        "product": product_result,
    }

    out_path = run_dir / "structured" / "_merged.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")

    financial_conflicts: list[object] = financial_result.get("conflicts", [])  # type: ignore[assignment]
    product_conflicts: list[object] = product_result.get("conflicts", [])  # type: ignore[assignment]
    total_conflicts = len(financial_conflicts) + len(product_conflicts)
    print(f"conflicts={total_conflicts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
