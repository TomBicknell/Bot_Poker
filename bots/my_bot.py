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
    try:
        n_opp = active_opponents(state)

        if state.street == "preflop":
            s = preflop_score(state.my_cards)
            raise_threshold, call_threshold = 0.65, 0.38
        else:
            s = hand_strength(state.my_cards, state.board)

            # Slightly account for having more opponents
            s -= 0.015 * (n_opp - 1)

            raise_threshold, call_threshold = 0.62, 0.32

        # Very strong hand -> go all in
        if s >= 0.88 and state.can_raise:
            return all_in()

        # Strong hand -> raise aggressively
        if s >= raise_threshold and state.can_raise:
            if s >= 0.80:
                return bet_size(state, 0.85)
            else:
                return bet_size(state, 0.60)

        # If nobody has bet, usually check.
        # Occasionally bluff with a weak hand.
        if state.can_check:
            if state.can_raise and s < 0.30 and random.random() < 0.05:
                return bet_size(state, 0.40)

            return check()

        # We have to call or fold
        if s >= call_threshold:
            # Call if the price is reasonable,
            # or if we have a genuinely decent hand.
            if state.pot_odds <= 0.25 or s >= 0.55:
                return call()

        return fold()

    except Exception:
        return check() if state.can_check else fold()

# ----------------------------------------------------------------------
# You don't need to change anything below this line.
if __name__ == "__main__":
    run(decide, name=BOT_NAME)
