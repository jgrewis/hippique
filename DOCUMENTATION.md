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
| `collect.yml` | 06:00, 11:00, 18:00, 21:45 UTC + manuel | Collecte d'hier (si incomplet) et du jour, pronostics, génération et publication du site, puis complément d'historique (35 min max). |
| `train.yml` | Lundi 04:00 UTC + manuel | Backtest, réentraînement, sauvegarde datée de la base (6 conservées), republication. |

Les deux partagent le groupe de concurrence `data`. Deux runs ne modifient donc jamais
la base en même temps.

**Alerte en cas de panne.** Si l'API PMU ne répond plus, le site est quand même publié
avec les données disponibles, et le job `alert` fait échouer le run. GitHub envoie alors
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

Codes de retour : `200` données, `204` pas (encore) de données. L'ancienne adresse
`www.pmu.fr/services/turfInfo/...` répond `403` (testé le 16/10/2026).

Unités à connaître : gains en centimes, poids en hectogrammes (605 = 60,5 kg),
heures en millisecondes epoch plus `timezoneOffset`.

**Repli HTML** : `https://www.turf-fr.com/arrivees-rapports-pmu`. Il ne récupère que les
arrivées du jour et de la veille (balise `<input id="coursearrivee">` et titre `R1C6`).
La numérotation R/C est identique à celle du PMU (vérifié).

**Politesse** : 1 seconde entre deux requêtes (`PMU_DELAY`), 3 tentatives avec attente
exponentielle. Une journée représente environ 60 à 120 requêtes.

## 4. Schéma de la base

Voir `db/schema.sql`. Tables :

| Table | Clé | Contenu |
|---|---|---|
| `courses` | `id_course` = `AAAA-MM-JJ-R1C1` | Une ligne par course française |
| `partants` | (`id_course`, `numero`) | Partants, cotes, arrivée, non-partants |
| `rapports` | (`id_course`, `type_pari`, `libelle`, `combinaison`) | Rapports pour 1 € |
| `pronostics` | (`id_course`, `numero`, `methode`) | Pronostics figés au départ (`forme`, `logit`) |
| `collect_days` | `date_course` | Jour complet ou non (permet la reprise de l'historique) |
| `collect_log` | `id` | Journal de chaque collecte (INFO / WARNING / ERROR) |

Toutes les écritures sont des « upserts » : relancer une collecte ne crée jamais de doublon.
Une course terminée (arrivée et rapports en base) n'est plus jamais redemandée.

## 5. Pronostics

- `predict/features.py` : un seul passage chronologique. Les critères d'une course du jour J
  n'utilisent que des données antérieures à J. La musique et les statistiques de carrière
  publiées par le PMU sont celles d'avant la course (vérifié : le gagnant du 15/09 n'a pas
  de « 1 » en tête de sa musique ce jour-là).
- `predict/form_score.py` : méthode 1, poids fixes et lisibles.
- `predict/logit_model.py` : méthode 2, logit conditionnel en deux étapes (critères, puis
  mélange avec la cote du matin), estimé par maximum de vraisemblance avec pénalité L2 (scipy).
- `predict/harville.py` : probabilités d'ordre d'arrivée.
- `predict/train.py` : test sur les 60 derniers jours avec un modèle entraîné sur la période
  précédente, puis réentraînement sur tout l'historique. Il faut au moins 300 courses terminées.
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
