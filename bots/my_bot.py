"""
My poker bot!

This is the only file you need to edit. Change decide() to change how your
bot plays.

Run it (the organiser will tell you the host and port):
    python3 my_bot.py --host 192.168.1.20 --port 8000

Practise against 3 copies of itself on your own computer (start the server
first: see "Practising on your own computer" in README.md):
    python3 my_bot.py --port 8000 --count 4 --quiet

On Windows, type `python` (or `py`) instead of `python3`.
"""
from pokerbot import all_in, call, check, fold, raise_to, run
from pokerbot.cards import describe_hand, hand_strength, is_pair, rank
import random

BOT_NAME = "Larp Bot"   # change this to your team's name!

def preflop_score(cards):
# Rough 0-1 score for a starting hand
    r1, r2 = sorted((rank(c) for c in cards), reverse=True)
    suited  = cards[0][-1] == cards[1][-1]

    if is_pair(cards):
        return 0.45 + r1 * 0.035

    score = (r1 - 2) / 12 * 0.6 + (r2 - 2) / 12 * 0.3
    if suited:
        score += 0.05
    if r1 - r2 <= 2:
        score += 0.04
    if score > 1.0:
        score = 1.0
    return score

def bet_size(state, fraction):
# Raise to roughly `fraction` of the pot, clamped to legal limits."""
    target = state.to_call + int(state.pot * fraction)
    amount = max(state.min_raise, min(target, state.max_raise))
    return raise_to(amount)


def active_opponents(state):
# Opponents still in the hand (falls back to all opponents).
    try:
        live = [o for o in state.opponents
                if str(getattr(o, "status", "")).lower() not in ("folded", "fold", "out")]
        return max(1, len(live))
    except Exception:
        return max(1, len(state.opponents))

def decide(state):
    """
    Called every time it's your turn. Look at `state`, then return ONE of:

        fold()          give up this hand
        check()         pass without betting (only if state.can_check)
        call()          match the current bet (costs state.to_call chips)
        raise_to(100)   make your total bet this round 100 chips
        all_in()        bet everything

    Handy things in `state`:
        state.my_cards     your two cards, e.g. ["As", "Kd"]
        state.board        the shared cards on the table
        state.street       "preflop", "flop", "turn" or "river"
        state.pot          chips in the middle
        state.to_call      chips you need to call (0 means you can check)
        state.can_check    True if checking is allowed
        state.can_raise    True if raising is allowed
        state.min_raise    smallest amount you can raise_to()
        state.max_raise    largest amount you can raise_to() (all-in)
        state.my_stack     chips you have left
        state.opponents    the other players (name, stack, bet, status)
        state.history      everything that has happened this hand
        state.pot_odds     how much calling costs compared to the pot

    And from pokerbot.cards:
        hand_strength(my_cards, board)   a score from 0 (bad) to 1 (amazing)
        describe_hand(my_cards, board)   e.g. "Two pair"
        rank("As") -> 14,  is_pair(["Kh", "Kd"]) -> True

    Don't worry about making an illegal move: it gets fixed for you, and a
    note is printed so you can see what happened.
    """
    try:
        n_opp = active_opponents(state)

        if state.street == "preflop":
            s = preflop_score(state.my_cards)
            raise_threshold, call_threshold = 0.72, 0.50
        else:
            s = hand_strength(state.my_cards, state.board)
            s -= 0.03 * (n_opp - 1)
            raise_threshold, call_threshold = 0.70, 0.40

        if s >= 0.92 and state.can_raise:
            return all_in()

        if s >= raise_threshold and state.can_raise:
            return bet_size(state, 0.75 if s >= 0.85 else 0.5)

        if state.can_check:
            if state.can_raise and s < 0.30 and random.random() < 0.08:
                return bet_size(state, 0.5)
            return check()

        if s >= call_threshold and s > state.pot_odds + 0.10:
            return call()
        if state.pot_odds <= 0.15 and s >= 0.25:
            return call()

        return fold()

    except Exception:
        return check() if state.can_check else fold()


# ----------------------------------------------------------------------
# You don't need to change anything below this line.
if __name__ == "__main__":
    run(decide, name=BOT_NAME)
