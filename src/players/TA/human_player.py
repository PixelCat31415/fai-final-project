class HumanPlayer():
    def __init__(self, player_idx):
        self.player_idx = player_idx
    
    def _get_card_score(self, card):
        if card % 55 == 0: return 7
        if card % 11 == 0: return 5
        if card % 10 == 0: return 3
        if card % 5 == 0: return 2
        return 1

    def action(self, hand, history):
        print("\n" + "="*30)
        print("YOUR TURN")
        print("Current Board:")
        for i, row in enumerate(history["board"]):
            row_score = sum(self._get_card_score(c) for c in row)
            print(f"Row {i}: {row} ({row_score} pts)")
        
        print("\nYour Hand:", hand)
        
        while True:
            try:
                choice_str = input("Choose a card to play: ")
                choice = int(choice_str)
                if choice in hand:
                    return choice
                else:
                    print(f"Card {choice} is not in your hand. Try again.")
            except ValueError:
                print("Invalid input. Please enter a number.")
