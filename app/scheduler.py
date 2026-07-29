from datetime import datetime, timezone
from fsrs import Card, Rating, Scheduler


def _now(value=None):
    return value or datetime.now(timezone.utc)


def new_state(now=None) -> dict:
    card = Card()
    card.due = _now(now)
    return card.to_dict()


def review(state: dict, rating: int, now=None, retention: float = 0.9) -> dict:
    card = Card.from_dict(state)
    updated, _ = Scheduler(desired_retention=retention).review_card(
        card, Rating(rating), _now(now)
    )
    return updated.to_dict()


def retrievability(state: dict, now=None, retention: float = 0.9) -> float:
    try:
        return float(Scheduler(desired_retention=retention).get_card_retrievability(
            Card.from_dict(state), _now(now)
        ))
    except (TypeError, ValueError):
        return 0.0
