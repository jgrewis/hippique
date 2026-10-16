"""Method 2: conditional (multinomial) logit, two stages as in Benter (1994).

Stage 1 learns the weight of each fundamental criterion from past winners:
    P(i wins) = exp(beta . x_i) / sum_j exp(beta . x_j)
Stage 2 blends the stage-1 probability with the market (morning odds):
    P(i wins) ~ exp(a * log p_fund_i + b * log p_market_i)
"""
import json
from dataclasses import dataclass, field

import numpy as np
from scipy.optimize import minimize

from predict.features import FEATURES, Race

L2 = 1.0
MIN_RUNNERS = 4


def _fit(blocks: list, winners: list, l2: float = L2) -> np.ndarray:
    """Maximum likelihood with L2 penalty. blocks: list of (n_i x d) arrays."""
    X = np.vstack(blocks)
    sizes = np.array([len(b) for b in blocks])
    starts = np.concatenate(([0], np.cumsum(sizes)[:-1]))
    win_rows = starts + np.array(winners)
    d = X.shape[1]

    def objective(beta):
        u = X @ beta
        u_max = np.maximum.reduceat(u, starts)
        e = np.exp(u - np.repeat(u_max, sizes))
        denom = np.add.reduceat(e, starts)
        log_lik = (u[win_rows] - u_max - np.log(denom)).sum()
        probs = e / np.repeat(denom, sizes)
        expected = np.add.reduceat(probs[:, None] * X, starts)
        grad = -(X[win_rows] - expected).sum(axis=0) + l2 * beta
        return -log_lik + 0.5 * l2 * beta @ beta, grad

    result = minimize(objective, np.zeros(d), jac=True, method="L-BFGS-B")
    return result.x


def softmax(u: np.ndarray) -> np.ndarray:
    e = np.exp(u - u.max())
    return e / e.sum()


@dataclass
class LogitModel:
    beta: np.ndarray
    blend: np.ndarray = field(default_factory=lambda: np.array([1.0, 0.0]))  # (a, b)
    features: tuple = FEATURES
    n_races: int = 0

    def fundamental(self, race: Race) -> np.ndarray:
        return softmax(race.standardized(self.features) @ self.beta)

    def predict(self, race: Race) -> np.ndarray:
        p_fund = self.fundamental(race)
        if np.isnan(race.market).any():
            return p_fund
        u = self.blend[0] * np.log(p_fund) + self.blend[1] * np.log(race.market)
        return softmax(u)

    def to_json(self) -> str:
        return json.dumps({
            "features": list(self.features),
            "beta": [round(float(b), 6) for b in self.beta],
            "blend": [round(float(b), 6) for b in self.blend],
            "n_races": self.n_races,
        }, indent=2)

    @classmethod
    def from_json(cls, text: str) -> "LogitModel":
        data = json.loads(text)
        return cls(np.array(data["beta"]), np.array(data["blend"]), tuple(data["features"]), data.get("n_races", 0))


def trainable(races: list) -> list:
    return [r for r in races if r.winner_index is not None and len(r.numeros) >= MIN_RUNNERS]


def train(races: list) -> LogitModel:
    races = trainable(races)
    if not races:
        raise ValueError("Aucune course exploitable pour l'entraînement")
    beta = _fit([r.standardized() for r in races], [r.winner_index for r in races])
    model = LogitModel(beta=beta, n_races=len(races))
    with_market = [r for r in races if not np.isnan(r.market).any()]
    if with_market:
        blocks = [np.column_stack([np.log(model.fundamental(r)), np.log(r.market)]) for r in with_market]
        model.blend = _fit(blocks, [r.winner_index for r in with_market], l2=0.01)
    return model
