import random

class RandomPlayer():
    def __init__(self, player_idx, seed: int | None = None):
        self.player_idx = player_idx
        self.rng = random.Random(seed)
    
    def action(self, hand, history):
        return self.rng.choice(hand)
