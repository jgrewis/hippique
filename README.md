# Hippique

Site personnel d'analyse des courses PMU (Tiercé, Quarté+, Quinté+) : programme du jour,
partants, cotes, arrivées, rapports et pronostics statistiques. Sans publicité, sans traceur,
sans cookie, sans serveur et pour 0 €.

- **Collecte** : API JSON non officielle du PMU, avec repli HTML sur turf-fr.com pour les arrivées.
- **Stockage** : SQLite.
- **Pronostics** : cinq méthodes maison (score de forme, logit conditionnel, gradient boosting,
  classement Elo, consensus de toutes les sources), le pronostic PMU, les sélections de la presse
  (sans leurs textes) et ce que jouent les parieurs. La fiabilité de chaque source est mesurée et publiée.
- **Publication** : site statique généré par Jinja2 et publié sur GitHub Pages.
  GitHub Actions automatise tout.

Détails techniques, endpoints, maintenance et zones grises juridiques : voir [DOCUMENTATION.md](DOCUMENTATION.md).

## Pages du site

| Page | Contenu |
|---|---|
| `index.html` | Programme du jour, Quinté+ mis en avant, filtres (hippodrome, discipline, distance), export CSV |
| `jour/AAAA-MM-JJ.html` | Programme et arrivées d'un jour, navigation par date |
| `course/AAAA-MM-JJ-R1C1.html` | Arrivée, tous les pronostics (avec la place obtenue par chaque cheval), partants, cotes, probabilités, rapports |
| `archives.html` | Tous les jours collectés |
| `fiabilite.html` | Performance réelle des pronostics et test sur l'historique, comparés au favori |
| `methodo.html` | Méthodes, limites, sources, cadre légal |

## Installation locale

Prérequis : Python 3.11 ou plus récent.

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Utilisation locale

```bash
.venv/bin/python -m collect.pipeline                    # collecte d'hier (si incomplet) et du jour
.venv/bin/python -m collect.pipeline --date 2026-10-15  # une date précise
.venv/bin/python -m scripts.backfill --days 30          # historique (reprend là où il s'est arrêté)
.venv/bin/python -m predict.train                       # backtest et modèle (au moins 300 courses)
.venv/bin/python -m predict.forecast                    # pronostics des courses à venir
.venv/bin/python -m site_builder.builder                # génère le site dans output/
```

Ou tout en une fois : `scripts/run_daily.sh` (le script utilise le `python` actif, activer `.venv` avant).

Pour consulter le site généré :

```bash
python3 -m http.server 8765 --directory output
```

puis ouvrir http://localhost:8765.

Tests :

```bash
.venv/bin/python -m pytest -q
```

## Structure

```
.github/workflows/
  collect.yml        Collecte toutes les 20 min en journée, pronostics, publication Pages
  history.yml        La nuit : historique, backtest de toutes les sources, republication
  train.yml          Réentraînement hebdomadaire, sauvegarde datée, maintien des planifications
collect/
  http_client.py     Délai entre requêtes, relances, bascule entre les deux hôtes PMU
  api_pmu.py         Endpoints programme / participants / rapports
  normalize.py       JSON PMU → lignes de la base
  external_forecasts.py  Pronostics PMU, presse et plus joués → classements (sans textes)
  scraper.py         Repli HTML (arrivées) sur turf-fr.com
  pipeline.py        Orchestration d'une journée de collecte
db/
  schema.sql         Schéma SQLite
  repository.py      Accès base (upserts idempotents, lectures)
predict/
  musique.py         Analyse de la musique
  features.py        Critères par partant, sans fuite d'information
  form_score.py      Méthode 1 : score de forme
  logit_model.py     Méthode 2 : logit conditionnel en deux étapes
  boosting.py        Méthode 3 : gradient boosting (scikit-learn)
  elo.py             Méthode 4 : classement Elo cheval et driver
  consensus.py       Méthode 5 : consensus de toutes les sources
  sources.py         Toutes les sources sous une forme commune
  harville.py        Probabilités d'ordre d'arrivée
  backtest.py        Mesures de fiabilité
  train.py           Entraînement et backtest
  forecast.py        Pronostics maison du jour (figés au départ)
site_builder/
  builder.py         Génération des pages
  views.py           Préparation des données pour les modèles
  template_filters.py Formatage français
  templates/         Modèles Jinja2
  static/            CSS et JavaScript (filtres, export CSV, navigation par date)
scripts/
  backfill.py        Historique, reprise possible, limité dans le temps
  data_store.sh      Sauvegarde et restauration de la base (release GitHub « data »)
  run_daily.sh       Équivalent local du workflow de collecte
tests/               pytest et réponses PMU / turf-fr réelles enregistrées
config.py            Chemins, hôtes, délais
```

## Déploiement sur GitHub (une seule fois)

1. Créer un dépôt **public** `hippique` (GitHub Pages et Actions sont gratuits et illimités pour un dépôt public), puis y pousser ce dossier.
2. Dépôt → **Settings → Pages → Build and deployment → Source : « GitHub Actions »**.
3. Dépôt → **Settings → Actions → General → Workflow permissions : « Read and write permissions »**.
4. Onglet **Actions** → « Collecte et publication » → **Run workflow**.

Le site est alors en ligne à l'adresse `https://<utilisateur>.github.io/hippique/`.
Chaque nuit, deux passages complètent l'historique (100 minutes chacun) : l'année complète
est disponible en quelques nuits. Le premier modèle logit est entraîné dès que 300 courses
terminées sont en base. En attendant, seul le score de forme est affiché.

Pour accélérer l'historique, on peut aussi le récupérer en local (`scripts.backfill`), puis
publier la base : `gzip -k data/turf.db && gh release create data data/turf.db.gz --title "Données" --notes "Base SQLite" --latest=false`
(ou `gh release upload data data/turf.db.gz --clobber` si la release existe déjà).

## Variables d'environnement (facultatives)

| Variable | Défaut | Rôle |
|---|---|---|
| `PMU_DELAY` | `1.0` | Secondes entre deux requêtes |
| `HIPPIQUE_DATA_DIR` | `data/` | Dossier de la base et du modèle |
| `HIPPIQUE_OUTPUT_DIR` | `output/` | Dossier du site généré |
| `SITE_BASE_PATH` | `/` | Chemin de base du site (rempli automatiquement par le workflow) |

## Avertissement

Les pronostics sont des estimations statistiques, sans aucune garantie de gain. Jouer comporte
des risques : endettement, dépendance. Joueurs Info Service : 09 74 75 13 13 (appel non surtaxé).
