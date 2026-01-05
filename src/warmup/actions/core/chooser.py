from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Set

State = str


@dataclass
class ChooseState:
    history: List[State] = field(default_factory=list)
    cooldowns: Dict[State, int] = field(default_factory=dict)  # state -> steps remaining
    blocked: Set[State] = field(default_factory=set)

    def tick(self) -> None:
        # decrease cooldowns
        to_del = []
        for s, v in self.cooldowns.items():
            nv = v - 1
            if nv <= 0:
                to_del.append(s)
            else:
                self.cooldowns[s] = nv
        for s in to_del:
            del self.cooldowns[s]


def weighted_choice(rng: random.Random, items: List[Tuple[State, float]]) -> State:
    total = sum(w for _, w in items)
    if total <= 0:
        return items[-1][0]
    pick = rng.uniform(0, total)
    upto = 0.0
    for s, w in items:
        upto += w
        if upto >= pick:
            return s
    return items[-1][0]


def decay_repeats(items: List[Tuple[State, float]], history: List[State]) -> List[Tuple[State, float]]:
    if not history:
        return items
    last = history[-1] if len(history) >= 1 else None
    last2 = history[-2] if len(history) >= 2 else None
    last3 = history[-3] if len(history) >= 3 else None

    out: List[Tuple[State, float]] = []
    for s, w in items:
        ww = w
        if s == last:
            ww *= 0.25
        elif s == last2:
            ww *= 0.45
        elif s == last3:
            ww *= 0.65
        out.append((s, max(0.01, ww)))
    return out


def apply_runtime_rules(
    items: List[Tuple[State, float]],
    st: ChooseState,
    time_left_sec: float,
    action_costs: Dict[State, int],
) -> List[Tuple[State, float]]:
    """
    - blocked: remove
    - cooldowns: remove
    - time budget: avoid expensive actions near end
    """
    filtered: List[Tuple[State, float]] = []
    for s, w in items:
        if s in st.blocked:
            continue
        if s in st.cooldowns:
            continue
        cost = action_costs.get(s, 60)
        # если времени мало — режем тяжелые действия
        if time_left_sec < 120 and cost > 120:
            continue
        filtered.append((s, w))

    return filtered or items


def novelty_bonus(items: List[Tuple[State, float]], history: List[State]) -> List[Tuple[State, float]]:
    """
    Чем дольше state не встречался — тем небольшой бонус.
    """
    if not history:
        return items
    last_seen: Dict[State, int] = {}
    for i, s in enumerate(history):
        last_seen[s] = i

    out: List[Tuple[State, float]] = []
    n = len(history)
    for s, w in items:
        if s not in last_seen:
            out.append((s, w * 1.15))
        else:
            age = n - 1 - last_seen[s]
            boost = 1.0 + min(0.20, age * 0.03)
            out.append((s, w * boost))
    return out


def jitter_weights(rng: random.Random, items: List[Tuple[State, float]], pct: float = 0.08) -> List[Tuple[State, float]]:
    out: List[Tuple[State, float]] = []
    for s, w in items:
        delta = w * pct
        out.append((s, max(0.01, w + rng.uniform(-delta, delta))))
    return out
