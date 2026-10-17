# Plan — Collecte fiable des arrivées du jour

## 1. Résumé des demandes
1. Les arrivées du jour doivent apparaître sur le site au fil des courses (≤ 20 min, plus le temps de publication d'environ 6 min), sans dépendre de la ponctualité de l'horloge GitHub.
2. Expliquer l'alerte d'erreur reçue (e-mail GitHub hier soir).

## 2. Évaluation
- **Alerte** : e-mail de l'échec du run 38969422172 (16/10, 23 h 26 Paris) : `scripts/data_store.sh: Permission denied`. Déjà corrigé (bit exécutable), tous les runs suivants sont verts. Rien à faire.
- **Arrivées** : la planification `*/20 9-22` a été mise en ligne le 17/10 à 0 h 30 et n'a encore jamais tourné. Mais l'horloge GitHub n'est pas fiable : le run de 7 h (cron `0 5`) du 17/10 n'a jamais eu lieu, et ceux de l'historique sont partis avec 2 h 49 et 4 h 24 de retard. GitHub ne garantit pas les déclenchements planifiés et en saute aux heures chargées (minute :00 surtout).
  Nature : correctif d'infrastructure. Ampleur : `.github/workflows/collect.yml`, `.github/workflows/history.yml`, nouveau `scripts/relay.sh`. Risque : la mise en ligne (une boucle mal bornée tournerait en continu ; des alertes en rafale).

## 3. Hors périmètre
- Déclenchement par le n8n du Pi : le n8n est en panne selon JP ; à reprendre plus tard, en secours.
- Aucun changement du code Python ni des pages du site.

## 4. Décisions et arbitrages
- Option retenue (JP ne veut pas dépendre du Pi en panne) : **relais par GitHub lui-même**. Un déclenchement manuel (`workflow_dispatch`) part immédiatement, contrairement au cron. Chaque run de la plage de courses attend le créneau suivant, puis lance le run suivant. Le cron ne sert plus qu'à démarrer ou redémarrer la chaîne.
- Créneaux décalés à :07, :27 et :47 (au lieu de :00, :20 et :40), moins chargés chez GitHub.
- Plage inchangée : 9 h à 22 h 59 UTC.
- Anti-doublon : le relais ne relance rien si un autre run de collecte est déjà en attente ou en cours (cron de secours, lancement manuel).
- Alertes : un run lancé par le relais est traité comme un run planifié (au plus 3 e-mails par jour), sinon une panne PMU enverrait un e-mail toutes les 20 minutes.
- L'historique de nuit (1 h 40 de travail sur le même verrou « data ») ne démarre plus s'il est lancé après 8 h UTC. Avec 4 h 24 de retard, il bloquerait les arrivées de la fin de matinée.
- Coût : dépôt public, minutes Actions gratuites (attente comprise).
- Petite tâche (un script et deux fichiers YAML), mais elle touche à la mise en ligne : je la fais moi-même (Opus) plutôt que de déléguer.

## 5. Points de risque
- Boucle infinie : bornée par la plage horaire (aucun relais si le créneau suivant est hors 9 h–22 h UTC) et par l'anti-doublon.
- Run annulé : pas de relais (`!cancelled()`), le cron suivant redémarre la chaîne.
- Échec de la collecte ou du déploiement : le relais tourne quand même, et la chaîne continue.
- Verrou « data » : le relais attend dans le run, qui garde le verrou. Un cron de secours reste en file, puis prend la suite, et le relais ne fait alors rien (anti-doublon).

## 6. Approche technique
1. `scripts/relay.sh` : calcule le prochain créneau (:07, :27 ou :47), sort s'il est hors plage, dort jusqu'à ce créneau, vérifie l'anti-doublon, puis lance `gh workflow run collect.yml -f relay=true`.
2. `collect.yml` : cron `7-59/20 9-22`, cron `5 5` le matin, entrée `relay`, job `relay` (`actions: write`), alerte adaptée.
   Constat du 17/10 qui confirme le besoin : aucun des 6 crons de 09:07 à 10:47 UTC n'a démarré.
3. `history.yml` : job `gate`, qui reporte un lancement planifié démarrant après 08 h UTC.
4. Push, lancement manuel, puis observation de la chaîne.

## 7. Plan de délégation
| # | Tâche | Fichiers | Modèle | Raison | Dépend de |
|---|---|---|---|---|---|
| T1 | Relais et workflows | scripts/relay.sh, collect.yml, history.yml | opus (moi) | mise en ligne, petite taille | — |
| T2 | Recette en ligne | — | opus (moi) | recette non déléguée | T1 |

## 8. Checklist
- [x] `relay.sh` testé à sec (10 horaires de 05:10 à 23:59 UTC) : dans la plage → bon créneau ; hors plage → sortie. Anti-doublon : vérifié en ligne (voir recette)
- [x] YAML valide (lecture YAML OK, runs acceptés par GitHub)
- [x] Un run lancé à la main enchaîne seul un run « relay » au créneau suivant (10:57 → 11:07:04 → 11:27:02 UTC)
- [ ] Pas de double chaîne quand le cron tombe en même temps — non observé en ligne : le cron de 11:27 n'a pas démarré du tout. La logique anti-doublon est en place mais pas encore vue en action
- [ ] Les alertes des runs relais suivent la règle des 3 e-mails par jour
- [ ] Une arrivée de course du 17/10 apparaît sur le site moins de 30 min après la course
- [ ] La chaîne s'arrête après 22 h 47 UTC
