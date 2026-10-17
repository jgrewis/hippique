# Plan — Charte graphique Francis Turf

Source : `Francis-Turf-charte-graphique.pdf` + `charte-francis-turf.zip` (tokens.css, tokens.json, 10 fiches composants).

## 1. Résumé des demandes

1. Le site s'appelle désormais **Francis Turf** (nom visible : titre, en-tête, favicon, README, documentation).
2. Appliquer la palette de la charte (crème, vert pelouse, sable, brun terre, or), thème clair **et** sombre.
3. Appliquer la typographie : Fraunces (titres, noms de course, numéros d'arrivée, chiffres clés), Inter (texte, tableaux, navigation), échelle `display-xl` → `caption`.
4. Appliquer espacements (grille 8pt), rayons (8/16/24/pilule), ombres, conteneur 1200px, marges 16/32/48px.
5. Restyler les composants existants selon leurs fiches : Navigation (pastille couleur par rubrique, soulignement 3px du lien actif), Bouton (pilule, principal / secondaire sable / discret), Badge, TableProgramme (ligne de réunion en Fraunces), FicheCourse (faits `dl`, arrivée officielle avec 1re place en or), TablePartants (musique, lignes alternées), état vide de Fiabilité, Pied de page (fond vert profond, numéro d'aide en Fraunces).
6. **Ajouter** les pastilles de discipline (Attelé, Monté, Plat, Obstacle) dans le programme, la carte Quinté+ et la fiche course.
7. **Ajouter** les barres de probabilité dans le tableau des partants (modèle en `primary`, marché en `accent-text`) avec légende.
8. **Ajouter** la carte Quinté+ « hero » sur la page Programme (fond vert profond, motif feuille décoratif, arrivée en cases, gagnant en or, bouton secondaire sable « Voir la course »).
9. **Ajouter** un bouton de bascule thème clair / sombre dans l'en-tête (`data-theme`, mémorisé dans le navigateur, suit le système par défaut).

## 2. Hors périmètre

- Renommage du dépôt GitHub et de l'URL `jgrewis.github.io/hippique/` (arbitrage : on garde l'adresse, rien ne casse).
- Variables d'environnement `HIPPIQUE_*`, user-agent de collecte, noms de modules Python : internes, invisibles, inchangés.
- Tuiles rubriques (TuileRubrique) et cartes indicateurs de Fiabilité : non demandées ; la navigation couvre déjà l'accès aux rubriques et la page Fiabilité reste en tableaux. Les tokens `tool-*` sont quand même posés (pastilles de navigation).
- Logique de collecte, modèle, données : aucun changement.

## 3. Décisions et arbitrages

**Tranchés par le client**
- Nom : visible seulement (dépôt et URL inchangés).
- Polices : auto-hébergées en woff2 dans `assets/fonts/` → CSP `'self'` et promesse « sans traceur » préservées. Pas de lien Google Fonts.
- Ajouts retenus : pastilles discipline, barres de probabilité, carte Quinté+ hero, bascule de thème.

**Décidées seul**
- Les tokens de `tokens.css` sont repris tels quels dans `style.css` (pas de fichier CSS supplémentaire : une requête de moins). Les anciennes variables (`--text`, `--muted`, `--accent`…) sont renommées vers les noms de la charte (`--ink`, `--ink-muted`, `--primary`…).
- Le sable `accent` n'est jamais utilisé en texte sur fond clair : `accent-text` à la place (écart volontaire de la charte).
- Discipline « Obstacle » (haies, steeple, cross regroupés à la collecte) → pastille `disc-obstacle` libellée « Obstacle ».
- Numéros de chevaux (tapis de selle) : case `radius-sm` en `surface-sunken` + texte `ink` hors podium ; la 1re place en `gold`/`on-gold`. On abandonne le tapis vert plein partout (trop de vert, contraire à « la donnée d'abord »).
- Signature « lice » sous l'en-tête et bordure gauche `.card.highlight` supprimées (la charte interdit la bordure gauche colorée).
- Bascule de thème : script externe `theme.js` (CSP sans `unsafe-inline`). Le thème choisi est appliqué par le script en `<head>` sans `defer` pour éviter le flash. Stockage `localStorage` dans un try/catch : sans stockage, le thème suit le système.
- Favicon : feuille stylisée + « F » en crème sur vert hero.
- Polices limitées aux graisses 400 et 600 (charte), sous-ensemble latin.

## 4. Points de risque

- **Tests** `tests/test_site.py` peuvent vérifier des classes ou le titre « Hippique » → relancer la suite, adapter seulement ce qui relève du renommage.
- **Contraste sombre** : `tool-*` et `disc-*` sombres passent du contenu foncé ; vérifié via les valeurs de la charte (calculées WCAG 2.2).
- **Tableaux larges sur mobile** : la charte demande des colonnes figées (Course, Heure, Nom). Colonnes collantes en CSS (`position: sticky`) sur les 1 à 2 premières colonnes seulement, pour ne pas manger l'écran à 375px.
- **Barres de probabilité dans l'export CSV** : les barres sont décoratives (`aria-hidden`), l'export lit le texte de la cellule → vérifier que le CSV garde « 28,0 % » et pas de bruit.
- **Flash de thème** : script bloquant minimal en `<head>`.
- **Poids des polices** : ~4 fichiers woff2 latin, ~150 Ko au total, `font-display: swap`.

## 5. Approche technique

Fichiers touchés :
- `config.py` (SITE_TITLE), `README.md`, `DOCUMENTATION.md` (mentions du nom).
- `site_builder/static/css/style.css` (réécriture des tokens + composants).
- `site_builder/static/fonts/*.woff2` (nouveau), `site_builder/static/favicon.svg`, `site_builder/static/js/theme.js` (nouveau).
- `site_builder/templates/base.html` (nav pastilles, bascule thème, pied de page), `day.html` (carte hero, pastilles discipline), `course.html` (faits, arrivée, barres, discipline), `_macros.html` (macro `discipline_badge`, `proba_bar`), `reliability.html` / `empty.html` si besoin.
- `site_builder/template_filters.py` : filtre `disc_class` (Attelé/Monté → trot, Plat → plat, Obstacle → obstacle).
- Vérifier que le builder copie bien `static/fonts/` (copie récursive de `static/` ?).

Tranches :
1. Renommage + polices + tokens + base (nav, boutons, pied de page, thème).
2. Programme : carte Quinté+ hero, TableProgramme, pastilles discipline.
3. Fiche course : faits, arrivée, TablePartants avec barres de probabilité.
4. Fiabilité, Archives, états vides, impression.
5. Tests, build, recette navigateur (375 / 768 / 1280, clair / sombre).

## 6. Checklist

**Demandes**
- [x] « Francis Turf » visible dans l'en-tête, le `<title>`, le favicon, README et DOCUMENTATION ; plus aucune mention visible « Hippique » sur le site généré
- [x] Palette claire = valeurs de `tokens.css` (vérifiée par `getComputedStyle`)
- [x] Palette sombre appliquée par `prefers-color-scheme` et par `data-theme="dark"`
- [x] Fraunces sur h1/h2/noms de course/numéros d'arrivée, Inter ailleurs, servies depuis `assets/fonts/` (aucune requête externe)
- [x] Échelle typographique : h1 48/56 desktop (36/44 tablette, 32/40 mobile), h2 24/32, body 16/24, cellules 14/20, en-têtes de colonnes 13/16
- [x] Conteneur 1200px max, marges 16/32/48px
- [x] Navigation : pastille couleur par rubrique, lien actif souligné 3px dans sa couleur, `aria-current="page"`
- [x] Boutons pilule : principal, secondaire sable, discret ; focus 2px décalé 2px
- [x] Badges : paris Quinté+ en sable, autres en contour
- [x] Pastilles discipline (Attelé, Monté, Plat, Obstacle) dans programme, carte Quinté+, fiche course
- [x] Ligne de réunion en `surface-sunken` + Fraunces
- [x] Carte Quinté+ hero : fond vert profond, nom en `display-lg`, métadonnées à points médians, arrivée en cases avec gagnant en or, heure de départ si pas d'arrivée, motif feuille `aria-hidden`, bouton sable « Voir la course »
- [x] Fiche course : faits `dl`, arrivée officielle avec rang en disque et 1re place en or
- [x] Tableau des partants : barres modèle (`primary`) et marché (`accent-text`) + valeur + légende ; musique victoires en `primary` gras, D/A/T en `danger` gras
- [x] Bascule de thème dans l'en-tête, mémorisée, sans flash au chargement, libellé accessible
- [x] Pied de page fond `hero`, état de collecte en toutes lettres, message jeu responsable + numéro en Fraunces

**Référentiel**
- [x] Contrastes ≥ 4,5:1 texte, ≥ 3:1 contrôles, dans les deux thèmes (paires de couleurs reprises telles quelles de la charte, qui publie les ratios calculés ; pas de nouvelle mesure outillée)
- [x] Couleur jamais seule (libellé sur chaque pastille, signe +/− sur gains/pertes)
- [x] Chiffres tabulaires et alignés à droite dans tous les tableaux
- [x] Aucune bordure gauche colorée, aucun émoji
- [x] Cibles tactiles ≥ 44px
- [x] `prefers-reduced-motion` respecté

**Vérification humaine**
- [x] 375px : pas de scroll horizontal de page, nav lisible, tableaux défilent dans leur conteneur avec colonne(s) figée(s)
- [x] 768px et 1280px : mise en page correcte
- [x] Thème clair et sombre visuellement corrects sur Programme, Course, Fiabilité, Archives, Méthode (Fiabilité vue en état vide uniquement : la base locale n'a ni test historique ni résultats réels ; le format « +12,3 % / −4,0 % » est vérifié par le filtre seul)
- [x] Navigation clavier : lien d'évitement en premier, focus visible partout, bascule thème au clavier
- [x] Filtres, saut de date et export CSV fonctionnent toujours ; CSV sans bruit des barres
- [x] Console sans erreur, aucune 404 (polices comprises)
- [x] `pytest` vert

## 7. Notes de développement

- Correctif hors charte trouvé en recette : les séparateurs « - » réservés aux lecteurs d'écran (`.sr-only`, positionnés en absolu) dans les arrivées sortaient du conteneur défilant des tableaux et élargissaient la page sur mobile (fenêtre de 1 050 px au lieu de 375). `.table-wrap` est désormais `position: relative`. Le défaut existait avant la refonte.
- Colonnes figées sur mobile : seule la première colonne (code course / numéro) est figée, plus l'intitulé de réunion (`.group-label` collant), pour laisser de la place aux données à 375 px.
- Barres de probabilité en `<progress>` : la CSP interdit les styles en ligne, donc pas de `style="width:…"`. Échelle plafonnée à 50 %. L'export CSV ne lit que la valeur imprimée (vérifié : « 30,2 % »).
- Bascule de thème réduite à l'icône sous 1 024 px (nom accessible dans `aria-label`).
- Export CSV : les nombres signés « +12,3 % » ne sont plus préfixés d'une apostrophe anti-formule.
- Navigation mobile : les quatre rubriques ne tiennent pas à 375 px, la liste défile horizontalement comme le prévoit la charte.
- Non testé : zoom navigateur 200 %, lecteur d'écran réel.
