# Rapport

Données : 14 doubles pages de `gold/` (140 lignes). Métriques détaillées dans `results/summary.md`, `results/metrics.csv` ; erreurs cellule par cellule dans `results/errors.csv`.

Seuils provisoires : exactitude ≥ 95 % (champs fermés, numériques, dates), CER ≤ 5 % (nom, prénoms, lieu et département de naissance).

## N0 — Page entière, un seul appel

Paramètres : photo redimensionnée à 2048 px de côté, temperature 0,3, top_k 20, top_p 0,9, repeat_penalty 1,05, num_ctx 16384, num_predict 8192, seed 42 ; prompt `configs/prompts/n0_page.fr.txt` ; sortie JSON contrainte par schéma (Ollama `format`).

### Vue d'ensemble

| Modèle | JSON valide | Lignes trouvées | s/ligne | tok/s | Mémoire | h pour 5000 lignes | Seuils |
|---|---|---|---|---|---|---|---|
| Qwen3-VL 8B | 100 % | 140/140 | 18,8 | 17,3 | 6,7 Go | 26 | ❌ tous |
| Gemma 3 12B | 100 % | 122/140 | 23,4 | 10,8 | 7,9 Go | 32 | ❌ tous |
| Churro 3B (Q8_0) | 71 % | 107/140 | 22,5 | 29,3 | 4,4 Go | 31 | ❌ tous |

### Exactitude par colonne (% de cellules exactes, CER tolérant entre parenthèses pour le texte)

| Colonne | Qwen3-VL 8B | Gemma 3 12B | Churro 3B |
|---|---|---|---|
| numéro | 62,9 | 0,0 | 57,1 |
| nom | 62,9 (CER 8,6) | 5,0 (73,5) | 54,3 (28,7) |
| prénoms | 78,6 (11,4) | 1,4 (87,8) | 66,4 (27,0) |
| date de naissance | 55,7 | 0,0 | 59,3 |
| lieu de naissance | 28,6 (34,9) | 1,4 (95,1) | 7,9 (84,5) |
| département | 66,4 (22,2) | 1,4 (89,0) | 39,3 (58,1) |
| pays | 94,3 | 76,4 | 72,1 |
| état civil | 94,3 | 38,6 | 57,9 |
| catégorie médicale | 87,1 | 4,3 | 56,4 |
| date d'entrée | 74,3 | 0,0 | 58,6 |
| date de sortie | 38,6 | 0,0 | 45,0 |
| nb journées | 61,4 | 0,0 | 58,6 |
| adresse (CER) | 33,5 | 85,3 | 46,2 |
| observations (CER) | 39,7 | 85,8 | 86,1 |

### Erreurs principales

- **Qwen3-VL 8B** : lit la structure correctement (10 lignes partout, alignement juste), mais confond les lettres sur les mots manuscrits : Lescun → « Leceux », Montesquieu-Volvestre → « Montpellier-Ville », Mounicoux → « Mouricoux ». Les chiffres posent problème : en date de sortie, 02/07/1935 → « 31/04/35 » ; en numéro, 3331 → « 3334 ». Les colonnes de droite, plus petites et plus loin du début du prompt, sont nettement moins bonnes.
- **Gemma 3 12B** : **invente** le contenu. Les numéros (151, 152… au lieu de 3241…), les noms et les dates sont plausibles mais faux. Il saute aussi des lignes (7 à 10 par page). La sortie est inutilisable, ce qui n'est pas un problème d'évaluation.
- **Churro 3B** : bonne lecture du manuscrit quand il termine (par exemple « Etchepare », « Cambo les Bains »). Il sort en revanche du format demandé : dates en toutes lettres (« 30 Septembre 1904 »), « à Tarbes ». Surtout, sur 4 pages sur 14, il **part en boucle** (« Il a reconnu son erreur. » répété) jusqu'à la limite de 8192 tokens : JSON tronqué et lignes perdues. Sur la photo 12, il s'arrête après 4 lignes.
- **Biais de la référence** : le gold est une transcription éditoriale, pas littérale. Abréviations développées (« St Denis » → « Saint-Denis »), adresses reformulées, années complétées en date de sortie. Une partie des erreurs comptées en texte court et en texte long vient de cette différence. Elle ne suffit pas à expliquer l'écart aux seuils.

### Conclusion N0

Aucun modèle n'approche les seuils. Qwen3-VL 8B est le seul candidat sérieux. Au rythme actuel, il faudrait environ 26 h pour 5000 lignes, avec un taux d'erreur incompatible avec un usage sans relecture. N0 est donc insuffisant, ce qui justifie N1 : des crops par ligne et par cellule, pour donner au modèle des images plus grandes et un contexte plus court.

## N1 — Une ligne, un appel

### Segmentation

La segmentation en lignes et en cellules est faite (`uv run python -m htr.segmentation.segment`) : 14/14 photos, 10 lignes par page, lignes gauche et droite appariées (détail dans `docs/segmentation.md`).

### Protocole

Deux variantes, mêmes paramètres d'inférence que N0 (temperature 0,3, top_k 20, top_p 0,9, repeat_penalty 1,05, seed 42), sortie JSON contrainte par schéma, crops en pleine résolution :
- **ligne** (`<modèle>`) : un appel sur la ligne complète (≈ 3400×290 px, gauche et droite côte à côte), tous les champs, `num_predict` 1024 ; prompt `configs/prompts/n1_ligne.fr.txt` ;
- **demi** (`<modèle>-demi`) : deux appels, demi-ligne gauche (identité, ≈ 1650×290 px) puis droite (séjour), `num_predict` 768 ; prompts `n1_gauche.fr.txt` et `n1_droite.fr.txt`.

L'évaluateur a été corrigé à cette occasion. Un sigle écrit lettre par lettre (« A. M. G. ») est désormais égal à « AMG » en comparaison tolérante. Les durées de génération aberrantes renvoyées par Ollama (plus longues que l'appel) sont ignorées dans le calcul des tok/s. Les chiffres N0 de `results/` sont recalculés avec cette version (effet marginal).

### Vue d'ensemble

| Stratégie / modèle | JSON valide | Lignes trouvées | Ligne exacte (champs structurés) | s/ligne | tok/s | Mémoire | h pour 5000 lignes | Seuils |
|---|---|---|---|---|---|---|---|---|
| N0 Qwen3-VL 8B (rappel) | 100 % | 140/140 | 0,7 % | 18,8 | 17,3 | 6,7 Go | 26 | ❌ tous |
| N1 Qwen3-VL 8B, ligne | 93 % | 140/140 | 6,4 % | 28,8 | 18,9 | 6,7 Go | 40 | ❌ tous |
| N1 Qwen3-VL 8B, demi | 100 % | 140/140 | 5,7 % | 37,4 | 21,1 | 6,4 Go | 52 | ❌ tous |
| N1 Churro 3B, ligne | 100 % | 140/140 | 1,4 % | 15,1 | 36,9 | 4,4 Go | 21 | ❌ tous |
| N1 Churro 3B, demi | 100 % | 140/140 | 9,3 % | 20,9 | 38,0 | 4,4 Go | 29 | ❌ tous |
| N1 Gemma 3 12B, ligne | 93 % | 140/140 | 0,0 % | 41,7 | 10,0 | 7,9 Go | 58 | ❌ tous |
| N1 Gemma 3 12B, demi | 93 % | 140/140 | 0,7 % | 43,6 | 11,8 | 7,9 Go | 61 | ❌ tous |

« JSON valide » à 93 % : une ligne sur la photo concernée a produit un JSON tronqué ou réparé (avertissements dans `results/runs/N1/*.json`).

### Exactitude par colonne (% de cellules exactes, CER tolérant entre parenthèses pour le texte)

| Colonne | N0 Qwen | N1 Qwen ligne | N1 Qwen demi | N1 Churro ligne | N1 Churro demi | N1 Gemma ligne | N1 Gemma demi |
|---|---|---|---|---|---|---|---|
| numéro | 62,9 | 70,0 | 77,9 | 92,9 | **93,6** | 0,7 | 30,0 |
| nom | 62,9 (8,6) | 70,0 (13,0) | 60,0 (12,7) | **80,7 (3,7)** | 70,7 (6,8) | 23,6 (32,5) | 45,7 (24,9) |
| prénoms | 78,6 (11,4) | 80,7 (14,0) | 87,9 (7,2) | 95,0 (3,8) | **95,7 (2,3)** | 22,1 (66,6) | 68,6 (21,7) |
| profession | 35,7 (35,7) | 42,9 (42,1) | 54,3 (18,8) | 62,1 (18,3) | **69,3 (11,0)** | 1,4 (90,1) | 20,0 (69,0) |
| date de naissance | 55,7 | 74,3 | 75,7 | **94,3** | 92,9 | 0,0 | 53,6 |
| lieu de naissance | 28,6 (34,9) | 50,7 (24,0) | **60,0 (18,2)** | 38,6 (45,2) | 17,1 (73,7) | 1,4 (94,3) | 27,9 (39,0) |
| département | 66,4 (22,2) | 80,0 (15,9) | **84,3 (11,3)** | 50,7 (52,8) | 67,9 (30,5) | 10,0 (80,8) | 52,9 (38,5) |
| pays | 94,3 | 95,0 | 95,0 | 94,3 | **96,4** | 91,4 | 95,7 |
| état civil | **94,3** | 65,0 | 42,9 | 93,6 | 89,3 | 52,9 | 55,7 |
| admis au titre de | 33,6 | 37,9 | **49,3** | 3,6 | 17,9 | 2,1 | 6,4 |
| venant de | **60,7 (41,1)** | 17,1 (82,9) | 36,4 (56,1) | 7,1 (99,1) | 22,1 (75,2) | 0,0 (93,3) | 4,3 (90,1) |
| religion | 80,7 | 65,7 | 70,7 | **94,3** | 89,3 | 14,3 | 55,7 |
| adresse (CER) | 33,5 | 36,2 | 25,6 | 36,2 | **24,1** | 77,3 | 53,9 |
| catégorie médicale | 87,1 | 72,9 | 75,0 | 82,1 | **88,6** | 20,7 | 55,7 |
| date d'entrée | 74,3 | 85,7 | 90,7 | 86,4 | **96,4** | 7,1 | 51,4 |
| date de sortie | 38,6 | 63,6 | 81,4 | 82,9 | **90,7** | 3,6 | 42,9 |
| nb journées | 61,4 | 73,6 | 84,3 | **93,6** | **93,6** | 7,9 | 59,3 |
| observations (CER) | 39,7 | 21,6 | 14,4 | 11,8 | **10,3** | 82,4 | 48,1 |

### Erreurs principales

- **Gain net sur les champs courts, les dates et les nombres.** Avec Churro 3B, le numéro, les dates d'entrée et de naissance et le nombre de journées passent de 57-59 % (N0) à 93-96 %. La date d'entrée de Churro demi (96,4 %) est la seule colonne au-dessus du seuil de 95 %. Les observations en cursive passent de 86 % à 10 % de CER. Churro, qui bouclait en N0, ne boucle plus : le contexte court fonctionne.
- **Décalage de colonnes sur la page de gauche.** La case « Admis au titre de » tient sur deux lignes (« A.M.G. » puis le département). Les modèles mettent souvent le département dans `venant_de` et décalent ou vident `etat_civil`. C'est la cause de la chute de `venant_de` (17 % pour Qwen ligne, 7 % pour Churro ligne) et de `etat_civil` chez Qwen (94 % → 43-65 %). « Admis au titre de » se réduit souvent à « A.M.G. » sans département. Ce défaut tient à la sortie « tous les champs d'un coup », pas à la lecture.
- **Churro** lit très bien le manuscrit, mais reprend des formes non normalisées : mois en lettres, « à Lescun », et lieu de naissance confondu avec le département (17 % exact en demi).
- **Qwen3-VL** reste meilleur sur les lieux et départements, mais il est derrière Churro partout ailleurs.
- **Gemma 3** : Ollama ramène toute image à 896×896, donc une ligne de 3400×290 px n'a plus que ≈ 78 px de haut. Les résultats sont inexploitables en ligne complète et faibles en demi-ligne. Ce n'est pas un verdict sur le modèle, mais sur l'appariement entre ce format d'image et des crops très allongés.
- **Variante demi contre ligne** : elle est meilleure pour presque toutes les colonnes et tous les modèles, au prix d'environ 30 % de temps en plus (deux encodages d'image).

### Conclusion N1

N1 apporte un gain important sur N0. Churro 3B en demi-lignes devient le meilleur candidat (29 h pour 5000 lignes sur le Mac). Mais aucun seuil n'est atteint : champs fermés à 89-94 %, numériques et dates à 91-96 %, CER du nom à 6,8 % et du lieu de naissance à 74 %. Les erreurs restantes viennent surtout du **regroupement des champs dans un seul appel** (décalages de colonnes, formats non respectés). C'est ce que vise N2 (une case, un appel, prompts et vocabulaires spécialisés).

## N2 — Une case, un appel

*En cours d'exécution.*
