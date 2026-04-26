This file is a guide for future Codex sessions working in this repository. Keep it concise and update it when the repository layout or workflow changes.

## Project Intro

This is the FAI 2026 final project: a Python framework for building and evaluating agents for 6 Nimmt!. A game uses cards 1 through 104, four table rows, four players by default, and ten rounds. Each round, every player chooses one card, then cards are resolved from smallest to largest.

Key rules: place a card on the row whose tail is smaller than the card and closest to it; taking the sixth card in a row collects that row as penalty; if the card is lower than every row tail, the engine takes the row with lowest bullhead score, then shortest length, then lowest row index. Lower final penalty is better, and tournaments rank by average rank with fractional ties.

Important implementation constraints from the spec: Python 3.13.11, allowed packages from `requirements.txt`, 1 second per `action()` call, 1 GB memory limit, no multiprocessing/threading in player code, and no bare `except:` or `except BaseException` because the timeout exception inherits from `BaseException`.

## Directory Structure

- `project-spec.pdf`: assignment specification/slides.
- `README.md`: official usage notes, config schema, and warning summary.
- `requirements.txt`: official dependency list.
- `activate.fish`: local fish virtualenv helper.
- `run_single_game.py`: CLI for one game simulation.
- `run_tournament.py`: CLI for tournament runs.
- `configs/game/`: single-game JSON configs.
- `configs/tournament/`: tournament JSON configs.
- `src/engine.py`: authoritative game engine and rule implementation.
- `src/game_utils.py`: player config normalization and dynamic class loading.
- `src/tournament_runner.py`: tournament implementations and standings logic.
- `src/players/TA/`: TA-provided players and binary baselines.
- `src/players/student/`: student-owned player code and local simulation helpers.
- `src/players/student/test/`: tests for student helper code.

Ignored/generated paths from `.gitignore`: `__pycache__/`, `results/`, `data/`, `.venv/`, `tmp/`, and `log/`. Do not treat generated outputs in those paths as source files.

Place new source files under the most specific existing folder: player implementations and helper code in `src/players/student/`, helper tests in `src/players/student/test/`, game configs in `configs/game/`, and tournament configs in `configs/tournament/`.

## Codebase Knowledge

`src/engine.py` is the source of truth for game behavior. `Engine.reset()` shuffles/deals and initializes board/history. `Engine.play_round()` passes each player a copied hand and deep-copied history, handles timeout/exception/invalid-move fallbacks, records actions, sorts cards, and applies placements. `Engine.process_card_placement()` implements closest-fit placement, sixth-card row taking, low-card row selection, and score updates. `TimeoutException` inherits from `BaseException`, so player code must not catch it accidentally.

The `history` argument passed to `action(hand, history)` contains `board`, `scores`, `round`, `history_matrix`, `board_history`, and `score_history`. Hands are sorted by the engine when dealt.

`src/game_utils.py` loads players from configs. Entries may be dicts with `path`, `class`, `args`, and `label`, or compact lists such as `["module.path", "ClassName", {"arg": "value"}, "label"]`. `_preprocess_player_config()` merges `players` and `baselines`.

`src/tournament_runner.py` provides `CombinationTournamentRunner`, `RandomPartitionTournamentRunner`, and `GroupedRandomPartitionTournamentRunner`. Final-style evaluation is represented by `random_partition`. Runner-level parallelism is controlled by tournament config `num_workers`; do not add parallelism inside player code.

`src/players/student/customized_engine.py` is a compact rollout simulator that stores row tail, row count, and row score instead of full row lists. `src/players/student/monte_carlo.py` defines `MonteCarloPlayer`, which infers unseen cards, samples opponent hands, runs random rollouts with `CustomizedEngine`, and chooses the card with lowest simulated final rank. `src/players/student/test/test_customized_engine_stress.py` checks that `CustomizedEngine` matches `Engine` under random stress.

`src/players/TA/random_player.py` and `src/players/TA/human_player.py` are readable reference players. `src/players/TA/public_baselines1.cpython-313-x86_64-linux-gnu.so` is an opaque binary baseline module.

## Common Commands

```bash
python run_single_game.py --config configs/game/example.json
python run_tournament.py --config configs/tournament/example.json
python -m unittest src.players.student.test.test_customized_engine_stress
SIX_NIMMT_STRESS_GAMES=100 python -m unittest src.players.student.test.test_customized_engine_stress
```

## Workflow Notes

Before editing, run `git status --short` and preserve user changes. Do not revert files unless explicitly asked. Prefer small, scoped edits that follow the existing code style. Keep generated outputs, caches, virtualenvs, and scratch files out of git.

When changing player or simulation code, re-read the relevant engine behavior first. Keep player code single-threaded, offline, memory-conscious, and comfortably under the action timeout. Use specific exception handling only; never use bare `except:` or `except BaseException`.

Never commit anything unless explicitly instructed. Always ask for review and approval after any change.
