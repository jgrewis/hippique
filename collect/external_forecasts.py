"""Third-party rankings (PMU forecast, press, most-played bets) -> `selections` rows.

Only the source name and the ranked runner numbers are kept. Comments
written by journalists or by the PMU are deliberately dropped: they are
copyrighted texts and the site is public.
"""
import re
import unicodedata

PRESS_TOP = 8           # runners kept per press selection
PLAYED_TOP = 8          # runners kept in the "most played" single-bet ranking
PLAYED_COMBOS = 3       # most-played combinations kept per exotic bet
COMBO_BETS = {"TIERCE": "Tiercé", "QUARTE_PLUS": "Quarté+", "QUINTE_PLUS": "Quinté+"}
SYNTHESES = {"FAVORIS": "Favoris", "OUTSIDERS": "Outsiders", "DELAISSES": "Délaissés"}
MAX_LABEL = 60


def _slug(text: str) -> str:
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-") or "inconnu"


def _numbers(values) -> str:
    return "-".join(str(int(v)) for v in values)


def _row(id_course, source, famille, libelle, numbers, avant_depart, now):
    return {
        "id_course": id_course,
        "source": source,
        "famille": famille,
        "libelle": libelle[:MAX_LABEL],
        "numeros": numbers,
        "avant_depart": int(avant_depart),
        "collected_at": now,
    }


def pmu_rows(id_course: str, raw, avant_depart: bool, now: str) -> list:
    selection = sorted((raw or {}).get("selection", []), key=lambda s: s.get("rang", 99))
    numbers = [s["num_partant"] for s in selection if s.get("num_partant")]
    if not numbers:
        return []
    return [_row(id_course, "pmu", "pmu", "Pronostic PMU", _numbers(numbers), avant_depart, now)]


def press_rows(id_course: str, raw, avant_depart: bool, now: str) -> list:
    rows = {}
    for avis in (raw or {}).get("avis", []):
        numbers = [p["numPmu"] for p in avis.get("pronostics", []) if p.get("numPmu")][:PRESS_TOP]
        societe = (avis.get("societe") or "").strip()
        if not numbers or not societe:
            continue
        journaliste = (avis.get("journaliste") or "").strip()
        named = journaliste and journaliste.lower() != "rédaction"
        source = f"presse:{_slug(societe)}" + (f":{_slug(journaliste)}" if named else "")
        libelle = f"{societe} – {journaliste}" if named else societe
        rows[source] = _row(id_course, source, "presse", libelle, _numbers(numbers), avant_depart, now)
    for synthese in (raw or {}).get("syntheses", []):
        key = synthese.get("intitule")
        ranked = sorted(synthese.get("classement", []), key=lambda c: -c.get("nbPoints", 0))
        numbers = [c["numPmu"] for c in ranked if c.get("numPmu")]
        if key in SYNTHESES and numbers:
            source = f"synthese:{key}"
            rows[source] = _row(id_course, source, "synthese", f"Presse : {SYNTHESES[key].lower()}", _numbers(numbers), avant_depart, now)
    return list(rows.values())


def most_played_rows(id_course: str, raw, now: str) -> list:
    """Betting closes at the start, so totals collected afterwards are still pre-race information."""
    rows = []
    for bet in (raw or {}).get("combinaisons", []):
        ranked = sorted(bet.get("listeCombinaisons", []), key=lambda c: -c.get("totalEnjeu", 0))
        bet_type = bet.get("pariType")
        if bet_type == "SIMPLE_GAGNANT":
            numbers = [c["combinaison"][0] for c in ranked if c.get("combinaison")][:PLAYED_TOP]
            if numbers:
                rows.append(_row(id_course, "joues", "parieurs", "Plus joués (simple gagnant)", _numbers(numbers), True, now))
        elif bet_type in COMBO_BETS:
            for i, combo in enumerate(ranked[:PLAYED_COMBOS], start=1):
                if combo.get("combinaison"):
                    rows.append(_row(
                        id_course, f"joues:{bet_type}:{i}", "combinaisons",
                        f"{COMBO_BETS[bet_type]} le plus joué n° {i}", _numbers(combo["combinaison"]), True, now,
                    ))
    return rows
