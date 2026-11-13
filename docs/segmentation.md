# Segmentation des doubles pages (N1)

Découpe chaque photo de double page du registre en **2 pages → 7 colonnes par page → 10 lignes → cellules**, et exporte les crops qui servent d'entrée aux modèles à partir de N1.

- Code : `src/htr/segmentation/segment.py` (détection, export) et `src/htr/segmentation/click_corners.py` (repli manuel)
- Paramètres : `configs/segmentation.yaml`
- Commande : `uv run python -m htr.segmentation.segment [--input gold/photos] [--only "1491_W_1 (9)"]`

Principe général : on va du plus grossier au plus fin, et chaque étape s'appuie sur la **grille imprimée** du formulaire, jamais sur l'écriture. Toute page dont la structure ne correspond pas à l'attendu est **signalée** et n'est pas exportée.

## Vue d'ensemble

```
photo ─► binarisation + masques de traits longs
      ─► reliure (coupe gauche / droite)
      ─► pour chaque page : coins du tableau ─► redressement ─► 7 colonnes (gabarit) ─► 10 lignes (suivi de traits)
      ─► appariement des lignes gauche / droite
      ─► export des crops + images de contrôle
```

## 0. Préparation

- La détection travaille sur la photo réduite de moitié (`work_scale: 0.5`). Les crops sont ensuite découpés dans la **photo d'origine**, sans perte de résolution.
- **Binarisation de Sauvola** (`binarization`) : seuil local, robuste au papier jauni et à l'éclairage inégal.
- **Masques de traits longs** (`lines`) : une ouverture morphologique avec un noyau horizontal (`h_open_len`), puis vertical (`v_open_len`), ne garde que les traits droits plus longs que n'importe quel tracé de plume. Une fermeture (`close_len`) comble les petites interruptions. Le noyau vertical est plus court pour tolérer l'inclinaison due à la perspective.

## 1. Reliure

Fonction `find_gutter`, paramètres `gutter`.

Les réglures horizontales des deux pages **ne sont pas à la même hauteur**. Pour chaque abscisse de la bande centrale (`search_band`), on compare le profil vertical des traits juste à gauche et juste à droite (`offset_frac`). Sur une même page, les deux profils sont corrélés ; à la pliure, ils ne le sont plus. On retient le minimum de corrélation.

Cette position est ensuite recalée sur la colonne la plus sombre à ± `refine_frac` (ombre de la pliure, points de couture), après avoir effacé les fins traits imprimés par fermeture morphologique. Chaque page est découpée avec un petit débord sur l'autre (`overlap_frac`), pour ne pas perdre le bord du tableau.

Approches essayées sans succès : colonne la plus sombre seule, minimum de couverture des traits horizontaux.

## 2. Coins du tableau

Fonction `detect_corners`.

- **Bords latéraux** : les traits verticaux du tableau vont de l'en-tête au bas de page. On garde les plus longs qui **commencent et finissent ensemble**, ce qui écarte la tranche du livre et les traits parasites. Le plus à gauche et le plus à droite donnent les bords.
- **Côté reliure**, le trait de bord se courbe et se perd dans le pli. On prend le bord de la découpe, parallèle au trait fiable le plus proche ; l'étape 4 retrouvera le vrai bord dans la page redressée.
- **Bords haut et bas** :
  - leur pente est la **médiane des pentes** des longues réglures horizontales, une mesure très stable ;
  - leur position est la médiane des extrémités des traits verticaux du tableau ;
  - puis chaque bord est recalé sur le trait horizontal le plus marqué à proximité (`refine_hline`).
- Les intersections des quatre droites donnent les coins haut-gauche, haut-droit, bas-droit et bas-gauche.

## 3. Redressement

Fonction `warp`, paramètre `table.warp_margin_frac`.

Une homographie transforme le quadrilatère du tableau en rectangle droit, avec une marge pour garder les bords visibles. Elle corrige la perspective et la rotation de la prise de vue.

## 4. Colonnes : ajustement sur un gabarit

Fonction `detect_columns`, paramètres `columns_template` et `table.column_*`.

Toutes les pages sont le même formulaire imprimé. La position relative des 8 traits de colonne a été mesurée sur 6 pages bien segmentées (écart-type < 0,006 de la largeur) et sert de **gabarit**, un pour la page gauche et un pour la page droite.

1. Les traits verticaux candidats sont les pics du profil de couverture du masque vertical (`column_min_coverage`).
2. On cherche l'échelle et le décalage qui alignent le plus de candidats sur le gabarit, à `column_template_tol` près. Le tableau doit occuper au moins `column_min_width_frac` de la largeur.
3. Un trait non vu (pli, encre pâle) est placé à sa position prévue. Au-delà de `column_max_missing` traits non vus, la page est signalée.

Noms des colonnes exportées (`columns`) :

| Page | Colonnes |
|---|---|
| gauche | numero, noms_prenoms, profession, naissance, etat_civil, admis_au_titre_de, venant_de |
| droite | religion, adresse, categorie_medicale, date_entree, date_sortie, nb_journees, observations |

## 5. Lignes : suivi de traits

Fonction `detect_rows`, paramètres `table.row_*`.

C'est l'étape la plus délicate. Les séparateurs sont fins, parfois en pointillés, et se courbent près de la reliure ; certaines cases (Observations surtout) contiennent des réglures internes.

1. **Carte de réponse** (`line_response`) : un black-hat avec un élément vertical de `row_blackhat_px` fait ressortir les traits sombres plus fins que cette hauteur, lissés horizontalement.
2. **Suivi par programmation dynamique** (`trace_paths`) : de gauche à droite, par pas de `row_dp_step_px`, on cherche pour chaque ordonnée d'arrivée le chemin de réponse maximale, en pénalisant chaque pixel de déplacement vertical (`row_dp_penalty`). Le chemin épouse la courbure et franchit les trous des pointillés.
3. **Critère « toutes les colonnes »** :
   - un trait est « présent » là où la réponse dépasse `row_on_factor` fois la médiane de la page ;
   - un séparateur doit être présent sur au moins `row_min_coverage` de son chemin **dans chacune des 7 colonnes** ;
   - une réglure interne à une case ne traverse pas les colonnes voisines : elle est éliminée.
4. **Pas régulier** : parmi les candidats, on cherche 11 séparateurs consécutifs dont le coefficient de variation du pas est ≤ `row_pitch_cv_max`. On préfère la suite qui se termine au bas du tableau trouvé à l'étape 2, sinon la plus basse.
5. **Contrôles** :
   - **En-tête** : il doit y avoir au moins `row_header_min_frac` × pas au-dessus du premier séparateur. Ce contrôle détecte un décalage d'une ligne, qui serait silencieux sinon (cas rencontré sur la page droite de la photo 9).
   - **Bord bas peu visible** : contre la pliure, le bord bas peut n'être vu que dans une partie des colonnes. Il est accepté s'il est vu dans au moins la moitié d'entre elles, puis extrapolé dans les autres à partir du séparateur précédent et du pas médian de la colonne. Cela produit l'avertissement « bord bas extrapolé ».
   - **Cohérence par colonne** : si l'écart entre deux séparateurs s'éloigne de plus de `row_gap_tol` du pas médian dans certaines colonnes seulement, c'est que le chemin s'est accroché à une réglure interne. Le séparateur est recalé d'après le décalage relatif des autres colonnes (avertissement « séparateur recalé »). Au-delà de `row_max_fixes` recalages, la page est signalée.

Chaque séparateur est enregistré **colonne par colonne** (médiane du chemin dans la colonne), ce qui conserve la courbure.

Approches essayées sans succès : grille ancrée sur le bas de page, suivi de bas en haut par colonne puis par bande, détection en pleine résolution.

## 6. Appariement gauche / droite

Fonction `segment_photo`, paramètre `table.pair_max_rel_diff`.

Les positions des séparateurs sont ramenées à la hauteur du tableau (de 0 en haut à 1 en bas) sur chaque page. Si l'écart maximal entre gauche et droite dépasse `pair_max_rel_diff` (4 %), la photo est signalée : la ligne *i* de gauche ne serait plus le même patient que la ligne *i* de droite.

## 7. Export

Fonction `export_crops`, paramètres `export`. L'export n'a lieu que si la photo n'est pas signalée.

| Sortie | Contenu |
|---|---|
| `data/cells/<photo>/rNN/<colonne>.jpg` | Cellule : bande entre les séparateurs haut et bas **propres à la colonne**, avec une marge verticale (`row_pad_frac`) et horizontale (`cell_pad_frac`) |
| `data/rows/<photo>/rNN_left.jpg`, `rNN_right.jpg` | Demi-ligne : cellules juxtaposées et ramenées à la hauteur médiane, ce qui redresse la courbure par morceaux |
| `data/rows/<photo>/rNN.jpg` | Ligne complète, gauche et droite côte à côte |
| `data/debug/<photo>/overview.jpg` | Photo avec la reliure et les quadrilatères des tableaux |
| `data/debug/<photo>/page_left.jpg`, `page_right.jpg` | Pages redressées avec colonnes et séparateurs |
| `data/debug/<photo>/rows.jpg` | Planche des 10 lignes, pour relecture |
| `data/debug/index.html` | Page locale de relecture de toutes les photos |
| `data/segmentation/<photo>.json` | Statut, drapeaux, avertissements, reliure, coins, colonnes, séparateurs |
| `data/segmentation/report.csv` | Une ligne par photo |

## Statuts, drapeaux et avertissements

- **`ok`** : structure conforme, crops exportés. Des *avertissements* peuvent accompagner ce statut (bord bas extrapolé, séparateur recalé, dernier séparateur loin du bas estimé). Ils sont à vérifier visuellement, mais la page reste exploitable.
- **`flagged`** : un *drapeau* a été levé et rien n'est exporté. Exemples : pas assez de traits verticaux, pas assez de séparateurs traversants, aucune suite régulière, pas d'en-tête, trop de recalages, lignes gauche et droite non appariées.

## Repli manuel

```
uv run python -m htr.segmentation.click_corners "1491_W_1 (9)"
```

Pour chaque page (gauche puis droite), on clique les coins du tableau, en-tête compris, dans l'ordre haut-gauche, haut-droit, bas-droit, bas-gauche. La touche `r` recommence, `Entrée` valide, `Échap` annule.

Les coins sont écrits dans `data/corners/<photo>.json` et remplacent l'étape 2 au prochain lancement de la segmentation. Les étapes 3 à 7 s'appliquent ensuite normalement.

## État sur le gold

14/14 photos sont au statut `ok` et ont été vérifiées visuellement. Avertissements restants :

- photos 9 et 10, page droite : bord bas extrapolé dans la colonne 1 ;
- photo 12, page droite : bord bas extrapolé dans les colonnes 5 et 6, séparateur 10 recalé dans la colonne 7 ;
- photos 5 et 6, page gauche : dernier séparateur loin du bas estimé du tableau.

Limites observées : sur la photo 12, ligne 10, la dernière ligne d'Observations touche le bas du crop ; sur certaines pages, le texte de la colonne Religion déborde en partie dans la pliure.
