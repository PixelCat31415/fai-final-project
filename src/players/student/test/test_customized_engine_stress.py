import copy
import os
import random
import unittest

from src.players.student.customized_engine import CustomizedEngine
from src.engine import Engine


class RandomPlayer:
    """Self-contained equivalent of the TA random player without side effects."""

    def __init__(self, player_idx: int, seed: int):
        self.player_idx = player_idx
        self.rng = random.Random(seed)

    def action(self, hand, history):
        return self.rng.choice(hand)


def _build_initial_state(seed: int, n_cards: int, n_players: int, n_rounds: int, board_size_y: int):
    deck = list(range(1, n_cards + 1))
    random.Random(seed).shuffle(deck)

    board = [[deck.pop()] for _ in range(board_size_y)]
    hands = [sorted(deck.pop() for _ in range(n_rounds)) for _ in range(n_players)]
    return board, hands


def _custom_rows_snapshot(custom_engine: CustomizedEngine):
    return [(row.tail, row.cnt, row.score) for row in custom_engine.rows]


def _build_custom_history(round_idx: int, board, scores, actions, score_after_round):
    return {
        "round": round_idx,
        "board_before_round": copy.deepcopy(board),
        "actions": list(actions),
        "scores_after_round": list(score_after_round),
    }


def _format_mismatch(seed: int, player_seeds: list[int], initial_board, initial_hands, engine_trace, custom_trace):
    return "\n".join(
        [
            "CustomizedEngine mismatch detected.",
            f"game_seed={seed}",
            f"player_seeds={player_seeds}",
            f"initial_board={initial_board}",
            f"initial_hands={initial_hands}",
            f"engine_trace={engine_trace}",
            f"custom_trace={custom_trace}",
        ]
    )


class CustomizedEngineStressTest(unittest.TestCase):
    def test_customized_engine_matches_engine_under_random_stress(self):
        n_games = int(os.environ.get("SIX_NIMMT_STRESS_GAMES", "2000"))
        n_players = 4
        n_rounds = 10
        n_cards = 104
        board_size_y = 4
        root_rng = random.Random(20260422)

        for _ in range(n_games):
            seed = root_rng.randrange(1 << 31)
            player_seeds = [root_rng.randrange(1 << 31) for _ in range(n_players)]
            initial_board, initial_hands = _build_initial_state(seed, n_cards, n_players, n_rounds, board_size_y)

            engine_players = [RandomPlayer(i, player_seeds[i]) for i in range(n_players)]
            shadow_players = [RandomPlayer(i, player_seeds[i]) for i in range(n_players)]

            engine = Engine(
                {
                    "seed": seed,
                    "n_cards": n_cards,
                    "n_players": n_players,
                    "n_rounds": n_rounds,
                    "board_size_y": board_size_y,
                    "fixed_hands": copy.deepcopy(initial_hands),
                },
                engine_players,
            )
            custom_engine = CustomizedEngine()
            custom_engine.reset([row[0] for row in initial_board])

            engine_trace = []
            custom_trace = []
            shadow_hands = copy.deepcopy(initial_hands)

            if engine.board != initial_board or engine.hands != initial_hands:
                raise AssertionError(
                    "Test setup does not reproduce Engine dealing.\n"
                    f"engine_board={engine.board}\n"
                    f"expected_board={initial_board}\n"
                    f"engine_hands={engine.hands}\n"
                    f"expected_hands={initial_hands}"
                )

            for round_idx in range(n_rounds):
                expected_actions = []
                for player_idx, player in enumerate(shadow_players):
                    hand = shadow_hands[player_idx]
                    history = {
                        "board": copy.deepcopy(engine.board),
                        "scores": list(engine.scores),
                        "round": engine.round,
                        "history_matrix": copy.deepcopy(engine.history_matrix),
                        "board_history": copy.deepcopy(engine.board_history),
                        "score_history": copy.deepcopy(engine.score_history),
                    }
                    action = player.action(hand.copy(), history)
                    expected_actions.append(action)
                    hand.remove(action)

                engine_board_before = copy.deepcopy(engine.board)
                custom_rows_before = _custom_rows_snapshot(custom_engine)

                engine.play_round()
                actual_actions = list(engine.history_matrix[-1])

                if actual_actions != expected_actions:
                    raise AssertionError(
                        _format_mismatch(
                            seed,
                            player_seeds,
                            initial_board,
                            initial_hands,
                            engine_trace
                            + [
                                {
                                    "round": round_idx,
                                    "board_before_round": engine_board_before,
                                    "expected_actions": expected_actions,
                                    "actual_actions": actual_actions,
                                }
                            ],
                            custom_trace,
                        )
                    )

                custom_engine.play_round(actual_actions)
                custom_engine.round += 1

                engine_round_trace = {
                    "round": round_idx,
                    "board_before_round": engine_board_before,
                    "actions": actual_actions,
                    "board_after_round": copy.deepcopy(engine.board),
                    "scores_after_round": list(engine.scores),
                }
                custom_round_trace = {
                    "round": round_idx,
                    "rows_before_round": custom_rows_before,
                    "actions": actual_actions,
                    "rows_after_round": _custom_rows_snapshot(custom_engine),
                    "scores_after_round": list(custom_engine.scores),
                }
                engine_trace.append(engine_round_trace)
                custom_trace.append(custom_round_trace)

                if custom_engine.scores != engine.scores:
                    raise AssertionError(
                        _format_mismatch(seed, player_seeds, initial_board, initial_hands, engine_trace, custom_trace)
                    )

                custom_engine.reset_to(
                    {
                        "round": engine.round,
                        "scores": engine.scores,
                        "board": engine.board,
                    }
                )

                if _custom_rows_snapshot(custom_engine) != [
                    (row[-1], len(row), sum(engine.score_mapping[card] for card in row)) for row in engine.board
                ]:
                    raise AssertionError(
                        _format_mismatch(seed, player_seeds, initial_board, initial_hands, engine_trace, custom_trace)
                    )

                engine.round += 1

            if custom_engine.scores != engine.scores:
                raise AssertionError(
                    _format_mismatch(seed, player_seeds, initial_board, initial_hands, engine_trace, custom_trace)
                )


if __name__ == "__main__":
    unittest.main()
