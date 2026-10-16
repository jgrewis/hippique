"""Convert raw PMU JSON into rows matching db/schema.sql."""
from datetime import date, datetime, timedelta, timezone

DISCIPLINES = {
    "ATTELE": "Attelé",
    "MONTE": "Monté",
    "PLAT": "Plat",
    "HAIE": "Obstacle",
    "STEEPLECHASE": "Obstacle",
    "CROSS": "Obstacle",
}
MAIN_BETS = ("TIERCE", "QUARTE_PLUS", "QUINTE_PLUS")
KEPT_BETS = (
    "SIMPLE_GAGNANT", "SIMPLE_PLACE", "COUPLE_GAGNANT", "COUPLE_PLACE",
    "DEUX_SUR_QUATRE", "MULTI", "TIERCE", "QUARTE_PLUS", "QUINTE_PLUS",
)
ARRIVED_STATUSES = {"ARRIVEE"}


def course_id(day: date, num_reunion: int, num_course: int) -> str:
    return f"{day.isoformat()}-R{num_reunion}C{num_course}"


def _local_time(epoch_ms, offset_ms):
    if epoch_ms is None:
        return None
    moment = datetime.fromtimestamp(epoch_ms / 1000, tz=timezone.utc)
    return (moment + timedelta(milliseconds=offset_ms or 0)).strftime("%H:%M")


def _flatten_arrival(ordre):
    """[[7], [8], [2, 14]] -> "7-8-2=14" (dead heats joined by '=')."""
    if not ordre:
        return None
    return "-".join("=".join(str(n) for n in group) for group in ordre[:5])


def is_course_arrived(raw_course: dict) -> bool:
    return raw_course.get("categorieStatut") in ARRIVED_STATUSES and bool(raw_course.get("ordreArrivee"))


def normalize_course(day: date, raw_reunion: dict, raw_course: dict, now_iso: str) -> dict:
    bets = sorted({p["typePari"] for p in raw_course.get("paris", []) if p.get("typePari") in MAIN_BETS})
    terrain = (raw_course.get("penetrometre") or {}).get("intitule")
    arrived = is_course_arrived(raw_course)
    # Untrusted source: these numbers end up in API URLs and output file paths.
    num_reunion, num_course = int(raw_reunion["numOfficiel"]), int(raw_course["numOrdre"])
    return {
        "id_course": course_id(day, num_reunion, num_course),
        "date_course": day.isoformat(),
        "num_reunion": num_reunion,
        "num_course": num_course,
        "hippodrome": (raw_reunion.get("hippodrome") or {}).get("libelleCourt", "?"),
        "discipline": DISCIPLINES.get(raw_course.get("discipline"), raw_course.get("discipline")),
        "specialite": raw_course.get("specialite"),
        "distance_m": raw_course.get("distance"),
        "nb_partants": raw_course.get("nombreDeclaresPartants"),
        "heure_depart": _local_time(raw_course.get("heureDepart"), raw_course.get("timezoneOffset")),
        "depart_ts": raw_course.get("heureDepart"),
        "nom_course": raw_course.get("libelle"),
        "montant_prix": raw_course.get("montantPrix"),
        "categorie": raw_course.get("categorieParticularite"),
        "terrain": terrain,
        "paris": ",".join(bets),
        "is_quinte": int("QUINTE_PLUS" in bets),
        "statut": raw_course.get("statut"),
        "arrivee": _flatten_arrival(raw_course.get("ordreArrivee")) if arrived else None,
        "updated_at": now_iso,
    }


def _odds(raw: dict, key: str):
    value = (raw.get(key) or {}).get("rapport")
    return float(value) if value else None


def _weight_kg(raw: dict):
    hectograms = raw.get("poidsConditionMonte") or raw.get("handicapPoids")
    return hectograms / 10 if hectograms else None


def normalize_partant(id_course: str, raw: dict) -> dict:
    gains = (raw.get("gainsParticipant") or {}).get("gainsCarriere")
    return {
        "id_course": id_course,
        "numero": int(raw["numPmu"]),
        "nom_cheval": raw.get("nom", "?"),
        "id_cheval": raw.get("idCheval"),
        "age": raw.get("age"),
        "sexe": raw.get("sexe"),
        "driver_jockey": raw.get("driver"),
        "entraineur": raw.get("entraineur"),
        "musique": raw.get("musique"),
        "nb_courses": raw.get("nombreCourses"),
        "nb_victoires": raw.get("nombreVictoires"),
        "nb_places": raw.get("nombrePlaces"),
        "gains_carriere": gains // 100 if gains is not None else None,
        "poids_kg": _weight_kg(raw),
        "corde": raw.get("placeCorde"),
        "deferre": raw.get("deferre"),
        # "Reference" odds are the morning odds, "direct" the latest live ones.
        "cote_matin": _odds(raw, "dernierRapportReference"),
        "cote_actuelle": _odds(raw, "dernierRapportDirect"),
        "non_partant": int(raw.get("statut") == "NON_PARTANT"),
        "incident": raw.get("incident"),
        "arrivee": raw.get("ordreArrivee"),
    }


def normalize_rapports(id_course: str, raw_list: list) -> list:
    rows = {}
    for bet in raw_list or []:
        if bet.get("typePari") not in KEPT_BETS or bet.get("rembourse"):
            continue
        for r in bet.get("rapports", []):
            per_euro = r.get("dividendePourUnEuro")
            key = (bet["typePari"], r.get("libelle", ""), r.get("combinaison", ""))
            rows[key] = {
                "id_course": id_course,
                "type_pari": key[0],
                "libelle": key[1],
                "combinaison": key[2],
                "rapport": per_euro / 100 if per_euro is not None else None,
            }
    return list(rows.values())
