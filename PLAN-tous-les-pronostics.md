# Plan — Tous les pronostics

## 1. Résumé des demandes

1. Afficher, pour chaque course, **tous les pronostics disponibles**, regroupés par origine :
   - **Méthodes maison** (5) : score de forme et logit (existants), **gradient boosting**, **classement Elo**, **consensus de toutes les sources** (nouveaux) ;
   - **PMU officiel** : classement Datahippique ;
   - **Presse et experts** : sélection de chaque média ou expert (10 à 15 par course), plus la synthèse « favoris, outsiders, délaissés » ;
   - **Parieurs** : favori des cotes, chevaux les plus joués en simple gagnant, et les 3 combinaisons les plus jouées en Tiercé, Quarté+ et Quinté+.
2. **Comparer la fiabilité de toutes ces sources** sur la page Fiabilité, avec les mêmes indicateurs pour chacune, sur l'historique et sur les pronostics réels.
3. Montrer, pour chaque partant, **combien de sources le citent**.
4. Accueil : le Quinté+ du jour affiche le pronostic consensus.
5. *(Ajout en cours de route, 17/10)* **Rendre les arrivées lisibles** : tapis numérotés par place sur la page du jour,
   arrivée de référence en tête des pronostics, place obtenue sous chaque numéro pronostiqué, colonne Arrivée
   déplacée près du numéro dans le tableau des partants.

## 2. Hors périmètre

- **Aucun texte rédigé par la presse ou le PMU** (commentaires, analyses par cheval) : textes protégés par le droit d'auteur, refusés par le client. Seuls le nom du média, celui de l'expert et ses numéros sont repris.
- Pas de casaques ni d'images du PMU : ressources externes interdites par la CSP et la règle « zéro ressource externe ».
- Pas de suivi en direct des cotes ou des enjeux : on garde l'instantané des 4 collectes quotidiennes.
- Historique par cheval et statistiques par driver : toujours prévus en v2.

## 3. Décisions et arbitrages

| Sujet | Décision | Origine |
|---|---|---|
| Méthodes ajoutées | Gradient boosting, Elo, consensus | Client (« les trois ») |
| Commentaires presse | Non repris, sélections seulement | Client (« on ne fait pas cela ») |
| Fiabilité presse et PMU | Comparée malgré un historique d'environ 1 mois au départ | Client (« parfait ») |
| Carte hub | Publiée le 17/10/2026 | Client |
| Persistance du boosting | **Pas de fichier modèle** : réentraîné à chaque run (quelques secondes). Évite `pickle`, qui exécute du code au chargement et serait un risque si la release était altérée. | Moi |
| Elo | Un Elo cheval et un Elo driver, mis à jour en « multi-joueurs » (chaque partant bat ceux qu'il devance, K = 24/(n−1)). Sert de méthode autonome **et** de critère supplémentaire pour le logit et le boosting. | Moi |
| Consensus | Borda par familles : chaque source note ses 8 premiers (8 → 1 point). On fait la moyenne dans chaque famille (maison, PMU, presse, parieurs), puis la somme des 4 familles. Ainsi, 15 médias ne noient pas les autres sources. | Moi |
| Experts homonymes | Clé de source = média + nom du journaliste quand ce n'est pas « Rédaction ». | Moi |
| Arrivées (demande 5) | Place affichée en texte sous chaque numéro (pas seulement la couleur) ; colonne Arrivée déplacée en 3e position (page du jour) et 2e (partants) pour rester visible sur mobile. | Moi |
| Backtest à chaque collecte | `predict.train` passe de « si absent » à chaque run (≈ 10 s) : la page Fiabilité reste à jour et l'ancien `backtest.json` est remplacé dès le premier run. | Moi |
| Pronostic PMU a posteriori | Suspicion que l'endpoint soit réécrit après la course (15/09 : 7-8 en tête = arrivée). Instantané du Quinté+ du 17/10 pris à 00h07 pour comparaison après la course. En attendant, le bilan réel n'utilise que les sélections collectées avant le départ. | Moi |
| Données presse anciennes | L'API renvoie 204 au-delà d'environ 40 jours : l'historique ne demande pas ces endpoints pour les dates plus anciennes (gain de temps). | Moi |

## 4. Points de risque

| Risque | Parade |
|---|---|
| Base existante (en production dans la release) sans les nouvelles tables ni colonnes | Migration automatique au démarrage (`ALTER TABLE` si la colonne manque). Testée sur une copie de la base de production avant le push. |
| Jours déjà « complets » qui n'auront jamais leurs pronostics externes | Nouvelle colonne `courses.externes_ok`. Une course terminée sans données externes ne fait plus que les 3 nouveaux appels, sans recharger les partants. La migration remet `collect_days.complete` à 0 pour que l'historique repasse. |
| Volume de requêtes ×2 à ×3 | Délai d'1 s conservé. Endpoints presse et PMU ignorés au-delà de 40 jours. L'historique complet prendra quelques jours de plus. |
| Format des endpoints externes qui change | Chaque source est facultative : une erreur est journalisée, et la course reste affichée sans cette source. Tests sur réponses réelles enregistrées. |
| Biais du backtest : les sources externes « voient » des infos d'avant course, le modèle doit aussi | Sélections presse et PMU publiées avant la course ; enjeux figés au départ. Les méthodes maison restent calculées sans regarder l'avenir. Le consensus du backtest n'utilise que ce qui était disponible. |
| Tableau illisible sur mobile avec 20 sources | Liste groupée par famille, numéros en « tapis de selle » qui passent à la ligne, familles repliables (`<details>`, sans JS). |
| Durée de build | Le boosting s'entraîne une fois par run, pas par course. Mesure du temps avant et après. |
| Retour arrière | `git revert` du commit, puis relance du workflow. Les nouvelles tables sont ignorées par l'ancien code (compatible). |

## 5. Approche technique

**Fichiers touchés**
- `db/schema.sql`, `db/repository.py` : table `selections (id_course, source, famille, libelle, numeros, rang_source)`, colonne `courses.externes_ok`, migration.
- `collect/api_pmu.py`, `collect/normalize.py`, `collect/pipeline.py` : 3 endpoints (`pronostics`, `pronostics-detailles` limité aux sélections et synthèses, `combinaisons`), normalisation en classements.
- `predict/elo.py` (nouveau), `predict/features.py` (critères Elo), `predict/boosting.py` (nouveau, scikit-learn), `predict/consensus.py` (nouveau), `predict/forecast.py`, `predict/train.py`, `predict/backtest.py` (toutes les sources).
- `site_builder/views.py` et templates `course.html`, `day.html`, `reliability.html`, `_macros.html`, `methodology.html`, plus le CSS (réutilisation des tokens existants).
- `requirements.txt` (scikit-learn), tests et nouvelles fixtures réelles, README et DOCUMENTATION.

**Tranches**
1. **Données externes de bout en bout** : collecte, base, migration et affichage brut sur la page course (PMU, presse, parieurs). Livrable seule.
2. **Elo**, comme méthode et comme critère.
3. **Gradient boosting**.
4. **Consensus**, plus la colonne « cité par N sources » et le Quinté+ de l'accueil.
5. **Fiabilité de toutes les sources** (backtest et réel).
6. Documentation, recette navigateur, migration testée sur une copie de la base de production, puis push et vérification en ligne.

## 6. Checklist

**Demandes**
- [x] Page course : section Pronostics groupée en Maison (5), PMU, Presse (une ligne par média ou expert), Parieurs
- [x] Aucun texte de journaliste ni du PMU dans les pages générées (vérifié par recherche dans `output/`)
- [x] Synthèse presse favoris / outsiders / délaissés affichée
- [x] Plus joués : classement simple gagnant et 3 combinaisons les plus jouées pour Tiercé, Quarté+ et Quinté+ quand ces paris existent
- [x] Gradient boosting : probabilités par partant, somme = 100 % par course
- [x] Elo cheval et driver calculés chronologiquement, sans fuite (test)
- [x] Consensus calculé par familles et affiché
- [x] Colonne « Presse » (cité par N/M sélections) dans le tableau des partants
- [x] Accueil : le Quinté+ affiche le consensus
- [x] Fiabilité : toutes les sources dans un même tableau (historique et réel), avec le nombre de courses par source

**Données et robustesse**
- [x] Migration testée sur une copie de la base de production : aucune perte, colonnes ajoutées, historique relancé
- [x] Une source absente (204) ou en erreur n'empêche ni la collecte ni l'affichage du reste
- [x] Course terminée : seuls les 3 endpoints manquants sont demandés, une seule fois
- [x] Endpoints presse et PMU non demandés au-delà de 40 jours
- [x] Les tests existants et nouveaux passent

**Référentiel et usage**
- [x] Tokens CSS existants réutilisés, aucun style inline (CSP)
- [x] 375, 768 et 1280 px : pas de défilement horizontal de la page, lisible
- [x] Clavier : les sections repliables sont accessibles, focus visible
- [x] État vide : message clair quand une source n'a pas de données
- [x] Console sans erreur, 0 lien cassé
- [x] Méthodes décrites sur la page Méthode, documentation à jour
- [ ] Workflow en ligne : run vert, nouvelles sections visibles sur le site
- [x] Arrivées lisibles : page du jour, référence en tête des pronostics, place sous chaque numéro, colonne partants
- [ ] Après le Quinté+ du 17/10 : comparer le pronostic PMU collecté avant et après la course
