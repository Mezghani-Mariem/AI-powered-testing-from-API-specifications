# Module Mariem — architecture et validation

## Périmètre et décisions

La demande principale fixe le contrat officiel **v1.0** et l’architecture `ai_generator/`. Le plan DOCX antérieur proposait des noms de champs et de fichiers différents ; ces propositions ne remplacent pas le contrat demandé. Aucun module serveur, moteur d’exécution HTTP ou rapport QA de Rimeh n’est implémenté.

## Composants

| Composant | Responsabilité |
| --- | --- |
| `openapi_parser.py` | Lecture sûre, normalisation, références locales, extraction des opérations et contraintes |
| `schemas.py` | Modèles Pydantic stricts `TestCase` et `TestSuite` ; champs supplémentaires interdits |
| `config.py` | Chargement `.env`/environnement, bornes et masquage de la clé |
| `prompt_builder.py` | Prompt système versionné et données utilisateur structurées par opération |
| `llm_client.py` | Appel live Chat Completions, extraction stricte, retries bornés et replay enregistré |
| `validator.py` | Validation structurelle et classification sémantique acceptée/refusée/incertaine |
| `test_generator.py` | Orchestration, suivi par opération, déduplication et attribution d’identifiants |
| `exporter.py` | Dernière validation du contrat et remplacement atomique par fichier |
| `metrics.py` | Comptages et pourcentages de génération avec dénominateurs explicites |
| `audit.py` | Vérification conjointe des exports, hypothèses, métriques et empreintes ; sans réparation des candidats |
| `prompt_logger.py` | Trace JSONL configurable, sans clé API |
| `cli.py` | Commandes `inspect`, `generate` et `validate` |

Les erreurs publiques dérivent de `GeneratorError`. Une spécification invalide interrompt le pipeline ; une erreur LLM est enregistrée pour son opération et les autres opérations continuent. Le CLI renvoie alors `1` et le rapport porte `partial_error`. Aucun secours mock implicite.

## Interfaces Python

```python
from ai_generator.openapi_parser import OpenAPIParser
from ai_generator.llm_client import MockLLMClient
from ai_generator.test_generator import TestGenerator

spec = OpenAPIParser().parse("examples/sample_openapi.json")
result = TestGenerator(MockLLMClient()).generate(
    "examples/sample_openapi.json", "outputs/mock/generated_tests.json",
    tests_per_operation=3,
)
assert result.report["mode"] == "mock"
```

`ParsedSpec` expose `operations`, `sha256`, `version`, `warnings` et `find(method, endpoint)`. Une `Operation` conserve méthode, chemin, paramètres, `requestBody`, réponses, preuves et raisons de prise en charge partielle. `SemanticValidator.validate(case)` rend un `ValidationResult` sans modifier le cas. `validate_contract(raw)` vérifie aussi l’unicité des identifiants d’un fichier complet.

Les clients reçoivent les messages, l’opération, la spécification et la cible. `LLMResult` expose les données décodées, le texte final, le nombre de tentatives, la durée, le modèle et le mode. Le client live utilise `httpx`, sans dépendance à un SDK fournisseur. Le transport et la fonction d’attente sont injectables pour les tests hors ligne.

## Parsing et contraintes

Référence : [OpenAPI 3.1.1](https://spec.openapis.org/oas/v3.1.1.html) et [OpenAPI 3.0.3](https://spec.openapis.org/oas/v3.0.3.html).

Lecture UTF-8 JSON/YAML ; taille brute maximale 5 MB, arbre limité à 100 niveaux/100 000 nœuds, parcours de résolution limité à 200 000 nœuds. Les doublons de clés, valeurs non finies, objets YAML arbitraires, cycles et expansions excessives d’alias sont refusés. Le parser vérifie les sections nécessaires à ce pipeline (`openapi`, `info.title/version`, `paths`, opérations et réponses). Il ne prétend pas être un validateur exhaustif de toute la spécification OpenAPI.

Les paramètres d’opération remplacent ceux du Path Item avec le même couple nom/emplacement. Les noms de headers sont comparés sans casse. Les paramètres path doivent être requis et correspondre aux variables du chemin. GET, POST, PUT, PATCH, DELETE, HEAD, OPTIONS et TRACE sont reconnus.

Les pointeurs locaux `#/...` sont résolus avec échappement JSON Pointer et décodage URI. Les cycles sont refusés, y compris dans un composant inutilisé. Les siblings de références 3.0 sont ignorés ; les contraintes adjacentes à un `$ref` de schéma 3.1 sont conservées via `allOf`. Pour les autres Reference Objects 3.1, seuls `summary` et `description` adjacents sont retenus.

Les contraintes `required`, types, minimum/maximum, bornes exclusives, longueurs, enum, format, tableaux, pattern et compositions usuelles sont validées par `jsonschema` Draft 2020-12. La traduction 3.0 couvre `nullable` (si `type` est explicite), les bornes exclusives booléennes et les propriétés requises `readOnly`/`writeOnly` selon la direction. Les formats dépendent des vérificateurs JSON Schema installés via `jsonschema[format]` ; un format personnalisé n’est pas une règle métier interprétable.

Les constructions exotiques (`$dynamicRef`, `$recursiveRef`, `$id`, ancres), schémas récursifs et références externes sont refusées. Les conversions OAS 3.0 dans des vocabulaires de schéma personnalisés, `patternProperties`/`dependentSchemas` complexes et dialectes personnalisés ne sont pas garantis. Les corps multipart/form/XML, les cookies et la configuration d’authentification ne sont pas traduits en requêtes exécutables par ce contrat. Une opération concernée reste comptée dans le dénominateur de couverture mais ses candidats sont classés incertains.

## Prompt engineering et modes

Version initiale : `1.0.0` ; version de consolidation : `1.1.0`. Un appel par opération limite le contexte et évite de mélanger les endpoints. Le message système décrit le contrat, l’indépendance des cas, les catégories, l’absence de suppositions sur les identifiants et les critères de preuve. Le message utilisateur contient la cible, l’opération normalisée, la version OpenAPI et le JSON Schema Pydantic. La version 1.1.0 privilégie les positifs documentés et interdit de compléter une assertion partielle avec les champs requis du schéma de réponse. Un essai live exploratoire ultérieur donne 6 acceptations sur 6, sans hypothèse, avec un GET positif limité à l’ID ; voir [la comparaison des deux prompts](LIVE_PROMPT_1_0_VS_1_1.md), y compris ses limites et sa durée plus élevée.

Les descriptions et exemples sont des données non fiables, jamais des instructions applicatives. Aucun code généré n’est évalué ou exécuté. Les sorties Markdown, JSON ambigu, clés dupliquées, enveloppes incorrectes et réponses tronquées sont refusées. Le client limite les réponses JSON analysées à 2 MB et les enveloppes à 500 candidats.

Le mode live envoie une vraie requête uniquement lorsqu’il est demandé et configuré. `json_schema` utilise `strict=false`, car les objets à clés libres du contrat peuvent dépasser le sous-ensemble strict d’un fournisseur. Voir [Groq Structured Outputs](https://console.groq.com/docs/structured-outputs). Le refus HTTP d’un mode structuré n’entraîne aucun basculement silencieux.

Le mode mock restitue des snapshots écrits à la main, dans `ai_generator/fixtures/`. Les deux jeux correspondent à la même spécification de produits avec des ordres différents. Leur provenance est déclarée dans les fichiers. `python -m scripts.update_demo_recordings` est un outil de maintenance explicite pour régénérer ces snapshots depuis les scénarios rédigés dans la démonstration ; il n’est jamais appelé par la génération ordinaire.

## Preuves et validation sémantique

Trois résultats sont possibles :

| Résultat | Destination |
| --- | --- |
| `accepted` | Export v1.0 après déduplication et nouveaux identifiants |
| `rejected` | Raisons structurelles/sémantiques dans `generation_report.json` |
| `hypothetical` | Cas complet et raisons dans `hypothetical_scenarios.json`, jamais dans l’export exécutable |

Le nom d’un test n’est pas utilisé pour prouver son intention. L’endpoint, la méthode, les valeurs, les contraintes et les preuves explicites sont examinés.

Un positif respecte les paramètres requis, le schéma du corps et un statut 2xx exact. Sans scénario explicite, une opération sans paramètre path et avec un unique code de succès documenté peut fournir une attente fondée sur le schéma. L’existence d’une ressource adressée, les résultats DELETE, un choix entre plusieurs succès ou une assertion concrète de contenu demandent une preuve supplémentaire. Les règles métier implicites demeurent une limite de toute génération depuis OpenAPI.

Un négatif attend un code non 2xx documenté. Il peut omettre un champ, un paramètre query/header ou le corps requis, ou violer un type/une contrainte. La présence d’un 422 dans `responses` ne prouve pas le statut d’une requête précise. Pour accepter le cas, il faut une correspondance exacte avec `x-test-scenarios`, ou une violation de schéma reliée à `x-validation-error-status`. Cette seconde extension ne justifie pas les échecs de négociation de contenu.

Un boundary exerce une borne déclarée : borne numérique, valeur numérique adjacente (distance ≤ 1), longueur ou taille de collection à une borne ou adjacente. Une valeur invalide ne peut attendre un succès. Les formats seuls et les enums ne définissent pas de distance limite générale. Un champ à la limite n’autorise pas à ignorer les autres contraintes.

La différence entre absence de corps et corps JSON `null` n’est pas exprimable : `body=null` signifie absence. Un chemin non substituable est rejeté même pour un négatif. Les tests d’omission de variable path demandent un autre contrat ; aucune réécriture d’endpoint n’est inventée.

`expected_body` est un objet partiel : les propriétés requises de la réponse complète ne sont pas exigées dans l’assertion. Ses valeurs doivent néanmoins correspondre à une preuve explicite et à un schéma de réponse JSON. Pour les compositions complexes, le contrôle partiel reste conservateur et peut refuser une assertion pourtant possible ; utiliser `null` et examiner le scénario manuellement.

### Extensions facultatives du projet

```yaml
x-validation-error-status: 422
x-test-scenarios:
  - name: Get existing product
    test_type: positive
    request:
      path_params: {id: 1}
    expected_status: 200
    expected_body: {id: 1}
```

`x-validation-error-status` doit être un entier 4xx explicitement présent dans `responses`. Il déclare que les violations de schéma de requête sont rejetées avec ce code. `x-test-scenarios` contient les requêtes concrètes et leurs résultats attendus ; les conteneurs absents valent `{}` et l’absence de `body` vaut `null`. La comparaison est exacte pour les valeurs de requête, sans casse pour les noms de headers. L’extension est rédigée par la personne responsable des préconditions de l’API. Ces extensions ne modifient jamais le contrat de sortie.

## Déduplication et métriques

Après validation, le fingerprint contient tous les champs de contrat sauf `test_id` et `name`. Il conserve la catégorie. Des noms ou identifiants différents ne multiplient donc pas le même comportement dans une catégorie. Les IDs sont ensuite réattribués dans l’ordre de parcours et validés dans le fichier complet.

| Mesure | Définition |
| --- | --- |
| Opérations analysées | Toutes les opérations extraites, même partiellement prises en charge |
| Tests proposés | Tous les éléments des enveloppes v1.0 décodées avec succès |
| Structure valide | Candidats conformes au modèle `TestCase`, avant nouveaux IDs |
| Taux structurel | Structure valide / tests proposés × 100 |
| Acceptation sémantique | Candidats acceptés / structure valide × 100, avant déduplication |
| Validés | Cas acceptés uniques réellement exportés |
| Rejetés | Rejets structurels + rejets sémantiques + hypothétiques |
| Doublons | Candidats sémantiquement acceptés déjà présents |
| Couverture de génération | Opérations avec ≥ 1 cas exporté / opérations analysées × 100 |
| Répartition | Comptages par catégorie parmi les cas exportés uniques |
| Temps de génération | Temps monotone du parsing, prompts, appels/retries, journal et validation ; exclut l’écriture finale des trois exports |
| Tentatives LLM | Nombre réel de requêtes live, retries inclus ; zéro en mock |
| Playbacks mock | Opérations rejouées avec succès |
| Échecs LLM | Opérations n’ayant pas fourni d’enveloppe valide après tentatives |

Un dénominateur nul donne `null`, pas un taux artificiel de 100 %. Une enveloppe invalide ne permet pas un comptage fiable de candidats ; elle compte comme échec d’opération. Pour les enveloppes décodées : `proposés = validés + rejetés + doublons`. Les IDs sources peuvent se répéter ; l’unicité du contrat est imposée aux IDs finaux, après normalisation.

Cette couverture ne mesure ni lignes de code, ni branches, ni comportements métier réellement exécutés. Les bons scores des fixtures montrent le fonctionnement du pipeline ; ils ne mesurent pas la qualité d’un fournisseur LLM réel.

## Journal et reproductibilité

`--log-prompts` conserve version du prompt, modèle, mode, paramètres non secrets, heure UTC, hash SHA-256 des octets OpenAPI, opération, durée, tentatives, résultats et erreur éventuelle. `--log-content` ajoute le prompt et la dernière réponse textuelle reçue, y compris une dernière réponse invalide. Les réponses intermédiaires de retries ne sont pas archivées ; leur nombre est conservé. La clé API configurée est masquée avant écriture. Désactiver le contenu pour des descriptions sensibles ; protéger également les exports et rapports de candidats.

Les tests exportés des mocks sont reproductibles octet pour octet. Les durées et horodatages des rapports/journaux varient normalement. Un modèle live peut varier même avec une température nulle. Le hash d’entrée et les paramètres permettent d’identifier l’expérience ; ils ne rendent pas un service externe déterministe.

## Résultats vérifiés de livraison

Python 3.12.6 ; Pydantic 2.12.4, PyYAML 6.0.2, httpx 0.28.1, python-dotenv 1.2.1, jsonschema 4.26.0 et pytest 9.1.1.

Les commandes et résultats effectifs sont enregistrés dans `outputs/reproducibility_report.json`. La démonstration attend 2 opérations, 6 cas acceptés, 2 positifs, 2 négatifs et 2 boundary, aucun rejet/doublon, taux structurel et sémantique de 100 %, couverture de génération de 100 %, **zéro tentative LLM réelle**. Les deux jeux enregistrés sont vérifiés sur deux exécutions chacun. La suite de tests livrée est entièrement hors ligne.

Exécution finale : `python -m pytest -q` → **126 passed**. La commande `validate` sur l’export livré confirme `contract_valid=true`, `semantic_checked=true`, `valid=true` pour les six cas ; résultat conservé dans `outputs/validation_report.json`.

À la livraison initiale, le client live avait seulement été testé par simulation HTTP. Mariem a ensuite fourni une expérience Ollama `qwen2.5-coder:7b`, prompt 1.0.0 : 6 candidats, 4 exports, 2 hypothèses, 26,728039 secondes. Les fichiers et compteurs ont été audités hors ligne ; aucun appel LLM ni exécution de l’API cible n’a été effectué pendant la consolidation. Le résultat est détaillé dans [MOCK_LIVE_COMPARISON.md](MOCK_LIVE_COMPARISON.md).

Les futurs rapports incluent une section `artifacts` avec les chemins et SHA-256 de l’export et du fichier d’hypothèses. Ces métadonnées ne font pas partie du contrat de tests. `audit` vérifie les associations et les égalités de métriques ; les anciens rapports restent lisibles mais signalent leur absence de liaison historique. Le script `scripts.compare_mock_live` isole son replay et préserve les mesures d’origine.

Validation finale de consolidation : **145 tests pytest réussis**, dont la non-régression des quatre exports et deux exclusions observés, les erreurs de métriques et les mélanges d’artefacts. La [stratégie de seed proposée](RIMEH_SEED_STRATEGY.md) n’ajoute aucun chargeur ni nouvelle garantie. La conformité du serveur, du jeu initial et de l’exécution doit encore être vérifiée à l’intégration avec Rimeh.
