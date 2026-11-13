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

## N1 — Segmentation

La segmentation en lignes et en cellules est faite (`uv run python -m htr.segmentation.segment`) : 14/14 photos, 10 lignes par page, lignes gauche et droite appariées. Les crops sont **à valider visuellement avant tout appel de modèle** : `data/debug/index.html`, `data/rows/`, `data/cells/`. Les avertissements sont listés dans `data/segmentation/report.csv`.
