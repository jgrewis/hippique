# Plan — Arrivée et rapports en priorité

## 1. Résumé des demandes
Quand une course est arrivée, le turfiste veut deux choses avant tout : les chevaux arrivés et les rapports.

1. Fiche course : les rapports s'affichent juste sous l'arrivée officielle, avant le pronostic, les sources et les partants.
2. Fiche course : si l'arrivée est connue mais pas encore les rapports, un message le dit à la même place.
3. Accueil : le bloc « Quinté+ du jour » montre les principaux rapports (Quinté+, Quarté+, Tiercé) à côté de l'arrivée.
4. Collecte : les rapports d'une course arrivée sont récupérés plus vite qu'aujourd'hui (jusqu'à 20 min de retard sur l'arrivée).

## 2. Évaluation
| Demande | Nature | Ampleur | Risques |
|---|---|---|---|
| 1, 2 | Affichage | `course.html` (déplacement de section + sommaire) | Faible : même contenu, autre ordre |
| 3 | Affichage | `day.html`, `views.py`, CSS du héros | Lisibilité sur fond vert en mobile |
| 4 | Collecte / mise en ligne | `collect.yml`, `relay.sh`, nouveau module de détection | Chaîne du relais : ne pas la casser ni la dupliquer ; ne pas boucler indéfiniment |

Constat du 17/10 : le PMU publie l'arrivée avant les rapports. La collecte de 15 h 27 a vu l'arrivée du quinté (départ 15 h 15) sans rapports ; ils sont arrivés avec celle de 15 h 47.

## 3. Hors périmètre
- Changer le rythme de base de la collecte (20 min) : la passe de rattrapage ne se déclenche que si des rapports manquent.
- Notifications (mail, push) à l'arrivée.
- Rapports sur les pages « jour » autres que le bloc quinté (le tableau des courses garde l'arrivée seule).

## 4. Décisions et arbitrages
- Arbitré par le client (17/10) : les trois changements sont faits.
- Rattrapage, option retenue : quand une collecte voit une course arrivée sans rapports, le relais lance la collecte suivante 6 min plus tard au lieu d'attendre le créneau de 20 min. Écartée : attendre dans l'étape de collecte (retarde la publication de l'arrivée et des cotes de tout le run).
- Fenêtre : seules les courses parties depuis moins de 60 min déclenchent le rattrapage, pour ne pas boucler sur une course dont les rapports ne viendront jamais (paris remboursés, course annulée).
- Accueil : Quinté+ ordre et désordre, Bonus 4 et Bonus 3, Quarté+ ordre et désordre, Tiercé ordre et désordre, plus un lien vers tous les rapports. Pour les bonus, une seule valeur (identique pour toutes les combinaisons).
- Toutes les tâches sont petites : faites directement par l'orchestrateur (règle « petites tâches »).
- En cours de route : sur grand écran (≥ 1024 px), les rapports du héros passent sur deux colonnes, sinon la carte s'allonge trop.
- Le relais peut viser un rattrapage après 22 h UTC (ex. 22 h 56) tant que l'heure reste dans la plage : accepté, cela ne concerne que la dernière course du soir.

## 5. Points de risque
- Relais : une relance anticipée ne doit pas créer deux chaînes parallèles. Dérisqué : `relay.sh` vérifie déjà qu'aucune autre collecte n'est en file avant de relancer.
- Hors de la plage horaire (après 22 h UTC) : la règle de fin de relais reste appliquée au créneau anticipé.
- Fiche course : le sommaire (ancres) doit suivre le nouvel ordre.

## 6. Approche technique
1. `course.html` : section Rapports déplacée sous l'arrivée ; message d'attente ; sommaire réordonné.
2. `views.py` : `quinte_summary(rapport_groups)` sélectionne les lignes du héros ; `day.html` + CSS les affichent.
3. `db/repository.py` : `courses_awaiting_rapports(conn, day, since_ms)` ; `collect/pending.py` écrit `pending_rapports=<n>` dans `GITHUB_OUTPUT`.
4. `collect.yml` : étape après la collecte, sortie `pending_rapports` transmise au job relay ; `relay.sh` : `CATCHUP=1` → créneau = min(prochain créneau, maintenant + 6 min).
5. Tests : vues, détection, décision du relais (`DRY_RUN`).

## 7. Plan de délégation
| # | Tâche | Fichiers | Modèle | Raison | Dépend de |
|---|---|---|---|---|---|
| T1 | Rapports sous l'arrivée | course.html | opus (orchestrateur) | Quelques lignes | — |
| T2 | Rapports du quinté à l'accueil | views.py, day.html, CSS | opus (orchestrateur) | Petit, design | — |
| T3 | Passe de rattrapage | repository.py, collect/pending.py, collect.yml, relay.sh | opus (orchestrateur) | Mise en ligne, risque de casser le relais | — |
| T4 | Recette | — | opus (orchestrateur) | Responsabilité de l'orchestrateur | T1–T3 |

## 8. Checklist
- [x] Fiche d'une course arrivée : la section Rapports suit immédiatement l'arrivée officielle
- [x] Sommaire de la fiche : Arrivée, Rapports, Pronostic, Toutes les sources, Partants
- [x] Course arrivée sans rapports : message « Rapports en attente » sous l'arrivée
- [x] Accueil, quinté arrivé : Quinté+ ordre/désordre, bonus, Quarté+, Tiercé et lien « Tous les rapports »
- [x] Accueil, quinté arrivé sans rapports : mention d'attente ; quinté pas encore couru : affichage inchangé
- [x] `collect.pending` compte les courses arrivées sans rapports parties depuis moins de 60 min
- [x] `relay.sh` avec `CATCHUP=1` vise maintenant + 6 min si c'est avant le prochain créneau, sinon le créneau
- [x] `relay.sh` sans `CATCHUP` : comportement inchangé
- [x] Workflow valide (YAML) et sortie transmise au job relay
- [x] Tests existants et nouveaux au vert
- [x] Rendu vérifié en navigateur à 375, 768 et 1280 px, sans débordement ni scroll horizontal
- [x] Aucune erreur console ni ressource 404

## 9. Recette (17/10/2026)
- Tests : 32 passés (dont 4 nouveaux : ordre de la fiche et accueil, état d'attente, sélection des rapports du héros, détection et décision du relais).
- Relais en simulation (`DRY_RUN`) : 13 h 29 sans attente → 13 h 47 ; avec rapports en attente → 13 h 35 ; à 13 h 42 → créneau de 13 h 47 conservé.
- Navigateur, base réelle du 17/10 : accueil à 1280, 768 et 375 px, fiche R1C3 (rapports sous l'arrivée, sommaire réordonné), fiche R12C4 (message d'attente). Aucun défilement horizontal, aucune erreur console.
- Non vérifiable en local : le déclenchement réel d'une collecte de rattrapage sur GitHub Actions, à observer au prochain jour de courses.
