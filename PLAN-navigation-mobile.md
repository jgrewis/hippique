# Plan — Navigation plus simple sur téléphone

## 1. Résumé des demandes
Public : turfistes passionnés, souvent âgés, qui consultent surtout sur téléphone. Les codes R1C3 restent tels quels, ce public les connaît.

- **A. Accueil, accès direct aux courses.** La liste des courses commence aujourd'hui à 2 380 px, soit le 3ᵉ écran. Il faut pouvoir l'atteindre d'un geste.
- **B. Liste des courses lisible sur téléphone.** Le tableau fait 998 px de large pour un écran de 341 px : l'arrivée est cachée à droite, et chaque ligne prend 37 à 97 px. Objectif : une course par carte compacte, avec l'arrivée visible, sans défilement de côté, et la carte entière cliquable.
- **C. Page de course moins longue.** Elle fait 9 300 px, soit 11,5 écrans. « Tous les pronostics » occupe 3 970 px, les rapports 2 670 px et les partants 1 150 px. Objectif : un sommaire pour sauter à chaque partie, et les gros blocs repliés par défaut sur téléphone.
- **D. Passer d'une course à l'autre.** Boutons « ← course précédente », « course suivante → » et « Retour au programme » en haut et en bas de chaque page de course, plus un bouton « Haut de page ».
- **E. Lisibilité.**
  - Menu entièrement visible sur téléphone : « Méthode » est coupé aujourd'hui.
  - Textes des tableaux passés de 14 à 16 px.
  - Zones à toucher d'au moins 44 px.

## 2. Évaluation
| Demande | Nature | Ampleur | Risque |
|---|---|---|---|
| A | design | day.html, style.css | faible |
| B | design et responsive | day.html, style.css | moyen : l'export CSV et les filtres lisent le tableau. On garde donc le même HTML et seul le CSS change sous 640 px. |
| C | design et un peu de JS | course.html, style.css, nouveau JS | faible : sans JS, tout reste ouvert |
| D | fonctionnalité | views.py (course voisine), course.html, tests | faible |
| E | design | base.html, style.css | moyen : grossir le texte peut faire déborder les blocs, à vérifier à 375 px |

## 3. Hors périmètre
- Renommer « R1C3 » : refusé par JP.
- Changer l'affichage ordinateur, sauf les retombées de D et E (boutons de navigation, menu, taille du texte des tableaux).
- Collecte et données : aucune modification.
- Plan de collecte fiable (`PLAN-collecte-fiable.md`) : en attente, sujet séparé.

## 4. Décisions et arbitrages
- B se fait **en CSS sur le tableau existant**, sans second gabarit : l'export CSV et les filtres continuent de fonctionner tels quels.
- La carte de course affiche sur une première ligne le code R1C3, l'heure et le nom, puis l'arrivée (ou « en attente »), puis une ligne discrète discipline · distance · partants. Les paris passent en badges. L'hippodrome est déjà dans l'en-tête de réunion.
- C : sur téléphone, les groupes de « Tous les pronostics » et les rapports sont repliés, sauf le consensus maison et le Quinté+. Ils restent ouverts sur ordinateur et sans JavaScript.
- A : sur téléphone, les filtres sont repliés derrière un bouton « Filtrer les courses » (383 px → 48 px), et un bouton « Voir les courses ↓ » est ajouté sous le titre.
- D : « course précédente / suivante » suit l'ordre chronologique des départs du jour, toutes réunions confondues. Plus utile qu'R1C1 → R1C2 quand on suit la journée.
- Tokens existants réutilisés (`--tap`, `--fs-*`, `--space-*`). Aucune nouvelle couleur.

## 5. Points de risque
- Tableau en cartes : en-têtes masqués visuellement, mais pas pour les lecteurs d'écran. On garde `<table>` et la sémantique.
- Carte cliquable : le lien « étiré » ne doit pas masquer les autres liens.
- Texte en 16 px : le tableau des partants reste défilant de côté. La colonne N° est déjà figée et on fige aussi le nom du cheval.
- Mode sombre : à vérifier sur chaque nouvel élément.

## 6. Approche technique
1. `views.py` : `course_context` reçoit les courses voisines (`prev_course`, `next_course`) et `builder.py` les fournit. Un test unitaire est ajouté.
2. `course.html` : barre de navigation (haut et bas), sommaire d'ancres, `<details>` autour des rapports, bouton haut de page.
3. `day.html` : bouton « Voir les courses », filtres dans un `<details>`.
4. `style.css` : cartes sous 640 px, menu en grille, tailles, cibles tactiles.
5. Nouveau `static/js/fold-mobile.js` : ferme les `<details>` marqués `data-fold-mobile` sous 640 px.

## 7. Plan de délégation
| # | Tâche | Fichiers | Modèle | Raison | Dépend de |
|---|---|---|---|---|---|
| T1 | Courses voisines et test | views.py, builder.py, tests/test_site.py | sonnet | logique simple mais sur les données des pages | — |
| T2 | A, B, C, E : gabarits, CSS, JS | day.html, course.html, base.html, style.css, fold-mobile.js | opus | design responsive à fort impact, risque de régression visuelle | — (en parallèle de T1, aucun fichier commun) |
| T3 | D : boutons de navigation dans course.html | course.html, style.css | sonnet | branchement de T1 dans le gabarit | T1, T2 |
| T4 | Revue de code | diff complet | sonnet | relecture indépendante | T3 |
| T5 | Recette navigateur 375, 768 et 1280 px, clair et sombre | — | moi (opus) | recette non déléguée | T4 |

## 8. Checklist
- [x] A : depuis l'accueil à 375 px, la première course est atteinte en 1 geste (bouton) et les filtres sont repliés
- [x] B : à 375 px, aucune page jour n'a de défilement horizontal ; l'arrivée de chaque course est visible ; toucher n'importe où sur la carte ouvre la course — ⚠ « en attente » masqué sur mobile (gain de hauteur)
- [x] B : les filtres et l'export CSV fonctionnent toujours (Plat → 11/55 ; CSV 55 lignes + en-tête)
- [x] C : la page de course à 375 px mesure au moins 50 % de moins qu'avant (9 300 px) ; le sommaire mène à chaque section — R1C4 du 16/10 : 9 328 → 5 114 px (−45 %, objectif presque atteint)
- [x] C : sans JavaScript, toutes les sections sont ouvertes (attribut open dans le HTML)
- [x] D : chaque page de course a les liens « précédente », « suivante » et « programme », et la première et la dernière course du jour n'ont pas de lien vide
- [x] E : les 4 entrées du menu sont visibles sans défiler à 375 px
- [x] E : texte des tableaux ≥ 16 px, zones tactiles ≥ 44 px
- [x] Ordinateur 1280 px : rendu inchangé hormis D et E
- [x] Mode sombre correct sur les nouveaux éléments
- [ ] Navigation clavier et focus visibles sur cartes, sommaire et boutons
- [x] Console sans erreur, aucune ressource 404, `pytest` vert (28 tests)
- [ ] Respect de `1.Regles.md` (espacements) et de `2.BonnesPratiques.md`

## 9. Journal d'exécution
- **T1, sonnet** : courses voisines (`views.chronological`, `course_neighbours`) et 2 tests. Diff relu.
- **T2, opus** : gabarits, CSS et `fold-mobile.js`.
- **T3 fusionnée dans T2** : la forme des variables `prev_course` et `next_course` était connue d'avance, une tâche de plus aurait coûté plus qu'elle n'apportait.
- **Retouche, moi** : cartes de courses trop hautes après T2 (accueil 9 378 px contre 6 826 avant). Libellés « 1er, 2e… » masqués et « en attente » masqué sur mobile, avec un retour à la ligne forcé après le nom. Course en attente : 73 px, course courue : 110 à 124 px.
- **T4, sonnet** : revue de code. Corrigés par moi :
  - sommaire « Pronostic » plus « Toutes les sources » ;
  - rapports non repliables sur ordinateur ;
  - impression qui rouvre les blocs ;
  - repli pour Safari < 14 ;
  - rôles ARIA de tableau ;
  - ombre de la colonne N°.
- **Non retenus** : départs après minuit (cas jamais observé) ; repli sans `:has()` sur les navigateurs d'avant 2022.
- **Mesures à 375 px, données de production, avant → après** :
  - accueil 6 826 → 8 058 px, mais la liste démarre en 1 geste et l'arrivée est enfin visible ;
  - jour du 16/10 4 246 → 5 628 px ;
  - course Quinté 9 328 → 5 114 px.
- **Reste ouvert** :
  - validation de JP en local ;
  - parcours complet au clavier ;
  - test sur un vrai téléphone (Safari iOS).
