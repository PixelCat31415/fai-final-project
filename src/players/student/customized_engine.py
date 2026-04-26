from dataclasses import dataclass
from collections.abc import Iterable, Sequence

# Mapping from card number to score
def _default_score_mapping(n_cards: int):
    mapping = [0] * (n_cards + 1)
    for i in range(1, n_cards + 1):
        if i % 55 == 0:
            mapping[i] = 7
        elif i % 11 == 0:
            mapping[i] = 5
        elif i % 10 == 0:
            mapping[i] = 3
        elif i % 5 == 0:
            mapping[i] = 2
        else:
            mapping[i] = 1
    return mapping

# constants
N_CARDS = 104
N_PLAYERS = 4
N_ROUNDS = 10
BOARD_SIZE_X = 5 # capacity before taking
BOARD_SIZE_Y = 4
SCORE_MAPPING = _default_score_mapping(N_CARDS)

# typing
@dataclass
class BoardRow:
    tail: int
    cnt: int
    score: int

class CustomizedEngine:
    
    def __init__(self):
        self.round: int = -1
        self.scores: list[int] = []
        self.rows: list[BoardRow] = []

    def reset(self, init_cards: list[int]):
        self.round = 0
        self.scores = [0] * N_PLAYERS
        self.rows = []
        for card in init_cards:
            self.rows.append(BoardRow(card, 1, SCORE_MAPPING[card]))
        
    def reset_to(self, history: dict):
        self.round = history["round"]
        self.scores = history["scores"][:]
        self.rows = [BoardRow(row[-1], len(row), sum(SCORE_MAPPING[card] for card in row)) for row in history["board"]]
    
    # Places a card on the board and returns the score incurred.
    def process_card_placement(self, card, player_idx):
        # Find row
        best_row_idx = -1
        max_val_under_card = -1
        for r_idx, row in enumerate(self.rows):
            if row.tail < card and row.tail > max_val_under_card:
                max_val_under_card = row.tail
                best_row_idx = r_idx
        
        score_incurred = 0
        
        # Case 1: Fits in a row
        if best_row_idx != -1:
            best_row = self.rows[best_row_idx]
            if best_row.cnt >= BOARD_SIZE_X:
                score_incurred = best_row.score
                best_row.tail = card
                best_row.cnt = 1
                best_row.score = SCORE_MAPPING[card]
            else:
                best_row.tail = card
                best_row.cnt += 1
                best_row.score += SCORE_MAPPING[card]
        # Case 2: Lower than all rows (Low Card Rule)
        else:
            # Choose row by (lowest score, shortest len, lowest index)
            chosen_r_idx = min(range(BOARD_SIZE_Y), key=lambda i: (self.rows[i].score, self.rows[i].cnt, i))
            score_incurred = self.rows[chosen_r_idx].score
            chosen_row = self.rows[chosen_r_idx]
            chosen_row.tail = card
            chosen_row.cnt = 1
            chosen_row.score = SCORE_MAPPING[card]
        
        self.scores[player_idx] += score_incurred
        return score_incurred

    def play_round(self, played_cards: Sequence[int]):
        current_played_cards = list(enumerate(played_cards))
        current_played_cards.sort(key=lambda x: x[1])
        for p_idx, card in current_played_cards:
            self.process_card_placement(card, p_idx)

    def play_game(self, played_cards_rounds: Iterable[Sequence[int]]):
        assert self.round >= 0
        for played_cards in played_cards_rounds:
            self.play_round(played_cards)
            self.round += 1
        return self.scores
