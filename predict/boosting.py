"""Method 3: gradient boosting (scikit-learn), retrained at each run.

The classifier learns P(win) per runner from the same criteria as the logit
(z-scored within the race) plus the market probability, and can capture
interactions the linear logit cannot. Its scores are then normalised within
each race so that they sum to 1.

The model is never written to disk: scikit-learn models are saved with
pickle, which executes code when loaded. Retraining takes a few seconds.
"""
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier

from predict.features import FEATURES, Race
from predict.logit_model import trainable

MIN_RACES = 300


def _matrix(race: Race) -> np.ndarray:
    market = np.log(race.market) if not np.isnan(race.market).any() else np.full(len(race.numeros), np.nan)
    market_rel = market - np.nanmean(market) if not np.isnan(market).all() else market
    return np.column_stack([race.standardized(FEATURES, keep_missing=True), market_rel])


class BoostingModel:
    def __init__(self, classifier, n_races: int):
        self.classifier = classifier
        self.n_races = n_races

    def predict(self, race: Race) -> np.ndarray:
        scores = self.classifier.predict_proba(_matrix(race))[:, 1]
        scores = np.clip(scores, 1e-6, None)
        return scores / scores.sum()


def train(races: list):
    """Return a BoostingModel, or None when history is too short."""
    races = trainable(races)
    if len(races) < MIN_RACES:
        return None
    X = np.vstack([_matrix(r) for r in races])
    y = np.concatenate([[int(r.arrivee.get(n) == 1) for n in r.numeros] for r in races])
    classifier = HistGradientBoostingClassifier(
        max_iter=200, learning_rate=0.05, max_leaf_nodes=15, min_samples_leaf=40,
        l2_regularization=1.0, random_state=0,
    )
    classifier.fit(X, y)
    return BoostingModel(classifier, len(races))
