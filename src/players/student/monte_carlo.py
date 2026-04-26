import random
import time

from src.players.student.customized_engine import CustomizedEngine
from src.players.student.customized_engine import N_CARDS
from src.players.student.customized_engine import N_PLAYERS


class MonteCarloPlayer:
    def __init__(self, player_idx, seed: int | None = None):
        self.player_idx = player_idx
        self.rng = random.Random(seed)

    def _infer_unseen_cards(self, hand, history):
        seen = [False] * (N_CARDS + 1)

        for board in history.get("board_history", []):
            for row in board:
                for card in row:
                    seen[card] = True

        for row in history["board"]:
            for card in row:
                seen[card] = True

        for round_actions in history.get("history_matrix", []):
            for card in round_actions:
                seen[card] = True

        for card in hand:
            seen[card] = True

        return [card for card in range(1, N_CARDS + 1) if not seen[card]]

    def _sample_opponent_hands(self, unseen_cards, cards_per_opponent):
        shuffled = unseen_cards[:]
        self.rng.shuffle(shuffled)

        opponent_hands = []
        offset = 0
        for opponent_idx in range(N_PLAYERS):
            if opponent_idx == self.player_idx:
                continue
            next_offset = offset + cards_per_opponent
            opponent_hands.append(shuffled[offset:next_offset])
            offset = next_offset
        return opponent_hands

    def _draw_random_card(self, cards):
        chosen_idx = self.rng.randrange(len(cards))
        return cards.pop(chosen_idx)

    def _final_rank(self, scores):
        my_score = scores[self.player_idx]
        lower = sum(score < my_score for score in scores)
        ties = sum(score == my_score for score in scores) - 1
        return 1.0 + lower + 0.5 * ties

    def _rollout(self, history, own_hand, forced_first_card, unseen_cards):
        engine = CustomizedEngine()
        engine.reset_to(history)

        remaining_cards = len(own_hand)
        opponent_hands = self._sample_opponent_hands(unseen_cards, remaining_cards)
        simulated_hands: list[list[int]] = []
        opponent_hand_idx = 0
        for player_idx in range(N_PLAYERS):
            if player_idx == self.player_idx:
                simulated_hands.append(own_hand[:])
                self.rng.shuffle(simulated_hands[-1])
                card_idx = own_hand.index(forced_first_card)
                simulated_hands[-1][card_idx] = own_hand[0]
                simulated_hands[-1][0] = forced_first_card
            else:
                simulated_hands.append(opponent_hands[opponent_hand_idx])
                opponent_hand_idx += 1

        engine.play_game(zip(*simulated_hands))
        return self._final_rank(engine.scores)

    def action(self, hand, history):
        if len(hand) == 1:
            return hand[0]

        unseen_cards = self._infer_unseen_cards(hand, history)

        deadline = time.perf_counter() + 0.9
        totals = {card: 0.0 for card in hand}
        counts = {card: 0 for card in hand}
        candidates = list(hand)
        candidate_idx = 0

        while time.perf_counter() < deadline or all(count == 0 for count in counts.values()):
            card = candidates[candidate_idx]
            totals[card] += self._rollout(history, hand, card, unseen_cards)
            counts[card] += 1
            candidate_idx = (candidate_idx + 1) % len(candidates)

        best_card = min(
            candidates,
            key=lambda card: (totals[card] / counts[card], counts[card] == 0, card),
        )
        return best_card
