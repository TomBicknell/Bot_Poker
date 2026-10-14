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
import random

from pokerbot import all_in, call, check, fold, raise_to, run
from pokerbot.cards import describe_hand, hand_strength, is_pair, rank

BOT_NAME = "LARP BOT"   # change this to your team's name!

SHORT_STACK = 300         # below this many chips we play push/fold


# ----------------------------------------------------------------------
# Per-hand memory: how many times have WE raised in this hand?
# Used so we never keep betting into someone who keeps raising us back.

_memory = {"hand": None, "raises": 0}


def _reset_if_new_hand(state):
    key = tuple(state.my_cards)
    if _memory["hand"] != key:
        _memory["hand"] = key
        _memory["raises"] = 0


def my_raises(state):
    _reset_if_new_hand(state)
    return _memory["raises"]


def note_raise(state):
    _reset_if_new_hand(state)
    _memory["raises"] += 1


# ----------------------------------------------------------------------
# Helpers

def preflop_score(cards):
    """Rough 0-1 score for a starting hand."""
    r1, r2 = sorted((rank(c) for c in cards), reverse=True)
    suited = cards[0][-1] == cards[1][-1]

    if is_pair(cards):
        return 0.45 + r1 * 0.035

    score = (r1 - 2) / 12 * 0.6 + (r2 - 2) / 12 * 0.3
    gap = r1 - r2
    if suited:
        score += 0.05
    if gap <= 2:
        score += 0.04
    elif gap >= 5:
        score -= 0.05
    if r1 < 10 and not suited:
        score -= 0.04
    return max(0.0, min(1.0, score))


def active_opponents(state):
    """Opponents still in the hand (falls back to all opponents)."""
    try:
        live = [o for o in state.opponents
                if str(getattr(o, "status", "")).lower() not in ("folded", "fold", "out")]
        return max(1, len(live))
    except Exception:
        return max(1, len(state.opponents))


def adjusted_equity(raw, n_opp):
    """Shrink hand strength a little for each extra opponent."""
    return raw ** (1 + 0.2 * (n_opp - 1))


def price_to_call(state):
    """Fraction of the final pot we must put in to call (0 if free)."""
    if state.to_call <= 0:
        return 0.0
    p = getattr(state, "pot_odds", None)
    if isinstance(p, (int, float)) and 0 <= p <= 1:
        return float(p)
    return state.to_call / (state.pot + state.to_call)


def commitment(state):
    """Share of our remaining chips a call would cost (0-1)."""
    return state.to_call / max(1, state.max_raise)


def bet_size(state, fraction):
    """Raise to roughly `fraction` of the pot, clamped to legal limits."""
    target = state.to_call + int(state.pot * fraction)
    amount = max(state.min_raise, min(target, state.max_raise))
    note_raise(state)
    return raise_to(amount)


def shove(state):
    note_raise(state)
    return all_in()


def check_or_fold(state):
    return check() if state.can_check else fold()


def call_or_check(state):
    return check() if state.can_check else call()


# ----------------------------------------------------------------------
# Preflop

def decide_preflop(state):
    s = preflop_score(state.my_cards)
    c = commitment(state)
    at_blinds = c <= 0.025        # nobody has raised: just the blinds to pay
    cheap = c <= 0.06             # a limp or a small raise
    short = state.max_raise < SHORT_STACK

    # Short stack: push or fold. Don't bleed away to the blinds.
    if short:
        if s >= 0.80 and state.can_raise:
            return shove(state)
        if at_blinds and s >= 0.58 and state.can_raise:
            return shove(state)
        if s >= 0.90:
            return call_or_check(state)
        return check_or_fold(state)

    # Premium hands (QQ+, AK, AQ suited...).
    if s >= 0.85:
        if c >= 0.30:
            # Facing a huge raise / shove: only the very best hands call.
            return call() if s >= 0.90 else fold()
        if state.can_raise and my_raises(state) < 2:
            return bet_size(state, 0.80)
        return call_or_check(state)

    # Strong hands: raise unopened pots, call small raises, fold to big ones.
    if s >= 0.62:
        if at_blinds and state.can_raise:
            return bet_size(state, 0.65)
        if c < 0.08:
            return call_or_check(state)
        if s >= 0.78 and c < 0.18:
            return call_or_check(state)
        return check_or_fold(state)

    # Playable hands: steal sometimes, otherwise see a cheap flop.
    if s >= 0.48:
        if at_blinds and state.can_raise and random.random() < 0.40:
            return bet_size(state, 0.55)
        if cheap:
            return call_or_check(state)
        return check_or_fold(state)

    # Weak hands: take free checks, rare bluff-steal, otherwise fold.
    if at_blinds and state.can_raise and s >= 0.35 and random.random() < 0.06:
        return bet_size(state, 0.55)
    return check_or_fold(state)


# ----------------------------------------------------------------------
# Postflop

def decide_postflop(state):
    n_opp = active_opponents(state)
    s = adjusted_equity(hand_strength(state.my_cards, state.board), n_opp)
    facing_bet = state.to_call > 0
    c = commitment(state)
    price = price_to_call(state)
    short = state.max_raise < SHORT_STACK

    # How much of the total chips are already in the middle (0 - 1).
    invest = state.pot / float(state.pot + max(1, state.max_raise))

    # Opponents who bet big usually have it: discount our strength.
    # (hand_strength is measured against random hands, not against bettors.)
    s_eff = s
    if facing_bet:
        bet_ratio = state.to_call / float(max(1, state.pot - state.to_call))
        s_eff -= 0.12 * min(2.0, bet_ratio)
        if my_raises(state) > 0:
            s_eff -= 0.10          # we bet, they raised back: respect it

    # The bar for betting for value rises as the pot gets big.
    value_bar = 0.78 + 0.12 * invest

    # --- Monster: get it in ---
    if s_eff >= 0.93 and state.can_raise:
        return shove(state)

    # --- Facing a bet or raise ---
    if facing_bet:
        # Short stack: call if clearly ahead of the price, else fold.
        needed = price + 0.05 + 0.25 * c
        if s_eff >= needed:
            return call()
        return fold()

    # --- Nobody has bet (we can check) ---
    # Very strong: bet for value (but never raise ourselves into a big pot
    # with a merely good hand).
    if s >= value_bar and state.can_raise and my_raises(state) < 3:
        return bet_size(state, 0.70)

    # Good hand: small bet for value, unless the pot is already big.
    if s >= 0.58 and state.can_raise and invest < 0.35 and my_raises(state) < 2:
        return bet_size(state, 0.45)

    # Occasional small probe in small, heads-up-ish pots.
    if (state.can_raise and n_opp <= 2 and 0.30 <= s < 0.58
            and invest < 0.15 and not short and random.random() < 0.20):
        return bet_size(state, 0.35)

    return check()


def decide(state):
    try:
        if state.street == "preflop":
            return decide_preflop(state)
        return decide_postflop(state)
    except Exception:
        return check() if state.can_check else fold()


# ----------------------------------------------------------------------
# You don't need to change anything below this line.
if __name__ == "__main__":
    run(decide, name=BOT_NAME)