# Master prompt v2 — Pipeline d'océrisation de registres de sanatorium, par niveaux de complexité

## 1. Contexte et objectif

- **Contexte** : thèse de doctorat en histoire de la santé
- **Objectif** : transcrire en CSV des photos de registres d'entrée/sortie d'un sanatorium français (1919-1939)

**Contraintes**
- **100 % local** : aucune image ni donnée ne sort de la machine. Le réseau n'est autorisé que pour `pip`/`uv` et `ollama pull` (demande-moi confirmation avant tout téléchargement de modèle ou de fichier de référence).
- Matériel actuel : MacBook Pro M1 Pro, 16 Go, Ollama installé sur l'hôte (Docker sur Mac n'a pas accès au GPU Metal : le conteneur ne contient que le code et appelle l'Ollama de l'hôte via `OLLAMA_HOST`). Un serveur GPU NVIDIA est envisagé plus tard : l'accès aux modèles doit donc passer par une couche d'abstraction (API Ollama par défaut, API compatible OpenAI en option pour vLLM ou llama.cpp), sans réécrire le pipeline.
- Langue du projet et des prompts de transcription : français.

**Principe directeur** : plusieurs stratégies, de la plus simple à la plus élaborée, implémentées avec la **même interface** (mêmes entrées, même schéma de sortie, même évaluateur). À chaque étape, on compare les performances de plusieurs modèles. On monte d'un niveau seulement si le niveau précédent ne suffit pas, et chaque niveau est évalué sur le même jeu de référence pour que le gain soit mesurable.

## 2. Données et schéma

**Données**
- Manuscrits sur tableaux imprimés, photographiés (double page par photo, prise de vue en biais, éclairage inégal)
- Une ligne du registre = un patient
- Certaines cases contiennent plusieurs lignes de texte

- `raw/` : photos à annoter.
- `gold/` : données de référence. Photos dans `gold/photos`, transcriptions correspondantes dans `gold/transcripts`.
- Informations présentes (l'ordre des colonnes peut varier) : N° d'ordre ; Noms et prénoms (nom en grand, prénoms en dessous) ; Profession ; Date et lieu de naissance (3 lignes : date, commune, département) ; État civil ; Admis au titre de (souvent « A.M.G. » + département) ; Religion ; Adresse (plusieurs lignes) ; Catégorie médicale (symbole) ; Date d'entrée ; Date de sortie ; Nombre de journées ; Observations du médecin (cursive, encre bleue).
- Sorties finales : CSV dans `transcripts/<strategie>/<modele>/`, un fichier par photo et un `all.csv`.

## 3. Les niveaux de complexité

Chaque niveau est une **stratégie sélectionnable** (`--strategy N0..N5`) et se décrit dans un fichier de configuration YAML (modèle, prompts, paramètres d'inférence, taille d'image).
Chaque niveau doit comparer les performances de plusieurs modèles :
- Qwen3-VL 8B
- Gemma 3 12B
- Churro (3B)

### N0 — Page entière, un seul appel
Un appel de modèle de vision par photo, sortie JSON contrainte. Sert de base de référence.

### N1 — Une ligne, un appel
Prérequis : segmentation automatique (§4). Un appel par patient, sur l'image de la ligne complète (gauche + droite côte à côte), ou sur deux demi-lignes (identité / séjour) en deux appels ; comparer les deux variantes. Un seul prompt, sortie JSON de tous les champs. Contexte court donc moins d'inventions et de boucles.

### N2 — Une cellule, un appel, prompts spécialisés
Un appel par cellule, avec un prompt adapté au type de colonne :
- **Champs fermés** : religion, état civil, « admis au titre de », catégorie médicale, par `enum` dans le schéma JSON (valeurs autorisées issues du gold et validées par moi). Pour le symbole de la catégorie médicale, comparer un appel de modèle et un petit classifieur d'images.
- **Numériques** : n° d'ordre, nb de journées (chiffres uniquement), dates (jour/mois/année, année à deux chiffres conservée).
- **Texte court libre** : nom, prénom (la case contient deux lignes : nom puis prénoms), profession, lieux, départements, « venant de ».
- **Texte long** : adresse et observations, avec limite de longueur proportionnelle à la largeur de la case, détection automatique de répétition (n-grammes répétés) et nouvelle tentative avec paramètres différents.
- Variante à mesurer : avec ou sans l'image de la ligne comme contexte de la cellule.

### N3 — N2 + validations et normalisation déterministes (sans modèle)
- **Dates** : ISO, année à deux chiffres → 19xx ; contrôle `sortie ≥ entrée`.
- **Cohérence** : `nb_journees = date_sortie − date_entree`. Quand le nombre est lu avec confiance et que la date de sortie est incohérente, proposer la date reconstruite dans `date_sortie_norm`, en gardant la lecture brute et un drapeau.
- **N° d'ordre** : +1 d'une ligne à l'autre ; une rupture déclenche un drapeau (lecture ou segmentation fautive).
- **Vocabulaires fermés** : valeurs hors liste → drapeau (ne pas corriger en silence).
- **Lieux et départements** : rapprochement flou avec un référentiel que je fournirai dans `ref/` (COG INSEE) et une table des noms de départements en 1935 (Basses-Pyrénées, Seine, Seine-et-Oise, Charente-Inférieure, etc.) ; Claude Code propose la table, je la valide. Écart important → drapeau, jamais de correction automatique.
- **Professions** : valeur brute + valeur normalisée (nomenclature simple à construire à partir du gold, extensible).
- **Noms propres** : jamais de correction automatique, seulement un drapeau de confiance.
- **Indicateurs de relecture** par champ (`_flag`) : règles violées, désaccord entre lectures, répétition détectée, valeur hors vocabulaire.

### N4 — Consensus et cascade
Pour les champs que N3 signale ou qui sont difficiles (lieux, professions, observations) :
- plusieurs modèles (au moins deux familles, par exemple Qwen3-VL instruct, Gemma 3, Qwen2.5-VL) et/ou plusieurs échantillons à température > 0 (*self-consistency*) ;
- vote par champ et **score d'accord** ; désaccord → relecture ;
- **cascade** : n'envoyer au second modèle (plus lent ou plus grand) que les cellules signalées, pour économiser le temps de calcul ;
- si disponible dans la version d'Ollama utilisée, exploiter les `logprobs` comme score de confiance ;
- option : moteur HTR spécialisé (Kraken, PyLaia, TrOCR) sur les colonnes d'écriture cursive, s'il existe un modèle pré-entraîné local pertinent (chercher, mais ne rien télécharger sans ma confirmation) ;
- test supplémentaire possible sur la page présente en double : traiter les deux photos comme deux vues indépendantes pour le consensus.

### N5 — Fine-tuning et boucle de relecture
- Exporter le jeu de référence en jeu d'entraînement (images de cellules ou de lignes + texte attendu, au format de conversation des modèles Qwen-VL) avec séparation **par page et par année** (aucune fuite entre cellules d'une même page).
- Écrire les scripts de fine-tuning LoRA/QLoRA, paramétrables pour un serveur CUDA futur (Unsloth, LLaMA-Factory ou ms-swift : choisir et justifier). Ne pas lancer sur le Mac, sauf modèle ≤ 4B via MLX si c'est réaliste.
- Outil de relecture local (Streamlit ou page HTML simple) : affiche pour chaque cellule signalée le crop, la prédiction et un champ éditable, et écrit les corrections dans un fichier dédié ; une commande permet de les intégrer au jeu de référence après ma validation.

## 4. Éléments transversaux (à construire en premier)

- **Banc d'évaluation commun** (`eval/`) : une commande compare n'importe quelle sortie au gold et produit `metrics.csv`, `errors.csv` (une ligne par erreur : gold, prédiction, image source) et un tableau de synthèse.
- **Métriques** (par colonne et par stratégie × modèle) : CER (Levenshtein normalisé, `rapidfuzz`) en version stricte et tolérante (minuscules, accents retirés) ; exactitude exacte pour les champs courts, fermés, numériques et les dates ; exactitude par ligne ; **taux d'invention** (texte non vide prédit là où le gold est vide) ; validité du JSON ; taux de cohérence interne (dates, nb de journées) ; **précision et rappel des drapeaux de relecture** (quelle part des erreurs est signalée) ; temps par ligne, tokens/s, mémoire maximale, extrapolation du temps pour 5 000 lignes.
- **Segmentation (utilisée dès N1)** : OpenCV, NumPy, scikit-image. Couper en page gauche/droite (profil de projection au niveau de la reliure), redresser chaque page par homographie à partir des 4 coins du tableau (binarisation Sauvola, détection des traits longs par morphologie ou LSD), détecter les 7 colonnes par page (pics de projection verticale pondérés par la longueur), puis les lignes : ne garder que les séparateurs qui traversent **toutes** les colonnes, épais et à pas régulier (≈ 10 par page), en ignorant les traits fins internes aux cases. Apparier la ligne *i* de gauche à la ligne *i* de droite. Exporter les crops (`data/cells/…`, `data/rows/…`) et des images de contrôle (`data/debug/…`). Repli manuel : script où je clique les 4 coins. Si le nombre de colonnes (7) ou de lignes diffère de l'attendu, signaler la page au lieu de continuer en silence.
- **Paramètres d'inférence par défaut** : variante `-instruct` de Qwen3-VL (la variante avec réflexion boucle jusqu'à saturation du contexte), échantillonnage léger (`temperature` 0,2-0,7, `top_k` 20, `repeat_penalty` ≈ 1,05), `num_ctx` ≥ 16384.
- **Couche modèles** : une interface unique (`vlm/`) avec backends Ollama et compatible OpenAI ; tous les paramètres d'appel enregistrés avec chaque réponse ; cache des réponses brutes (JSONL) pour reprendre après une interruption ; un seul modèle chargé à la fois.
- **Configuration** : un fichier YAML par stratégie et par modèle ; aucune valeur de réglage codée en dur.

## 5. Règles de travail

- Liste de tâches ; code dans `src/`, données dans `data/`, résultats dans `results/` et `transcripts/` ; environnement isolé (`uv` ou `venv`) avec dépendances épinglées ; un `README` indiquant comment relancer chaque étape.
- Reproductibilité : graine fixe, paramètres et versions (modèle, quantification, Ollama) enregistrés avec chaque résultat.
- Pas de fuite de la référence dans les prompts (ne jamais y copier des valeurs du gold).
- Si une étape échoue plusieurs fois ou si un choix est ambigu, dis-le-moi plutôt que de contourner en silence.
- Avant tout téléchargement (modèles, référentiels), liste ce qui est prévu avec les tailles et attends ma confirmation.
- **Seuils de succès provisoires** (à discuter avec moi, ne montent pas de niveau si atteints) : ≥ 95 % d'exactitude sur les champs fermés, numériques et dates ; CER ≤ 5 % sur noms, prénoms et lieux ; ≥ 90 % des erreurs restantes signalées par un drapeau de relecture.

## 6. Livrables

- `results/metrics.csv`, `results/errors.csv`, et `REPORT.md` avec, pour chaque niveau : tableau de métriques par colonne, temps par ligne et extrapolation pour le corpus, principales erreurs observées, recommandation argumentée (quel niveau et quel modèle retenir, pour quelles colonnes, et si un fine-tuning ou un GPU serveur se justifie).
- Les CSV de transcription par stratégie dans `transcripts/`.
- Les configurations YAML, les scripts, le `README`.

## 7. Relancer les étapes

Environnement : `uv sync` (Python 3.12, dépendances épinglées dans `pyproject.toml` / `uv.lock`). Ollama tourne sur l'hôte (`OLLAMA_HOST` pour le joindre depuis ailleurs).

| Étape | Commande | Sorties |
|---|---|---|
| Transcription (une stratégie × un modèle) | `uv run python -m htr.run --strategy N0 --model qwen3-vl-8b` | `transcripts/N0/<modèle>/`, `results/runs/N0/<modèle>.json`, cache `data/cache/` |
| Benchmark (plusieurs modèles, un chargé à la fois, puis évaluation) | `scripts/run_benchmark.sh N0 qwen3-vl-8b gemma3-12b churro-3b` | idem + `results/` |
| Évaluation seule | `uv run python -m eval.evaluate [--only N0/qwen3-vl-8b]` | `results/metrics.csv`, `summary.csv`, `errors.csv`, `summary.md` |
| Segmentation (N1) | `uv run python -m htr.segmentation.segment [--only "1491_W_1 (9)"]` | `data/rows/`, `data/cells/`, `data/debug/index.html`, `data/segmentation/report.csv` |
| Coins manuels (repli) | `uv run python -m htr.segmentation.click_corners "1491_W_1 (9)"` | `data/corners/<photo>.json`, pris en compte à la segmentation suivante |

Configurations : `configs/<stratégie>/<modèle>.yaml` (modèle, prompt, image, inférence), `configs/prompts/`, `configs/segmentation.yaml`. Le schéma de sortie commun est dans `src/htr/schema.py`.

Gold : les fichiers `gold/transcripts/<photo>.csv` portent le même nom que `gold/photos/<photo>.jpg` (14 photos ; la photo `(3)`, sans transcription, a été retirée).
