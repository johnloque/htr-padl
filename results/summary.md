# Synthèse de l'évaluation

Seuils provisoires : exactitude ≥ 95% (champs fermés, numériques, dates) ; CER ≤ 5% (nom, prenoms, lieu_naissance, departement_naissance) ; ≥ 90 % des erreurs signalées.

## Vue d'ensemble

| Stratégie | Modèle | JSON valide % | Lignes trouvées | Lignes en trop | Ligne exacte (structurés) % | s/ligne | tok/s | Mémoire Go | h pour 5000 lignes | Seuils exactitude | Seuils CER |
|---|---|---|---|---|---|---|---|---|---|---|---|
| N0 | churro-3b | 71.4 | 107/140 | 0 | 0.0 | 22.5 | 29.3 | 4.4 | 31.3 | ❌ | ❌ |
| N0 | gemma3-12b | 100.0 | 122/140 | 0 | 0.0 | 23.4 | 10.8 | 7.9 | 32.5 | ❌ | ❌ |
| N0 | qwen3-vl-8b | 100.0 | 140/140 | 0 | 0.7 | 18.8 | 17.3 | 6.7 | 26.1 | ❌ | ❌ |

## N0 — churro-3b

| Colonne | Type | Exact % | CER strict % | CER tolérant % | Invention % (n vides) | Omission % |
|---|---|---|---|---|---|---|
| numero | numerique | 57.1 | 29.6 | 28.6 | – (0) | 23.6 |
| nom | texte_court | 54.3 | 28.8 | 28.7 | – (0) | 23.6 |
| prenoms | texte_court | 66.4 | 27.4 | 27.0 | – (0) | 23.6 |
| profession | texte_court | 37.1 | 50.1 | 48.4 | – (0) | 23.6 |
| date_naissance | date | 59.3 | 87.8 | 72.5 | 0.0 (1) | 23.0 |
| lieu_naissance | texte_court | 7.9 | 88.0 | 84.5 | 0.0 (1) | 23.0 |
| departement_naissance | texte_court | 39.3 | 60.7 | 58.1 | 62.5 (8) | 42.4 |
| pays | ferme | 72.1 | 28.6 | 28.5 | – (0) | 23.6 |
| etat_civil | ferme | 57.9 | 268.9 | 203.0 | – (0) | 23.6 |
| admis_au_titre_de | ferme | 0.0 | 79.9 | 68.9 | – (0) | 23.6 |
| venant_de | texte_court | 36.4 | 71.5 | 68.7 | – (0) | 24.3 |
| religion | ferme | 71.4 | 28.2 | 28.1 | – (0) | 23.6 |
| adresse | texte_long | 0.0 | 52.6 | 46.2 | – (0) | 23.6 |
| categorie_medicale | ferme | 56.4 | 105.7 | 53.6 | – (0) | 23.6 |
| date_entree | date | 58.6 | 33.8 | 33.8 | – (0) | 23.6 |
| date_sortie | date | 45.0 | 56.1 | 51.1 | – (0) | 23.6 |
| nb_journees | numerique | 58.6 | 34.6 | 33.2 | 50.0 (2) | 23.9 |
| observations | texte_long | 9.3 | 88.8 | 86.1 | – (0) | 23.6 |

## N0 — gemma3-12b

| Colonne | Type | Exact % | CER strict % | CER tolérant % | Invention % (n vides) | Omission % |
|---|---|---|---|---|---|---|
| numero | numerique | 0.0 | 77.0 | 77.0 | – (0) | 12.9 |
| nom | texte_court | 5.0 | 74.4 | 73.5 | – (0) | 12.9 |
| prenoms | texte_court | 1.4 | 89.5 | 87.8 | – (0) | 17.9 |
| profession | texte_court | 1.4 | 93.7 | 91.2 | – (0) | 12.9 |
| date_naissance | date | 0.0 | 54.0 | 54.0 | 100.0 (1) | 12.9 |
| lieu_naissance | texte_court | 1.4 | 100.7 | 95.1 | 100.0 (1) | 12.9 |
| departement_naissance | texte_court | 1.4 | 92.6 | 89.0 | 87.5 (8) | 21.2 |
| pays | ferme | 76.4 | 23.5 | 23.4 | – (0) | 12.9 |
| etat_civil | ferme | 38.6 | 67.7 | 66.5 | – (0) | 12.9 |
| admis_au_titre_de | ferme | 0.0 | 96.0 | 88.1 | – (0) | 12.9 |
| venant_de | texte_court | 12.9 | 86.1 | 83.1 | – (0) | 12.9 |
| religion | ferme | 20.7 | 72.6 | 72.4 | – (0) | 25.7 |
| adresse | texte_long | 0.0 | 87.1 | 85.3 | – (0) | 25.7 |
| categorie_medicale | ferme | 4.3 | 95.7 | 95.7 | – (0) | 12.9 |
| date_entree | date | 0.0 | 47.1 | 47.1 | – (0) | 12.9 |
| date_sortie | date | 0.0 | 64.4 | 64.4 | – (0) | 12.9 |
| nb_journees | numerique | 0.0 | 88.8 | 88.8 | 100.0 (2) | 13.0 |
| observations | texte_long | 0.0 | 87.0 | 85.8 | – (0) | 12.9 |

## N0 — qwen3-vl-8b

| Colonne | Type | Exact % | CER strict % | CER tolérant % | Invention % (n vides) | Omission % |
|---|---|---|---|---|---|---|
| numero | numerique | 62.9 | 15.0 | 13.2 | – (0) | 0.0 |
| nom | texte_court | 62.9 | 8.9 | 8.6 | – (0) | 0.0 |
| prenoms | texte_court | 78.6 | 12.3 | 11.4 | – (0) | 0.0 |
| profession | texte_court | 35.7 | 37.7 | 35.7 | – (0) | 0.0 |
| date_naissance | date | 55.7 | 8.1 | 8.1 | 100.0 (1) | 0.0 |
| lieu_naissance | texte_court | 28.6 | 37.1 | 34.9 | 100.0 (1) | 0.0 |
| departement_naissance | texte_court | 66.4 | 24.0 | 22.2 | 100.0 (8) | 0.8 |
| pays | ferme | 94.3 | 6.3 | 6.1 | – (0) | 0.0 |
| etat_civil | ferme | 94.3 | 26.3 | 13.8 | – (0) | 0.0 |
| admis_au_titre_de | ferme | 33.6 | 59.2 | 43.6 | – (0) | 0.0 |
| venant_de | texte_court | 60.7 | 43.6 | 41.1 | – (0) | 7.1 |
| religion | ferme | 80.7 | 14.2 | 14.2 | – (0) | 7.1 |
| adresse | texte_long | 0.0 | 39.4 | 33.5 | – (0) | 0.0 |
| categorie_medicale | ferme | 87.1 | 12.9 | 12.9 | – (0) | 0.0 |
| date_entree | date | 74.3 | 7.3 | 7.3 | – (0) | 0.0 |
| date_sortie | date | 38.6 | 36.7 | 35.6 | – (0) | 0.0 |
| nb_journees | numerique | 61.4 | 19.9 | 19.9 | 50.0 (2) | 0.0 |
| observations | texte_long | 5.7 | 42.3 | 39.7 | – (0) | 2.9 |
