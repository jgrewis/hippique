# Documentation technique

## 1. Vue d'ensemble

```
API PMU (JSON) ──┐                       ┌─► predict/ (score de forme, logit, Harville)
                 ├─► collect/ ─► SQLite ─┤
turf-fr (repli) ─┘                       └─► site_builder/ ─► output/ ─► GitHub Pages
```

Tout tourne dans **GitHub Actions**. La base SQLite n'est pas versionnée dans Git :
elle est stockée, compressée, comme fichier attaché à une release GitHub nommée `data`
(script `scripts/data_store.sh`). Un fichier binaire réécrit quatre fois par jour aurait
fait grossir l'historique Git de plusieurs Go par an. Une release permet des fichiers
jusqu'à 2 Go, sans historique.

## 2. Workflows

| Workflow | Déclenchement | Rôle |
|---|---|---|
| `collect.yml` | 05:00 UTC, puis toutes les 20 min de 09:00 à 22:40 UTC + manuel | Collecte d'hier (si incomplète) et du jour, pronostics, génération et publication. Une course non partie n'est rechargée que si elle part dans l'heure ou si ses données ont plus de 3 h : un passage sans nouveauté ne coûte qu'une requête. Les arrivées apparaissent au plus 20 min après la course. |
| `history.yml` | 00:00 et 02:00 UTC + manuel | Complément d'historique (100 min max par passage), recalcul du backtest de toutes les sources et du logit, puis republication. |
| `train.yml` | Lundi 04:00 UTC + manuel | Entraînement, sauvegarde datée de la base (6 conservées), republication, maintien des planifications. |

Les trois partagent le groupe de concurrence `data`. Deux runs ne modifient donc jamais
la base en même temps.

**Alerte en cas de panne.** Si l'API PMU ne répond plus, le site est quand même publié
avec les données disponibles, et le job `alert` fait échouer le run, mais seulement pour le run
du matin, les runs de 12 h et 18 h UTC et les lancements manuels (3 e-mails par jour au plus). GitHub envoie alors
automatiquement un e-mail au propriétaire du dépôt (paramètre GitHub → Settings →
Notifications → Actions, activé par défaut).

## 3. Endpoints utilisés

Deux hôtes servent la même API. Ils sont essayés dans cet ordre (`config.PMU_HOSTS`) :

- `https://offline.turfinfo.api.pmu.fr/rest/client/7`
- `https://online.turfinfo.api.pmu.fr/rest/client/61`

| Chemin | Contenu |
|---|---|
| `/programme/{JJMMAAAA}` | Réunions, courses, statut, ordre d'arrivée, paris proposés |
| `/programme/{JJMMAAAA}/R{n}/C{m}/participants` | Partants : musique, carrière, gains, poids, cotes (`dernierRapportReference` = cote matin, `dernierRapportDirect` = dernière cote), ordre d'arrivée |
| `/programme/{JJMMAAAA}/R{n}/C{m}/rapports-definitifs` | Rapports de tous les paris (`dividendePourUnEuro` en centimes) |
| `/programme/{JJMMAAAA}/R{n}/C{m}/pronostics` | Pronostic officiel PMU (Datahippique) : classement des partants. Environ 40 jours d'historique. |
| `/programme/{JJMMAAAA}/R{n}/C{m}/pronostics-detailles` | Sélections presse et experts (`avis`), synthèse favoris / outsiders / délaissés. Environ 40 jours d'historique. |
| `/programme/{JJMMAAAA}/R{n}/C{m}/combinaisons` | Montants misés par combinaison et par pari (les plus joués). Historique long. |

**Droit d'auteur** : les endpoints de pronostics contiennent aussi des commentaires rédigés
(journalistes, PMU). Ils ne sont **jamais** stockés ni publiés : seuls le nom de la source et
ses numéros sont conservés (`collect/external_forecasts.py`, vérifié par un test).

Codes de retour : `200` données, `204` pas (encore) de données. L'ancienne adresse
`www.pmu.fr/services/turfInfo/...` répond `403` (testé le 16/10/2026).

Unités à connaître : gains en centimes, poids en hectogrammes (605 = 60,5 kg),
heures en millisecondes epoch plus `timezoneOffset`.

**Repli HTML** : `https://www.turf-fr.com/arrivees-rapports-pmu`. Il ne récupère que les
arrivées du jour et de la veille (balise `<input id="coursearrivee">` et titre `R1C6`).
La numérotation R/C est identique à celle du PMU (vérifié).

**Politesse** : 1 seconde entre deux requêtes (`PMU_DELAY`), 3 tentatives avec attente
exponentielle. Une journée représente environ 150 à 250 requêtes (5 par course tant qu'elle n'est pas terminée et complète, plus aucune ensuite).

## 4. Schéma de la base

Voir `db/schema.sql`. Tables :

| Table | Clé | Contenu |
|---|---|---|
| `courses` | `id_course` = `AAAA-MM-JJ-R1C1` | Une ligne par course française |
| `partants` | (`id_course`, `numero`) | Partants, cotes, arrivée, non-partants |
| `rapports` | (`id_course`, `type_pari`, `libelle`, `combinaison`) | Rapports pour 1 € |
| `pronostics` | (`id_course`, `numero`, `methode`) | Pronostics maison figés au départ (`forme`, `logit`, `boosting`, `elo`, `consensus`) |
| `selections` | (`id_course`, `source`) | Classements externes : PMU, presse, synthèse, plus joués. `avant_depart` = collecté avant le départ ; une sélection d'avant départ n'est jamais remplacée par une collecte postérieure. |
| `collect_days` | `date_course` | Jour complet ou non (permet la reprise de l'historique) |
| `collect_log` | `id` | Journal de chaque collecte (INFO / WARNING / ERROR) |

Toutes les écritures sont des « upserts » : relancer une collecte ne crée jamais de doublon.
Une course terminée (arrivée, rapports et sources externes en base, `externes_ok = 1`) n'est plus
jamais redemandée. Une course terminée sans sources externes ne refait que ces 3 appels.

**Migrations** : `db/repository.py::_migrate` met à jour une base créée par une version antérieure
au démarrage (ajout de `courses.externes_ok`, remise à zéro de `collect_days.complete` pour
compléter les sources externes de l'historique).

## 5. Pronostics

- `predict/features.py` : un seul passage chronologique. Les critères d'une course du jour J
  n'utilisent que des données antérieures à J. La musique et les statistiques de carrière
  publiées par le PMU sont celles d'avant la course (vérifié : le gagnant du 15/09 n'a pas
  de « 1 » en tête de sa musique ce jour-là).
- `predict/form_score.py` : méthode 1, poids fixes et lisibles.
- `predict/logit_model.py` : méthode 2, logit conditionnel en deux étapes (critères, puis
  mélange avec la cote du matin), estimé par maximum de vraisemblance avec pénalité L2 (scipy).
- `predict/elo.py` : méthode 4, Elo multi-concurrents (cheval et driver), aussi utilisé comme critère.
- `predict/boosting.py` : méthode 3, gradient boosting scikit-learn, **réentraîné à chaque run et jamais
  écrit sur disque** (les modèles scikit-learn se sauvegardent avec `pickle`, qui exécute du code au chargement).
- `predict/consensus.py` : méthode 5, Borda par familles à poids égal.
- `predict/sources.py` : toutes les sources (maison, PMU, presse, parieurs) sous une forme unique,
  utilisée par l'affichage, le consensus et la fiabilité.
- `predict/harville.py` : probabilités d'ordre d'arrivée.
- `predict/train.py` : test de toutes les sources sur les 60 derniers jours (modèles entraînés sur la
  période précédente), puis réentraînement du logit sur tout l'historique. Il faut au moins 300 courses
  terminées. Lancé à chaque collecte (quelques secondes). Pour les sources externes, le test historique
  inclut des sélections collectées après coup ; seul le bilan « résultats réels » ne retient que celles
  collectées avant le départ.
- `predict/forecast.py` : pronostics des courses non encore parties. Ils ne sont plus jamais
  réécrits après le départ, ce qui rend honnête le bilan « Résultats réels » de la page Fiabilité.

## 6. Maintenance

| Symptôme | Action |
|---|---|
| E-mail « run failed » de GitHub | Ouvrir le run → étape « Collecter ». `SourceUnavailable` = API en panne. Attendre le run suivant ; si ça dure plus de 24 h, tester les endpoints à la main (section 3). |
| L'API répond, mais les champs ont changé | Corriger `collect/normalize.py`, ajouter un fichier JSON réel dans `tests/fixtures/`, lancer `pytest`. |
| L'un des deux hôtes disparaît | Le second prend le relais automatiquement. Mettre à jour `config.PMU_HOSTS`. |
| Le repli turf-fr ne trouve plus rien | Vérifier la page et adapter `collect/scraper.py` (`parse_arrival_page`). |
| Base corrompue ou perdue | Release `data` → télécharger une sauvegarde `turf-AAAA-MM-JJ.db.gz`, la renommer `turf.db.gz` et la remettre en ligne (`gh release upload data turf.db.gz --clobber`). |
| Site non mis à jour | Onglet Actions → « Collecte et publication » → Run workflow. |

Un run planifié peut partir avec 5 à 30 minutes de retard : c'est normal sur GitHub Actions.
GitHub désactive les workflows planifiés d'un dépôt public après 60 jours sans commit.
`train.yml` les réactive chaque semaine via l'API, ce qui remet ce compteur à zéro. En cas de
désactivation malgré tout : onglet Actions → « Enable workflow ».

## 7. Zones grises juridiques

- **API PMU** : non documentée et non ouverte officiellement. Son usage n'est ni autorisé
  ni interdit explicitement. Ce projet reste personnel, non commercial, peu fréquent
  (4 collectes par jour) et ne republie pas les données à des fins commerciales.
- **Scraping de secours** : limité aux arrivées, en respectant le `robots.txt` de turf-fr.com
  (les pages de résultats n'y sont pas interdites), avec 1 seconde entre deux requêtes.
- **Données** : les résultats de courses sont des faits, non protégés par le droit d'auteur.
  Le schéma de base de données est propre à ce projet.
- **Site public** : GitHub Pages gratuit est public. Le site est marqué `noindex` (balise
  meta et `robots.txt`) et n'est lié nulle part, mais toute personne qui connaît l'adresse
  peut le consulter.
