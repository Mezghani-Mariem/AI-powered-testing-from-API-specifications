# S5 — Génération de tests d’API depuis OpenAPI

Module de **Mariem Mezghani**, projet universitaire avec **Rimeh Abidi**.

Pipeline autonome : **OpenAPI JSON/YAML → opérations normalisées → prompts → LLM ou enregistrement mock → validation → JSON v1.0**.

Ce dépôt produit des données de test. Le serveur de démonstration, l’exécution HTTP, les assertions sur des réponses réelles et les rapports QA d’exécution appartiennent au module de Rimeh. L’intégration passe uniquement par `generated_tests.json`.

## Installation

Python **3.11 ou ultérieur** ; validation locale effectuée avec Python 3.12.6.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Sous Linux/macOS, activer l’environnement avec `source .venv/bin/activate`. L’exécution depuis la racine ne nécessite pas d’installation du package ; `python -m pip install -e .` est également possible.

## Démonstration sans Internet

```powershell
python -m ai_generator.cli inspect --spec examples/sample_openapi.json
python -m ai_generator.cli generate --spec examples/sample_openapi.json --output outputs/mock/generated_tests.json --mode mock
python -m ai_generator.cli validate --tests outputs/mock/generated_tests.json
python -m ai_generator.cli validate --tests outputs/mock/generated_tests.json --spec examples/sample_openapi.json
```

Le mock rejoue des **réponses écrites à la main et enregistrées**, sans modèle, sans clé et sans accès réseau. Il vérifie que l’opération normalisée correspond à l’enregistrement. Il refuse une spécification différente au lieu de produire des fixtures inadaptées. Il ne simule pas une preuve de qualité d’un LLM.

Un second jeu enregistré, avec un ordre différent, est disponible :

```powershell
python -m ai_generator.cli generate --spec examples/sample_openapi.json --output outputs/demo_set_b/generated_tests.json --mode mock --mock-fixture ai_generator/fixtures/products_recording_b.json
```

La cible se règle avec `--tests-per-operation 3` (1 à 50). C’est un maximum demandé dans le prompt ; une sortie live plus longue est intégralement validée et comptabilisée. Le replay ne restitue que les premiers cas enregistrés jusqu’à cette cible et n’invente aucun cas supplémentaire.

## Configuration et génération live

Copier `.env.example` vers `.env`, puis renseigner la clé et un modèle disponible dans le compte du fournisseur :

```env
LLM_API_KEY=YOUR_KEY
LLM_BASE_URL=https://api.groq.com/openai/v1
LLM_MODEL=YOUR_AVAILABLE_MODEL
LLM_TEMPERATURE=0
LLM_TIMEOUT=60
LLM_MAX_RETRIES=2
LLM_RESPONSE_FORMAT=json_object
LLM_MAX_TOKENS=4096
```

```powershell
python -m ai_generator.cli generate --spec examples/sample_openapi.json --output outputs/live/generated_tests.json --mode live --env-file .env
```

Le client envoie une requête Chat Completions réelle à `LLM_BASE_URL/chat/completions`. Le fournisseur doit exposer ce protocole. Les variables d’environnement du processus priment sur `.env`. Les URL distantes doivent utiliser HTTPS ; HTTP est accepté pour localhost. Aucun fichier `.env` réel n’est livré et `.gitignore` exclut les secrets.

`LLM_RESPONSE_FORMAT` accepte `json_object`, `json_schema` (schéma en mode best effort, dépend du fournisseur) et `none`. La validation locale reste obligatoire. Le contrat comporte des objets à clés libres, que certains modes de schéma strict ne prennent pas en charge. Si le fournisseur refuse le format choisi, sélectionner explicitement un autre format ; le client ne change pas silencieusement de mode. Voir la [documentation officielle Groq](https://console.groq.com/docs/structured-outputs).

Au maximum, un appel initial et deux retries par défaut : backoff de 1 puis 2 secondes. Retry sur timeout, erreur réseau, HTTP 408/429/5xx, réponse JSON invalide ou tronquée. Pas de retry sur 400/401/403/404, redirection ou refus du modèle. Un échec live n’active jamais le mock. Les tests unitaires du client utilisent un transport HTTP simulé. Mariem a ensuite fourni une expérience live Ollama `qwen2.5-coder:7b` : 6 propositions, 4 exports et 2 hypothèses. Son [analyse comparative](docs/MOCK_LIVE_COMPARISON.md) conserve les résultats historiques ; la consolidation n’a effectué aucun nouvel appel LLM.

## Sorties

Chaque génération écrit dans le répertoire de sortie :

| Fichier | Contenu |
| --- | --- |
| `generated_tests.json` | Uniquement le contrat officiel v1.0 et les cas acceptés, sans métadonnées ajoutées |
| `generation_report.json` | Métriques, dénominateurs, rejets, avertissements et échecs d’opération |
| `hypothetical_scenarios.json` | Candidats incertains, explicitement non exécutables |

Les chemins des deux rapports sont personnalisables par `--report` et `--hypotheses`. Chaque fichier est remplacé atomiquement ; l’ensemble des trois fichiers n’est pas une transaction. Le rapport de génération des nouvelles expériences conserve les chemins relatifs à ce rapport et les SHA-256 des fichiers de tests et d’hypothèses, sans ajout au contrat v1.0. Les identifiants finaux sont normalisés en `TC_001`, `TC_002`, etc. Les doublons de comportement sont supprimés en ignorant leurs noms et identifiants.

Extrait valide du contrat :

```json
{
  "schema_version": "1.0",
  "tests": [
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
  ]
}
```

Ce cas dépend de la fixture documentée du produit 1. Il n’établit pas qu’un identifiant 1 existe dans une autre API.

## Validation, hypothèses et préconditions

Le validateur refuse les champs supplémentaires, les types incorrects, les endpoints/méthodes inconnus et les substitutions de chemin manquantes. Un cas positif doit respecter les contraintes. Un cas négatif peut volontairement violer le schéma ; son statut doit être relié à cette violation par une preuve explicite.

Les extensions facultatives `x-test-scenarios` et `x-validation-error-status` décrivent cette preuve dans la démonstration. Ce sont des conventions du projet, pas des garanties standard d’OpenAPI. Sans elles, les codes 4xx simplement listés, l’existence d’une ressource et les assertions de contenu concrètes restent incertains. Un POST conforme avec un unique code de succès documenté peut être retenu comme cas fondé sur le schéma ; cela ne vérifie ni les règles métier implicites ni l’état réel de l’API. Consulter [la stratégie de validation](docs/MARIEM_MODULE.md).

## Audit mock/live et intégration

Les artefacts historiques à la racine ne sont pas tous du même mode : `outputs/generated_tests.json` contient le mock (6 cas), tandis que `outputs/generation_report.json` et `outputs/hypothetical_scenarios.json` correspondent à `outputs/generated_tests_ollama.json` (4 cas live). Conserver ce lien explicite.

```powershell
python -m ai_generator.cli audit --spec examples/sample_openapi.json --tests outputs/generated_tests_ollama.json --generation-report outputs/generation_report.json --hypotheses outputs/hypothetical_scenarios.json --output outputs/consolidation/live_audit.json
python -m scripts.compare_mock_live
```

`audit` est hors ligne et vérifie les fichiers ensemble : contrat, sémantique, motifs d’exclusion, égalités de comptage, pourcentages et associations de fichiers. Il accepte les anciens rapports avec un avertissement sur l’absence de hashes historiques. Il ne répare aucun candidat et ne vérifie pas l’API cible. Le script comparatif conserve les sources et rejoue le mock dans `outputs/consolidation/mock_replay/`.

Pour une nouvelle expérience live avec le prompt 1.1.0, choisir un nouveau répertoire afin de conserver les mesures antérieures :

```powershell
python -m ai_generator.cli generate --spec examples/sample_openapi.json --output outputs/ollama_prompt_1_1/generated_tests.json --mode live --log-prompts --log-path outputs/ollama_prompt_1_1/prompts.jsonl
```

Le prompt amélioré demande une priorité aux positifs documentés et interdit de compléter `expected_body` avec des noms/prix inventés. Un nouvel essai réel avec Ollama a ensuite donné 6 exports sur 6 et zéro hypothèse, en 32,974391 s, avec un GET positif limité à l’ID documenté. Les quatre exports historiques et les deux hypothèses restent inchangés. La [comparaison live 1.0.0 / 1.1.0](docs/LIVE_PROMPT_1_0_VS_1_1.md) détaille cette observation exploratoire, ses artefacts séparés et la limite des paramètres historiques non archivés ; elle ne prouve aucune amélioration générale. Voir aussi [la comparaison mock/live historique](docs/MOCK_LIVE_COMPARISON.md) et [la stratégie de données initiales garanties](docs/RIMEH_SEED_STRATEGY.md). Aucun chargeur automatique de seed n’est ajouté ; les scénarios confirmés peuvent être annotés dans une spécification côté Mariem, sans modifier le contrat ni le code de Rimeh.

## Journalisation

```powershell
python -m ai_generator.cli generate --spec examples/sample_openapi.json --output outputs/mock/generated_tests.json --mode mock --log-prompts
```

`--log-prompts` active une trace JSONL de métadonnées et de validation. Par défaut, les prompts et réponses sont exclus. Ajouter **explicitement** `--log-content` pour enregistrer leur contenu. Choisir le chemin avec `--log-path`. Les descriptions OpenAPI peuvent contenir des données sensibles ; l’option de contenu est réservée aux entrées autorisées. La clé configurée est masquée même si elle apparaît dans le texte. Le rapport des hypothèses conserve les candidats incertains : il doit aussi être traité comme une sortie potentiellement sensible.

## Tests et résultats vérifiés

```powershell
python -m pytest -q
python -m scripts.verify_reproducibility
```

La suite standard interdit le transport HTTP réseau. Elle couvre le parser, les références, le contrat, les prompts, le client simulé, les erreurs, la sémantique, les négatifs intentionnels, la déduplication, l’export, les métriques, le CLI et la confidentialité du journal. Les résultats chiffrés de livraison figurent dans [MARIEM_MODULE.md](docs/MARIEM_MODULE.md) et `outputs/reproducibility_report.json`.

Codes de sortie : `0` génération terminée ou validation/audit réussi ; `1` échec d’au moins une opération LLM (exports partiels et rapport disponibles), refus sémantique lors de `validate` ou incohérence lors de `audit` ; `2` erreur d’entrée/configuration/contrat. Une génération terminée peut légitimement exporter zéro test si les candidats sont rejetés ou incertains : vérifier les compteurs du rapport.

## Limites

OpenAPI 3.0.x et 3.1.x, JSON/YAML, références locales non circulaires, paramètres path/query/header, corps JSON et contraintes usuelles. Les schémas `allOf`/`anyOf`/`oneOf` usuels sont vérifiés par JSON Schema, mais aucune génération exhaustive des combinaisons n’est garantie. Le traitement des schémas complexes et formats est détaillé dans la documentation technique.

Références externes, cycles, identifiants/ancres et références dynamiques refusés. Authentification, cookies, corps non JSON et sérialisations de headers non textuels rendent les scénarios incertains. Le contrat ne représente pas les dépendances, les fixtures exécutables, un corps JSON `null` distinct d’une absence de corps, les fichiers, les cookies ou les assertions avancées. Les codes `default`/`2XX` ne justifient pas un code concret. La couverture mesurée concerne les opérations ayant un test généré ; elle ne mesure ni le code ni les comportements réellement exécutés.

Intégration : [docs/INTEGRATION_CONTRACT.md](docs/INTEGRATION_CONTRACT.md). Aucun commit ni push automatique.
