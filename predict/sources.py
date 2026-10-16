"""Every ranking available for a race, as one uniform list.

House methods (computed here), the PMU forecast, each press selection and
the bettors (morning odds favourite, most-played horses) all become a
`SourceRanking`, so that display, consensus and reliability share one code path.
"""
from dataclasses import dataclass, field

import numpy as np

from predict import consensus, elo, form_score
from predict.features import Race

FAMILY_LABELS = {
    "maison": "Méthodes maison",
    "pmu": "PMU",
    "synthese": "Synthèse de la presse",
    "presse": "Presse et experts",
    "parieurs": "Parieurs",
}
FAMILY_ORDER = tuple(FAMILY_LABELS)
HOUSE_LABELS = {
    "consensus": "Consensus de toutes les sources",
    "logit": "Modèle logit",
    "boosting": "Gradient boosting",
    "elo": "Classement Elo",
    "forme": "Score de forme",
}
SYNTHESIS_ORDER = ("synthese:FAVORIS", "synthese:OUTSIDERS", "synthese:DELAISSES")


@dataclass
class SourceRanking:
    key: str
    label: str
    family: str
    numeros: list                                # best first
    probas: dict = field(default_factory=dict)   # numero -> win probability, if the source gives one
    scores: dict = field(default_factory=dict)   # numero -> score, if the source gives one


def _parse(numeros: str, runners: set) -> list:
    seen, out = set(), []
    for token in numeros.split("-"):
        if token.isdigit() and int(token) in runners and int(token) not in seen:
            seen.add(int(token))
            out.append(int(token))
    return out


def external_rankings(runners: list, selection_rows: list, only_before_start=False) -> list:
    """PMU, press, press synthesis and most-played rankings for one race."""
    allowed = set(runners)
    out, synthesis = [], {}
    for row in selection_rows:
        if only_before_start and not row["avant_depart"]:
            continue
        if row["famille"] == "synthese":
            synthesis[row["source"]] = _parse(row["numeros"], allowed)
        elif row["famille"] in ("pmu", "presse", "parieurs"):
            numeros = _parse(row["numeros"], allowed)
            if numeros:
                out.append(SourceRanking(row["source"], row["libelle"], row["famille"], numeros))
    combined = [n for key in SYNTHESIS_ORDER for n in synthesis.get(key, [])]
    if combined:
        out.append(SourceRanking("synthese", "Synthèse de la presse", "synthese", combined))
    return out


def market_ranking(market: dict):
    """Favourite first, from morning-odds probabilities {numero: p}."""
    if not market:
        return None
    ordered = sorted(market, key=lambda n: (-market[n], n))
    return SourceRanking("favori", "Favoris des cotes", "parieurs", ordered, probas=dict(market))


def _from_values(key, family, runners, values, probas=None, scores=None):
    order = [runners[i] for i in np.argsort(-np.asarray(values), kind="stable")]
    return SourceRanking(
        key, HOUSE_LABELS[key], family, order,
        probas=dict(zip(runners, map(float, probas))) if probas is not None else {},
        scores=dict(zip(runners, map(float, scores))) if scores is not None else {},
    )


def house_rankings(race: Race, logit_model=None, boost_model=None) -> list:
    """Form score, Elo, logit and boosting (consensus is added by `with_consensus`)."""
    runners = race.numeros
    out = []
    form = form_score.scores(race)
    out.append(_from_values("forme", "maison", runners, form, scores=form))
    elo_scores = [elo.combined_score(h, d) for h, d in zip(race.raw["elo_cheval"], race.raw["elo_driver"])]
    out.append(_from_values("elo", "maison", runners, elo_scores, probas=elo.win_probabilities(elo_scores), scores=elo_scores))
    if logit_model is not None:
        p = logit_model.predict(race)
        out.append(_from_values("logit", "maison", runners, p, probas=p))
    if boost_model is not None:
        p = boost_model.predict(race)
        out.append(_from_values("boosting", "maison", runners, p, probas=p))
    return out


def with_consensus(runners: list, rankings: list) -> list:
    """Append the consensus ranking computed from all the other ones."""
    by_family = {}
    for r in rankings:
        if r.family in consensus.FAMILIES:
            by_family.setdefault(r.family, []).append(r.numeros)
    points = consensus.scores(runners, by_family)
    order = consensus.ranking(runners, by_family)
    return rankings + [SourceRanking("consensus", HOUSE_LABELS["consensus"], "maison", order, scores=points)]


def market_probs(race: Race) -> dict:
    return {} if np.isnan(race.market).any() else dict(zip(race.numeros, map(float, race.market)))


def all_rankings(race: Race, logit_model, boost_model, selection_rows: list, only_before_start=False) -> list:
    rankings = house_rankings(race, logit_model, boost_model)
    favourite = market_ranking(market_probs(race))
    if favourite:
        rankings.append(favourite)
    rankings += external_rankings(race.numeros, selection_rows, only_before_start)
    return with_consensus(race.numeros, rankings)
