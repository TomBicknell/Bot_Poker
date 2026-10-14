"""
Larp Bot MAX v2 - Short-Handed Adaptive & Monte Carlo Engine
"""
from pokerbot import all_in, call, check, fold, raise_to, run
from pokerbot.cards import describe_hand, hand_strength, is_pair, rank
import random

BOT_NAME = "Larp Bot MAX v2"

ALL_SUITS = ['s', 'h', 'd', 'c']

def get_full_deck():
    return [f"{r_str}{s}" for r_str in ["2","3","4","5","6","7","8","9","T","J","Q","K","A"] for s in ALL_SUITS]

def simulate_equity(my_cards, board, num_opponents=1, iterations=350):
    """Calculates win probability via Monte Carlo rollouts."""
    if not board and len(my_cards) == 2:
        r1, r2 = sorted((rank(c) for c in my_cards), reverse=True)
        suited = my_cards[0][-1] == my_cards[1][-1]
        pair = is_pair(my_cards)
        
        if pair:
            base_eq = 0.52 + (r1 / 14.0) * 0.35
        elif r1 >= 13 and r2 >= 11:
            base_eq = 0.62 if suited else 0.55
        elif suited:
            base_eq = 0.38 + ((r1 + r2) / 28.0) * 0.25
        else:
            base_eq = 0.28 + ((r1 + r2) / 28.0) * 0.22
            
        # Adapt preflop equity requirement based on active opponents
        return max(0.12, base_eq / (1.0 + 0.20 * (num_opponents - 1)))

    known_cards = set(my_cards + board)
    deck = [c for c in get_full_deck() if c not in known_cards]
    cards_needed = 5 - len(board)
    wins = 0

    for _ in range(iterations):
        random.shuffle(deck)
        sim_board = board + deck[:cards_needed]
        my_score = hand_strength(my_cards, sim_board)
        
        deck_idx = cards_needed
        opp_best = 0.0
        for _ in range(num_opponents):
            opp_cards = deck[deck_idx:deck_idx+2]
            deck_idx += 2
            if len(opp_cards) == 2:
                opp_score = hand_strength(opp_cards, sim_board)
                if opp_score > opp_best:
                    opp_best = opp_score
                    
        if my_score > opp_best:
            wins += 1.0
        elif my_score == opp_best:
            wins += 0.5

    return wins / iterations

def active_opponents(state):
    try:
        live = [o for o in state.opponents 
                if str(getattr(o, "status", "")).lower() not in ("folded", "fold", "out")]
        return max(1, len(live))
    except Exception:
        return max(1, len(state.opponents))

def bet_size(state, fraction):
    target = state.to_call + int(state.pot * fraction)
    amount = max(state.min_raise, min(target, state.max_raise))
    return raise_to(amount)

def decide(state):
    try:
        n_opp = active_opponents(state)
        equity = simulate_equity(state.my_cards, state.board, num_opponents=n_opp)

        pot_after_call = state.pot + state.to_call
        pot_odds = state.to_call / max(1, pot_after_call)

        # Dynamic Threshold Adjustments: Be MORE aggressive with fewer players left
        # When 1-on-1 (heads up), thresholds lower so we don't get bullied.
        aggro_offset = 0.08 if n_opp <= 2 else (0.04 if n_opp == 3 else 0.0)

        # -------------------------------------------------------------
        # 1. PREFLOP STRATEGY
        # -------------------------------------------------------------
        if state.street == "preflop":
            r1, r2 = sorted((rank(c) for c in state.my_cards), reverse=True)
            is_premium = (is_pair(state.my_cards) and r1 >= 11) or (r1 == 14 and r2 >= 12) # TT+, AQ+

            # Stack Protection vs Wild Preflop Shoves
            if state.to_call > 180 and not is_premium:
                return fold()

            # Raise premium / strong hands
            if equity >= (0.60 - aggro_offset):
                if state.can_raise:
                    return bet_size(state, 0.55)
                return call()

            # Limp / Call small bets preflop
            if equity >= (0.38 - aggro_offset) and state.to_call <= 70:
                return call() if state.to_call > 0 else (check() if state.can_check else fold())

            return check() if state.can_check else fold()

        # -------------------------------------------------------------
        # 2. POSTFLOP STRATEGY
        # -------------------------------------------------------------
        
        # MONSTER / NUTS (Equity >= 80%): Massive bet or shove
        if equity >= (0.80 - aggro_offset):
            if state.can_raise:
                if equity >= 0.90:
                    return all_in()
                return bet_size(state, 0.75)
            return call()

        # STRONG HAND (Equity >= 58%): Value raise & standard bet
        if equity >= (0.58 - aggro_offset):
            if state.can_raise:
                return bet_size(state, 0.50)
            if pot_odds <= 0.48:
                return call()
            return fold()

        # MEDIUM HAND / FLOP DRAWS (Equity >= 35%)
        if equity >= (0.35 - aggro_offset):
            if state.can_check:
                # Continuation bet when checked to in short-handed pots (10% freq)
                if state.can_raise and n_opp <= 2 and random.random() < 0.12:
                    return bet_size(state, 0.40)
                return check()
            
            # Direct Mathematical EV Call
            if equity > (pot_odds + 0.03):
                return call()
            return fold()

        # WEAK HAND: Free check or fold
        if state.can_check:
            return check()

        return fold()

    except Exception:
        return check() if state.can_check else fold()

if __name__ == "__main__":
    run(decide, name=BOT_NAME)