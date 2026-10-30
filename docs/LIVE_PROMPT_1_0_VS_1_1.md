# Évaluation exploratoire live — prompts 1.0.0 et 1.1.0

Le nouvel essai Ollama a réellement été exécuté le **30 octobre 2026**, à partir de 16 h 58 (Africa/Lagos), avec `qwen2.5-coder:7b`. Sur les deux observations disponibles, le prompt 1.1.0 obtient **6 tests acceptés sur 6**, contre **4 sur 6** pour 1.0.0. Les deux scénarios hypothétiques disparaissent de la nouvelle génération et un GET positif est exporté avec une assertion limitée à l’ID documenté. La génération est cependant plus lente : **32,974391 s contre 26,728039 s**.

Ce résultat est exploratoire : un seul essai par version, les réglages historiques non archivés et un état de chargement historique inconnu ne permettent pas d’attribuer avec certitude toute la différence au seul prompt ni d’établir une amélioration générale.

## Conservation et fichiers produits

Tous les fichiers préexistants sous `outputs/`, ainsi que la spécification, ont été contrôlés par SHA-256 avant et après l’expérience : **aucun n’a été modifié**. La première expérience live a aussi été copiée octet pour octet dans un dossier d’archive, sans modifier ses quatre exports ou ses deux hypothèses.

Répertoire de cette nouvelle expérience :

`outputs/experiments/ollama_prompt_1_1_20261030_yzz6l3__/`

| Artefact | Lien |
| --- | --- |
| Copie des résultats live 1.0.0 et de la spécification | [historical_prompt_1_0](../outputs/experiments/ollama_prompt_1_1_20261030_yzz6l3__/historical_prompt_1_0/) |
| Nouveaux six tests live 1.1.0 | [generated_tests.json](../outputs/experiments/ollama_prompt_1_1_20261030_yzz6l3__/prompt_1_1/generated_tests.json) |
| Nouveau rapport de génération | [generation_report.json](../outputs/experiments/ollama_prompt_1_1_20261030_yzz6l3__/prompt_1_1/generation_report.json) |
| Nouveau rapport d’hypothèses, vide | [hypothetical_scenarios.json](../outputs/experiments/ollama_prompt_1_1_20261030_yzz6l3__/prompt_1_1/hypothetical_scenarios.json) |
| Audit 1.1.0 | [audit.json](../outputs/experiments/ollama_prompt_1_1_20261030_yzz6l3__/prompt_1_1/audit.json) |
| Prompts et réponses réellement échangés | [prompts.jsonl](../outputs/experiments/ollama_prompt_1_1_20261030_yzz6l3__/prompt_1_1/prompts.jsonl) |
| Configuration, modèle et empreintes de conservation | [experiment_metadata.json](../outputs/experiments/ollama_prompt_1_1_20261030_yzz6l3__/experiment_metadata.json) |
| Comparaison calculée depuis les fichiers | [comparison.json](../outputs/experiments/ollama_prompt_1_1_20261030_yzz6l3__/comparison.json) |
| Résultats pytest | [pytest_results.xml](../outputs/experiments/ollama_prompt_1_1_20261030_yzz6l3__/pytest_results.xml) |

Les fichiers historiques à la racine de `outputs/` conservent leurs rôles : `generated_tests_ollama.json` contient les quatre cas live 1.0.0 ; `generation_report.json` et `hypothetical_scenarios.json` correspondent toujours à cette expérience. `generated_tests.json` à la racine reste le mock historique. Aucun rapport historique n’a été remplacé par celui de 1.1.0.

## Conditions vérifiées et paramètres

Ollama est disponible sur `http://localhost:11434`, version serveur et CLI **0.13.0**. Le modèle installé est `qwen2.5-coder:7b`, 7.6B paramètres, quantification `Q4_K_M`, digest :

`dae161e27b0e90dd1856c8bb3209201fd6736d8eb66298e75ed87571486f4364`

La spécification est exactement celle du premier essai, vérifiée par son SHA-256 :

`2631c00425836bdd7b6c97ea81ef91f9181ac22fa24dafb041e41e7cb7372c88`

Le modèle nommé et la cible de trois tests par opération sont identiques. La configuration `.env` actuelle a été utilisée sans modification ni surcharge de variable d’environnement, et les paramètres réellement journalisés correspondent aux métadonnées de l’expérience :

| Paramètre | Valeur du nouvel essai |
| --- | --- |
| Base URL | `http://localhost:11434/v1` |
| Modèle | `qwen2.5-coder:7b` |
| Température | 0 |
| Timeout par appel | 180 s |
| Retries maximum | 2 |
| Format demandé | `json_object` |
| Limite de tokens de sortie | 4096 |
| Cible par opération | 3 |

**Limite sur l’égalité des paramètres :** le rapport 1.0.0 ne contient pas les paramètres LLM. Le seul ancien journal disponible contient des événements mock, pas de trace du premier live. L’égalité exacte des anciens réglages, du digest du modèle ou de la version d’Ollama n’est donc pas démontrable. Le nouvel essai conserve la configuration actuellement fournie ; il ne faut pas présenter l’expérience comme un protocole contrôlé où toutes les autres variables seraient prouvées identiques.

Avant l’essai, `/api/ps` ne signalait aucun modèle chargé. Le temps du nouvel essai peut donc inclure du chargement à froid. L’état avant le premier essai n’est pas connu. La nouvelle journalisation inclut également les contenus des prompts et réponses, contrairement à l’absence de journal live historique disponible.

## Exécution réelle et audits

L’expérience a été effectuée avec :

```powershell
python -u -m scripts.evaluate_prompt_versions
```

Ce script vérifie Ollama, archive les résultats historiques, alloue un répertoire unique et appelle réellement la commande de génération live. Il n’utilise aucun transport simulé et ne bascule jamais en mock. Les commandes exactes et leurs codes de sortie sont conservés dans les métadonnées et les fichiers `generation_command.log` / `audit_command.log`.

La commande de génération appelée correspond à :

```powershell
python -m ai_generator.cli generate --spec examples/sample_openapi.json --output outputs/experiments/ollama_prompt_1_1_20261030_yzz6l3__/prompt_1_1/generated_tests.json --mode live --tests-per-operation 3 --env-file .env --log-prompts --log-content --log-path outputs/experiments/ollama_prompt_1_1_20261030_yzz6l3__/prompt_1_1/prompts.jsonl
```

Deux appels Chat Completions réels ont réussi, un par opération, sans retry : environ 19,18 s pour GET et 13,78 s pour POST. La génération et les audits ont tous renvoyé le code `0`. L’audit historique est aussi valide, avec l’avertissement attendu sur l’absence de hashes de sorties dans son ancien rapport. L’audit 1.1.0 est valide sans avertissement et vérifie les empreintes des fichiers produits.

L’audit exécuté sur le nouvel essai est :

```powershell
python -m ai_generator.cli audit --spec examples/sample_openapi.json --tests outputs/experiments/ollama_prompt_1_1_20261030_yzz6l3__/prompt_1_1/generated_tests.json --generation-report outputs/experiments/ollama_prompt_1_1_20261030_yzz6l3__/prompt_1_1/generation_report.json --hypotheses outputs/experiments/ollama_prompt_1_1_20261030_yzz6l3__/prompt_1_1/hypothetical_scenarios.json --output outputs/experiments/ollama_prompt_1_1_20261030_yzz6l3__/prompt_1_1/audit.json
```

## Résultats réellement observés

| Mesure | Live 1.0.0 historique | Live 1.1.0 nouveau | Évolution observée |
| --- | ---: | ---: | --- |
| Tests proposés | 6 | 6 | Inchangé |
| Tests structurellement valides | 6 | 6 | Inchangé |
| Tests acceptés et exportés uniques | 4 | 6 | +2 |
| Scénarios hypothétiques | 2 | 0 | −2 |
| Rejets structurels / sémantiques stricts | 0 / 0 | 0 / 0 | Inchangé |
| Doublons | 0 | 0 | Inchangé |
| Validité structurelle | 100 % | 100 % | Inchangé |
| Acceptation sémantique | 66,6667 % | 100 % | +33,3333 points |
| Opérations couvertes | 2/2 | 2/2 | Inchangé |
| Couverture de génération | 100 % | 100 % | Inchangé |
| Positifs exportés | 1 | 2 | +1 |
| Négatifs exportés | 2 | 2 | Inchangé |
| Boundary exportés | 1 | 2 | +1 |
| GET positifs exportés | 0 | 1 | +1 |
| Tentatives LLM | 2 | 2 | Aucun retry dans les deux rapports |
| Temps de génération | 26,728039 s | 32,974391 s | +6,246352 s |

Les taux structurels utilisent les six candidats proposés comme dénominateur. Les taux sémantiques utilisent les six candidats structurellement valides, avant déduplication. La couverture utilise les deux opérations analysées. Ces scores portent sur la génération et la conformité à la spécification, pas sur l’exécution de comportements réels de l’API.

La qualité d’acceptation est meilleure sur cette observation ; **la durée ne s’améliore pas**. La hausse de durée ne peut pas être attribuée isolément au prompt : chargement, contexte plus long, variabilité du serveur et conditions de journalisation ne sont pas contrôlés dans l’expérience historique.

## GET positif et assertions non inventées

Le nouveau `TC_001` est :

```json
{
  "test_id": "TC_001",
  "name": "Get existing product",
  "method": "GET",
  "endpoint": "/products/{id}",
  "test_type": "positive",
  "path_params": {"id": 1},
  "query_params": {},
  "headers": {},
  "body": null,
  "expected_status": 200,
  "expected_body": {"id": 1}
}
```

Le scénario exact documenté justifie la requête, le statut et cette assertion sur l’ID. Les réponses brutes journalisées montrent que le modèle a directement proposé `expected_body={"id":1}` ; le pipeline ne l’a pas obtenu en supprimant des valeurs après validation. Aucun `name` ou `price` n’est inventé dans l’assertion.

Le GET boundary à `id=1000000` est également accepté avec seulement `expected_body={"id":1000000}`. Les quatre comportements déjà exportés en 1.0.0 restent présents. Les deux anciens candidats hypothétiques conservent leurs valeurs non prouvées dans l’archive ; ils n’ont pas été requalifiés. Les deux nouveaux GET sont issus d’une nouvelle réponse live.

Les six exports de ce nouvel essai sont identiques octet pour octet au mock de référence, mais leur provenance est live : les appels et réponses sont journalisés, le rapport indique deux tentatives LLM et zéro playback. Cela montre surtout que le modèle a correctement restitué les six scénarios explicitement fournis dans la spécification. Cela ne mesure ni la nouveauté ni la diversité de cas non fournis.

La présence réelle des produits 1 et 1000000 dans l’API de Rimeh n’a toujours pas été exécutée/vérifiée ici. L’acceptation est fondée sur les préconditions de la spécification ; leur réalisation reste une condition d’intégration.

## Régressions et changements de périmètre

Après l’exécution et l’ajout du script d’expérience, `python -m pytest -q` réussit : **145 tests, zéro échec, zéro erreur**. Un résultat JUnit est conservé dans le répertoire de l’expérience. Le contrat JSON v1.0, le parser, le validateur sémantique et les fichiers historiques de génération n’ont pas été modifiés pour obtenir ce score.

Le travail ajouté concerne le script d’expérience, les artefacts séparés et ce rapport. Aucun module de Rimeh, serveur API, moteur d’exécution, commit ou push n’a été créé ou modifié.

## Évaluation complémentaire proposée

Pour aller au-delà de cette observation, préparer par exemple **5 à 10 exécutions par version**, sans les lancer implicitement :

1. Archiver les textes exacts des deux prompts et leurs hashes ; figer la même spécification, le même digest de modèle, la même version d’Ollama et tous les paramètres d’inférence.
2. Alterner ou randomiser l’ordre des versions pour réduire l’effet d’ordre. Adopter une politique identique de chargement du modèle et distinguer les mesures à froid et à chaud ; conserver les mêmes options de journalisation.
3. Utiliser un répertoire unique pour chaque essai et auditer chaque sortie avec le même validateur. Relever les acceptations, hypothèses, GET positifs avec assertions prouvées, catégories et durées.
4. Présenter les résultats par exécution, puis les moyennes/médianes et la dispersion ; conserver les échecs et les répétitions identiques. Une température de zéro ne rend pas ces répétitions statistiquement indépendantes.
5. Étendre ensuite à d’autres spécifications et à des scénarios moins explicitement fournis, sans inventer les préconditions ni modifier les règles d’acceptation.

**Conclusion :** le prompt 1.1.0 donne un meilleur résultat d’acceptation et corrige le problème d’assertions observé dans ce nouvel essai. La génération est plus lente et l’amélioration générale, ainsi que son attribution causale au seul prompt, restent à confirmer.
