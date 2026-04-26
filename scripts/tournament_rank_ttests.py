#!/usr/bin/env python3
"""Pairwise t-tests for tournament rank logs."""

from __future__ import annotations

import argparse
import itertools
import json
import math
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np
from scipy import stats


DEFAULT_RESULTS_DIR = Path("results") / "tournament"
GREEN = "\033[32m"
RED = "\033[31m"
RESET = "\033[0m"


def latest_log_path(results_dir: Path = DEFAULT_RESULTS_DIR) -> Path:
    paths = list(results_dir.glob("*.json"))
    if not paths:
        raise FileNotFoundError(f"No tournament logs found in {results_dir}")
    return max(paths, key=lambda path: path.stat().st_mtime)


def load_log(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"{path} does not contain a JSON object")
    return data


def compact_player_configs(config: dict[str, Any]) -> list[Any]:
    return list(config.get("players", [])) + list(config.get("baselines", []))


def player_label(config: dict[str, Any], player_id: int) -> str:
    player_configs = compact_player_configs(config)
    cfg = player_configs[player_id] if 0 <= player_id < len(player_configs) else None

    label = None
    class_name = None
    if isinstance(cfg, dict):
        label = cfg.get("label")
        class_name = cfg.get("class")
    elif isinstance(cfg, list):
        if len(cfg) >= 4:
            label = cfg[3]
        if len(cfg) >= 2:
            class_name = cfg[1]

    name = label or class_name or f"player_{player_id}"
    return f"{player_id}:{name}"


def duplicate_count(config: dict[str, Any]) -> int:
    tournament = config.get("tournament", {})
    engine = config.get("engine", {})
    n_players = int(engine.get("n_players", 4))

    if "use_permutations" in tournament:
        mode = "permutations" if tournament["use_permutations"] else "none"
    else:
        mode = tournament.get("duplication_mode", "permutations")

    if mode == "permutations":
        return math.factorial(n_players)
    if mode == "cycle":
        return n_players
    return 1


def iter_result_lists(history: Any) -> list[list[dict[str, Any]]]:
    """Return all matchup result lists from all supported tournament histories."""
    result_lists: list[list[dict[str, Any]]] = []

    def is_player_result_list(node: list[Any]) -> bool:
        return all(
            isinstance(item, dict) and "id" in item and "rank" in item
            for item in node
        )

    def visit(node: Any) -> None:
        if isinstance(node, dict):
            results = node.get("results")
            if isinstance(results, list):
                if is_player_result_list(results):
                    result_lists.append(results)
                else:
                    for item in results:
                        visit(item)
            for key in ("stage1", "stage2"):
                if key in node:
                    visit(node[key])
        elif isinstance(node, list):
            if is_player_result_list(node):
                result_lists.append(node)
                return
            for item in node:
                visit(item)

    visit(history)
    return result_lists


def rank_observations(data: dict[str, Any]) -> dict[int, list[float]]:
    divisor = duplicate_count(data.get("config", {}))
    observations: dict[int, list[float]] = defaultdict(list)

    for result_list in iter_result_lists(data.get("history", [])):
        for result in result_list:
            rank = result.get("rank")
            player_id = result.get("id")
            if rank is None or player_id is None:
                continue
            observations[int(player_id)].append(float(rank) / divisor)

    return dict(observations)


def format_float(value: float) -> str:
    if math.isnan(value):
        return "nan"
    if math.isinf(value):
        return "inf" if value > 0 else "-inf"
    return f"{value:.2e}"


def color_text(text: str, color: str, enabled: bool) -> str:
    if not enabled:
        return text
    return f"{color}{text}{RESET}"


def player_order_by_avg_rank(observations: dict[int, list[float]]) -> list[int]:
    def sort_key(player_id: int) -> tuple[float, int]:
        values = observations[player_id]
        mean = float(np.mean(values)) if values else float("inf")
        return mean, player_id

    return sorted(observations, key=sort_key)


def holm_adjust(p_values: list[float]) -> list[float]:
    indexed = sorted(enumerate(p_values), key=lambda item: item[1])
    adjusted = [float("nan")] * len(p_values)
    running_max = 0.0
    m = len(p_values)
    for rank, (idx, p_value) in enumerate(indexed):
        value = min(1.0, (m - rank) * p_value)
        running_max = max(running_max, value)
        adjusted[idx] = running_max
    return adjusted


def welch_tests(
    observations: dict[int, list[float]],
    config: dict[str, Any],
    alpha: float,
    adjust: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    player_ids = sorted(observations)

    for a, b in itertools.combinations(player_ids, 2):
        xs = np.asarray(observations[a], dtype=float)
        ys = np.asarray(observations[b], dtype=float)
        if len(xs) < 2 or len(ys) < 2:
            t_stat = float("nan")
            p_value = float("nan")
        else:
            result = stats.ttest_ind(xs, ys, equal_var=False, nan_policy="omit")
            t_stat = float(result.statistic)
            p_value = float(result.pvalue)

        rows.append(
            {
                "a": a,
                "b": b,
                "player_a": player_label(config, a),
                "player_b": player_label(config, b),
                "n_a": len(xs),
                "n_b": len(ys),
                "mean_a": float(np.mean(xs)) if len(xs) else float("nan"),
                "mean_b": float(np.mean(ys)) if len(ys) else float("nan"),
                "diff_a_minus_b": float(np.mean(xs) - np.mean(ys)) if len(xs) and len(ys) else float("nan"),
                "t": t_stat,
                "p": p_value,
            }
        )

    if adjust == "holm":
        adjusted = holm_adjust([row["p"] for row in rows])
    elif adjust == "bonferroni":
        adjusted = [min(1.0, row["p"] * len(rows)) for row in rows]
    else:
        adjusted = [row["p"] for row in rows]

    for row, adjusted_p in zip(rows, adjusted):
        row["p_adjusted"] = adjusted_p
        row["reject"] = bool(adjusted_p < alpha) if not math.isnan(adjusted_p) else False

    rows.sort(key=lambda row: (row["p_adjusted"], row["p"]))
    return rows


def print_summary(path: Path, observations: dict[int, list[float]], config: dict[str, Any]) -> None:
    print(f"Log: {path}")
    print("Rank observations per player:")
    for player_id in player_order_by_avg_rank(observations):
        values = np.asarray(observations[player_id], dtype=float)
        mean = float(np.mean(values)) if len(values) else float("nan")
        std = float(np.std(values, ddof=1)) if len(values) > 1 else float("nan")
        print(
            f"  {player_label(config, player_id):<28} "
            f"n={len(values):<4} mean={format_float(mean):>8} std={format_float(std):>8}"
        )


def print_pvalue_matrix(
    rows: list[dict[str, Any]],
    observations: dict[int, list[float]],
    config: dict[str, Any],
    color: bool,
) -> None:
    ordered_ids = player_order_by_avg_rank(observations)
    p_values: dict[tuple[int, int], float] = {}
    rejects: dict[tuple[int, int], bool] = {}
    for row in rows:
        p_values[(row["a"], row["b"])] = row["p"]
        p_values[(row["b"], row["a"])] = row["p"]
        rejects[(row["a"], row["b"])] = row["reject"]
        rejects[(row["b"], row["a"])] = row["reject"]

    print()
    print("Pairwise p-value matrix ordered by avg rank")
    print("Rows beat columns when the row is above the column; cells are two-sided Welch p-values.")
    header = f"{'player':<28}" + "".join(f"{player_id:>12}" for player_id in ordered_ids)
    print(header)
    print("-" * len(header))
    for row_idx, row_id in enumerate(ordered_ids):
        cells = []
        for col_idx, col_id in enumerate(ordered_ids):
            if row_idx == col_idx:
                cells.append(f"{'-':>12}")
            elif row_idx < col_idx:
                value = f"{format_float(p_values[(row_id, col_id)]):>12}"
                cell_color = GREEN if rejects[(row_id, col_id)] else RED
                cells.append(color_text(value, cell_color, color))
            else:
                cells.append(f"{'':>12}")
        print(f"{player_label(config, row_id):<28}" + "".join(cells))


def print_tests(rows: list[dict[str, Any]], alpha: float, adjust: str) -> None:
    print()
    print(
        "Welch two-sample t-tests for H0: expected ranks are equal "
        f"(alpha={alpha}, p adjustment={adjust})"
    )
    header = (
        f"{'player_a':<28} {'player_b':<28} {'n_a':>4} {'n_b':>4} "
        f"{'mean_a':>9} {'mean_b':>9} {'diff':>9} {'t':>9} "
        f"{'p':>9} {'p_adj':>9} {'reject':>7}"
    )
    print(header)
    print("-" * len(header))
    for row in rows:
        print(
            f"{row['player_a']:<28} {row['player_b']:<28} "
            f"{row['n_a']:>4} {row['n_b']:>4} "
            f"{format_float(row['mean_a']):>9} {format_float(row['mean_b']):>9} "
            f"{format_float(row['diff_a_minus_b']):>9} {format_float(row['t']):>9} "
            f"{format_float(row['p']):>9} {format_float(row['p_adjusted']):>9} "
            f"{str(row['reject']):>7}"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Run pairwise t-tests for "expected ranks are equal" from a tournament log.'
    )
    parser.add_argument(
        "log_file",
        nargs="?",
        type=Path,
        help="Path to a tournament JSON log. Defaults to the latest results/tournament/*.json.",
    )
    parser.add_argument(
        "--alpha",
        type=float,
        default=0.05,
        help="Significance level used in the reject column. Default: 0.05.",
    )
    parser.add_argument(
        "--adjust",
        choices=("holm", "bonferroni", "none"),
        default="holm",
        help="Multiple-comparison p-value adjustment. Default: holm.",
    )
    parser.add_argument(
        "--details",
        action="store_true",
        help="Show the detailed pairwise t-test table. Hidden by default.",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable ANSI colors in the p-value matrix.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    path = args.log_file or latest_log_path()
    data = load_log(path)
    config = data.get("config", {})
    observations = rank_observations(data)

    if len(observations) < 2:
        print("Need rank observations for at least two players.", file=sys.stderr)
        return 1

    print_summary(path, observations, config)
    rows = welch_tests(observations, config, args.alpha, args.adjust)
    print_pvalue_matrix(rows, observations, config, color=not args.no_color)
    if args.details:
        print_tests(rows, args.alpha, args.adjust)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
