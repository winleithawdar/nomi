from __future__ import annotations

import argparse
from pathlib import Path

from nomi_backend.evaluation.harness import (
    DEFAULT_SEED,
    DEFAULT_SENIORS_PER_SCENARIO,
    render_json,
    render_markdown,
    run_evaluation,
)


def _default_out() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / ".git").exists():
            return parent / "docs" / "workstreams" / "P2"
    return Path("docs/workstreams/P2")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="nomi_backend.evaluation")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument(
        "--seniors-per-scenario", type=int, default=DEFAULT_SENIORS_PER_SCENARIO
    )
    parser.add_argument("--out", type=str, default=None)
    args = parser.parse_args(argv)

    report = run_evaluation(
        seed=args.seed, seniors_per_scenario=args.seniors_per_scenario
    )

    out_dir = Path(args.out) if args.out else _default_out()
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "evaluation-results.json").write_text(
        render_json(report) + "\n", encoding="utf-8"
    )
    (out_dir / "evaluation-results.md").write_text(
        render_markdown(report), encoding="utf-8"
    )
    print(
        f"wrote {out_dir/'evaluation-results.json'} and "
        f"{out_dir/'evaluation-results.md'} (selected window "
        f"{report['selected_window']})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
