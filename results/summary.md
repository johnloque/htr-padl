# Synthèse de l'évaluation

Seuils provisoires : exactitude ≥ 95% (champs fermés, numériques, dates) ; CER ≤ 5% (nom, prenoms, lieu_naissance, departement_naissance) ; ≥ 90 % des erreurs signalées.

## Vue d'ensemble

| Stratégie | Modèle | JSON valide % | Lignes trouvées | Lignes en trop | Ligne exacte (structurés) % | s/ligne | tok/s | Mémoire Go | h pour 5000 lignes | Seuils exactitude | Seuils CER |
|---|---|---|---|---|---|---|---|---|---|---|---|
| N0 | churro-3b | 71.4 | 107/140 | 0 | 0.7 | 22.5 | 29.3 | 4.4 | 31.3 | ❌ | ❌ |
| N0 | gemma3-12b | 100.0 | 122/140 | 0 | 0.0 | 23.4 | 10.8 | 7.9 | 32.5 | ❌ | ❌ |
| N0 | qwen3-vl-8b | 100.0 | 140/140 | 0 | 0.7 | 18.8 | 17.3 | 6.7 | 26.1 | ❌ | ❌ |
| N1 | churro-3b | 100.0 | 140/140 | 0 | 1.4 | 15.1 | 36.9 | 4.4 | 20.9 | ❌ | ❌ |
| N1 | churro-3b-demi | 100.0 | 140/140 | 0 | 9.3 | 20.9 | 38.0 | 4.4 | 29.0 | ❌ | ❌ |
| N1 | gemma3-12b | 92.9 | 140/140 | 0 | 0.0 | 41.7 | 10.0 | 7.9 | 57.9 | ❌ | ❌ |
| N1 | gemma3-12b-demi | 92.9 | 140/140 | 0 | 0.7 | 43.6 | 11.8 | 7.9 | 60.5 | ❌ | ❌ |
| N1 | qwen3-vl-8b | 92.9 | 140/140 | 0 | 6.4 | 28.8 | 18.9 | 6.7 | 39.9 | ❌ | ❌ |
| N1 | qwen3-vl-8b-demi | 100.0 | 140/140 | 0 | 5.7 | 37.4 | 21.1 | 6.4 | 52.0 | ❌ | ❌ |

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
| etat_civil | ferme | 57.9 | 268.9 | 186.8 | – (0) | 23.6 |
| admis_au_titre_de | ferme | 10.7 | 79.9 | 64.9 | – (0) | 23.6 |
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
| admis_au_titre_de | ferme | 0.0 | 96.0 | 88.8 | – (0) | 12.9 |
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
| admis_au_titre_de | ferme | 33.6 | 59.2 | 43.0 | – (0) | 0.0 |
| venant_de | texte_court | 60.7 | 43.6 | 41.1 | – (0) | 7.1 |
| religion | ferme | 80.7 | 14.2 | 14.2 | – (0) | 7.1 |
| adresse | texte_long | 0.0 | 39.4 | 33.5 | – (0) | 0.0 |
| categorie_medicale | ferme | 87.1 | 12.9 | 12.9 | – (0) | 0.0 |
| date_entree | date | 74.3 | 7.3 | 7.3 | – (0) | 0.0 |
| date_sortie | date | 38.6 | 36.7 | 35.6 | – (0) | 0.0 |
| nb_journees | numerique | 61.4 | 19.9 | 19.9 | 50.0 (2) | 0.0 |
| observations | texte_long | 5.7 | 42.3 | 39.7 | – (0) | 2.9 |

## N1 — churro-3b

| Colonne | Type | Exact % | CER strict % | CER tolérant % | Invention % (n vides) | Omission % |
|---|---|---|---|---|---|---|
| numero | numerique | 92.9 | 3.2 | 1.8 | – (0) | 0.0 |
| nom | texte_court | 80.7 | 4.2 | 3.7 | – (0) | 0.0 |
| prenoms | texte_court | 95.0 | 4.4 | 3.8 | – (0) | 1.4 |
| profession | texte_court | 62.1 | 20.6 | 18.3 | – (0) | 5.7 |
| date_naissance | date | 94.3 | 44.0 | 34.2 | 0.0 (1) | 1.4 |
| lieu_naissance | texte_court | 38.6 | 49.9 | 45.2 | 100.0 (1) | 2.2 |
| departement_naissance | texte_court | 50.7 | 54.9 | 52.8 | 37.5 (8) | 31.1 |
| pays | ferme | 94.3 | 6.4 | 6.3 | – (0) | 0.0 |
| etat_civil | ferme | 93.6 | 337.7 | 297.0 | – (0) | 0.0 |
| admis_au_titre_de | ferme | 3.6 | 72.2 | 64.0 | – (0) | 0.0 |
| venant_de | texte_court | 7.1 | 103.8 | 99.1 | – (0) | 20.0 |
| religion | ferme | 94.3 | 6.0 | 6.0 | – (0) | 0.0 |
| adresse | texte_long | 0.7 | 44.1 | 36.2 | – (0) | 0.0 |
| categorie_medicale | ferme | 82.1 | 47.1 | 18.6 | – (0) | 0.0 |
| date_entree | date | 86.4 | 11.2 | 10.4 | – (0) | 0.0 |
| date_sortie | date | 82.9 | 36.6 | 33.1 | – (0) | 3.6 |
| nb_journees | numerique | 93.6 | 5.7 | 2.5 | 0.0 (2) | 0.0 |
| observations | texte_long | 22.1 | 15.4 | 11.8 | – (0) | 0.0 |

## N1 — churro-3b-demi

| Colonne | Type | Exact % | CER strict % | CER tolérant % | Invention % (n vides) | Omission % |
|---|---|---|---|---|---|---|
| numero | numerique | 93.6 | 3.2 | 1.6 | – (0) | 0.0 |
| nom | texte_court | 70.7 | 7.2 | 6.8 | – (0) | 0.0 |
| prenoms | texte_court | 95.7 | 3.1 | 2.3 | – (0) | 0.0 |
| profession | texte_court | 69.3 | 13.0 | 11.0 | – (0) | 0.7 |
| date_naissance | date | 92.9 | 48.3 | 36.9 | 0.0 (1) | 0.0 |
| lieu_naissance | texte_court | 17.1 | 80.5 | 73.7 | 100.0 (1) | 0.0 |
| departement_naissance | texte_court | 67.9 | 34.4 | 30.5 | 12.5 (8) | 16.7 |
| pays | ferme | 96.4 | 4.8 | 4.6 | – (0) | 0.0 |
| etat_civil | ferme | 89.3 | 186.2 | 120.4 | – (0) | 0.0 |
| admis_au_titre_de | ferme | 17.9 | 66.9 | 53.3 | – (0) | 0.0 |
| venant_de | texte_court | 22.1 | 77.7 | 75.2 | – (0) | 22.1 |
| religion | ferme | 89.3 | 11.1 | 11.1 | – (0) | 10.0 |
| adresse | texte_long | 0.7 | 33.1 | 24.1 | – (0) | 0.0 |
| categorie_medicale | ferme | 88.6 | 45.7 | 11.4 | – (0) | 0.0 |
| date_entree | date | 96.4 | 7.6 | 7.6 | – (0) | 0.0 |
| date_sortie | date | 90.7 | 34.8 | 30.3 | – (0) | 0.0 |
| nb_journees | numerique | 93.6 | 5.2 | 3.0 | 50.0 (2) | 0.0 |
| observations | texte_long | 21.4 | 14.2 | 10.4 | – (0) | 0.0 |

## N1 — gemma3-12b

| Colonne | Type | Exact % | CER strict % | CER tolérant % | Invention % (n vides) | Omission % |
|---|---|---|---|---|---|---|
| numero | numerique | 0.7 | 61.1 | 61.1 | – (0) | 0.7 |
| nom | texte_court | 23.6 | 33.8 | 32.5 | – (0) | 0.7 |
| prenoms | texte_court | 22.1 | 70.2 | 66.6 | – (0) | 0.7 |
| profession | texte_court | 1.4 | 93.2 | 90.1 | – (0) | 29.3 |
| date_naissance | date | 0.0 | 44.4 | 44.2 | 100.0 (1) | 0.7 |
| lieu_naissance | texte_court | 1.4 | 97.6 | 94.3 | 100.0 (1) | 0.7 |
| departement_naissance | texte_court | 10.0 | 85.5 | 80.8 | 87.5 (8) | 1.5 |
| pays | ferme | 91.4 | 8.8 | 8.7 | – (0) | 0.7 |
| etat_civil | ferme | 52.9 | 55.7 | 54.5 | – (0) | 0.7 |
| admis_au_titre_de | ferme | 2.1 | 94.1 | 83.6 | – (0) | 0.7 |
| venant_de | texte_court | 0.0 | 96.3 | 93.3 | – (0) | 35.0 |
| religion | ferme | 14.3 | 82.5 | 81.4 | – (0) | 54.3 |
| adresse | texte_long | 0.0 | 80.4 | 77.3 | – (0) | 2.1 |
| categorie_medicale | ferme | 20.7 | 79.3 | 79.3 | – (0) | 0.7 |
| date_entree | date | 7.1 | 31.2 | 31.2 | – (0) | 0.7 |
| date_sortie | date | 3.6 | 53.1 | 53.1 | – (0) | 0.7 |
| nb_journees | numerique | 7.9 | 76.0 | 76.0 | 100.0 (2) | 0.7 |
| observations | texte_long | 0.0 | 84.0 | 82.4 | – (0) | 13.6 |

## N1 — gemma3-12b-demi

| Colonne | Type | Exact % | CER strict % | CER tolérant % | Invention % (n vides) | Omission % |
|---|---|---|---|---|---|---|
| numero | numerique | 30.0 | 28.9 | 28.9 | – (0) | 0.0 |
| nom | texte_court | 45.7 | 25.7 | 24.9 | – (0) | 0.0 |
| prenoms | texte_court | 68.6 | 22.7 | 21.7 | – (0) | 5.7 |
| profession | texte_court | 20.0 | 70.2 | 68.9 | – (0) | 47.9 |
| date_naissance | date | 53.6 | 25.1 | 23.6 | 100.0 (1) | 1.4 |
| lieu_naissance | texte_court | 27.9 | 41.9 | 39.0 | 100.0 (1) | 0.7 |
| departement_naissance | texte_court | 52.9 | 42.4 | 38.5 | 62.5 (8) | 3.8 |
| pays | ferme | 95.7 | 5.2 | 5.1 | – (0) | 0.7 |
| etat_civil | ferme | 55.7 | 53.9 | 49.1 | – (0) | 11.4 |
| admis_au_titre_de | ferme | 6.4 | 83.6 | 75.5 | – (0) | 17.9 |
| venant_de | texte_court | 4.3 | 92.7 | 90.1 | – (0) | 43.6 |
| religion | ferme | 55.7 | 43.0 | 40.6 | – (0) | 5.7 |
| adresse | texte_long | 0.0 | 60.1 | 53.9 | – (0) | 2.1 |
| categorie_medicale | ferme | 55.7 | 44.3 | 44.3 | – (0) | 0.7 |
| date_entree | date | 51.4 | 18.2 | 18.2 | – (0) | 0.7 |
| date_sortie | date | 42.9 | 44.3 | 41.6 | – (0) | 1.4 |
| nb_journees | numerique | 59.3 | 26.4 | 26.4 | 100.0 (2) | 0.7 |
| observations | texte_long | 0.7 | 51.7 | 48.1 | – (0) | 7.1 |

## N1 — qwen3-vl-8b

| Colonne | Type | Exact % | CER strict % | CER tolérant % | Invention % (n vides) | Omission % |
|---|---|---|---|---|---|---|
| numero | numerique | 70.0 | 10.5 | 9.3 | – (0) | 1.4 |
| nom | texte_court | 70.0 | 13.3 | 13.0 | – (0) | 0.7 |
| prenoms | texte_court | 80.7 | 15.1 | 13.9 | – (0) | 1.4 |
| profession | texte_court | 42.9 | 44.8 | 42.1 | – (0) | 4.3 |
| date_naissance | date | 74.3 | 7.8 | 7.8 | 100.0 (1) | 0.7 |
| lieu_naissance | texte_court | 50.7 | 26.5 | 24.0 | 100.0 (1) | 0.7 |
| departement_naissance | texte_court | 80.0 | 19.2 | 15.9 | 50.0 (8) | 3.8 |
| pays | ferme | 95.0 | 5.7 | 5.6 | – (0) | 1.4 |
| etat_civil | ferme | 65.0 | 58.1 | 47.3 | – (0) | 27.1 |
| admis_au_titre_de | ferme | 37.9 | 67.4 | 48.9 | – (0) | 1.4 |
| venant_de | texte_court | 17.1 | 85.1 | 82.9 | – (0) | 40.0 |
| religion | ferme | 65.7 | 18.1 | 17.8 | – (0) | 11.4 |
| adresse | texte_long | 0.0 | 42.5 | 36.2 | – (0) | 2.1 |
| categorie_medicale | ferme | 72.9 | 27.1 | 27.1 | – (0) | 0.7 |
| date_entree | date | 85.7 | 4.8 | 4.8 | – (0) | 0.7 |
| date_sortie | date | 63.6 | 36.7 | 34.1 | – (0) | 5.7 |
| nb_journees | numerique | 73.6 | 22.6 | 22.1 | 0.0 (2) | 0.7 |
| observations | texte_long | 11.4 | 24.9 | 21.6 | – (0) | 0.7 |

## N1 — qwen3-vl-8b-demi

| Colonne | Type | Exact % | CER strict % | CER tolérant % | Invention % (n vides) | Omission % |
|---|---|---|---|---|---|---|
| numero | numerique | 77.9 | 7.5 | 5.7 | – (0) | 0.0 |
| nom | texte_court | 60.0 | 13.3 | 12.7 | – (0) | 0.0 |
| prenoms | texte_court | 87.9 | 8.3 | 7.2 | – (0) | 0.0 |
| profession | texte_court | 54.3 | 21.0 | 18.8 | – (0) | 1.4 |
| date_naissance | date | 75.7 | 14.7 | 14.7 | 100.0 (1) | 9.4 |
| lieu_naissance | texte_court | 60.0 | 19.5 | 18.2 | 100.0 (1) | 3.6 |
| departement_naissance | texte_court | 84.3 | 13.4 | 11.3 | 12.5 (8) | 3.0 |
| pays | ferme | 95.0 | 5.6 | 5.5 | – (0) | 2.9 |
| etat_civil | ferme | 42.9 | 82.0 | 63.5 | – (0) | 53.6 |
| admis_au_titre_de | ferme | 49.3 | 46.1 | 29.2 | – (0) | 3.6 |
| venant_de | texte_court | 36.4 | 59.0 | 56.1 | – (0) | 32.1 |
| religion | ferme | 70.7 | 15.1 | 13.3 | – (0) | 7.9 |
| adresse | texte_long | 0.7 | 32.7 | 25.6 | – (0) | 0.0 |
| categorie_medicale | ferme | 75.0 | 25.0 | 25.0 | – (0) | 0.0 |
| date_entree | date | 90.7 | 9.1 | 9.1 | – (0) | 0.0 |
| date_sortie | date | 81.4 | 36.4 | 32.8 | – (0) | 2.1 |
| nb_journees | numerique | 84.3 | 11.2 | 11.2 | 0.0 (2) | 1.4 |
| observations | texte_long | 16.4 | 17.9 | 14.4 | – (0) | 0.0 |
