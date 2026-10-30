# Contrat d’intégration Mariem ↔ Rimeh — v1.0

## Interface unique

Le fichier `generated_tests.json` est l’unique interface obligatoire. Aucun import du code de Mariem n’est nécessaire dans le moteur de Rimeh. Les rapports de génération sont des annexes et ne doivent pas être interprétés comme des résultats d’exécution de l’API.

Le contrat de la demande principale fait autorité sur les anciennes propositions du plan de travail. Aucune clé `id`, `category`, `path` ou `json_body` n’est utilisée en remplacement des champs officiels.

## Contrat JSON complet

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
    },
    {
      "test_id": "TC_002",
      "name": "Get nonexistent product",
      "method": "GET",
      "endpoint": "/products/{id}",
      "test_type": "negative",
      "path_params": {"id": 999999},
      "query_params": {},
      "headers": {},
      "body": null,
      "expected_status": 404,
      "expected_body": null
    },
    {
      "test_id": "TC_003",
      "name": "Invalid product price",
      "method": "POST",
      "endpoint": "/products",
      "test_type": "boundary",
      "path_params": {},
      "query_params": {},
      "headers": {"Content-Type": "application/json"},
      "body": {"name": "Test product", "price": -1},
      "expected_status": 422,
      "expected_body": null
    }
  ]
}
```

Tous les champs présentés sont obligatoires, même lorsque leur valeur est `{}` ou `null`. Aucune clé supplémentaire n’est admise dans l’enveloppe ou dans un test. Les dictionnaires de paramètres, les headers et les objets JSON de données gardent naturellement leurs propres clés.

| Champ | Type et règle |
| --- | --- |
| `schema_version` | Chaîne exactement `"1.0"` |
| `tests` | Tableau de cas ; peut être vide si aucun cas n’est justifié |
| `test_id` | Chaîne non vide, unique dans le fichier ; génération `TC_001`, etc. |
| `name` | Chaîne non vide décrivant le cas |
| `method` | Méthode HTTP en majuscules, déclarée pour ce chemin |
| `endpoint` | Chemin relatif exact d’OpenAPI, sans serveur/query/fragment ; conserver `{id}` |
| `test_type` | `positive`, `negative` ou `boundary` |
| `path_params` | Objet de valeurs JSON ; exactement les variables du chemin |
| `query_params` | Objet de valeurs JSON ; noms et contraintes issus de la spécification |
| `headers` | Objet de chaînes ; noms HTTP sans doublons de casse, valeurs sans CR/LF |
| `body` | Valeur JSON ; `null` signifie qu’aucun corps n’est envoyé |
| `expected_status` | Entier HTTP 100–599 ; pour les cas exportés, code explicitement documenté et justifié |
| `expected_body` | Objet JSON partiel ou `null` ; sous-ensemble attendu, pas égalité obligatoire avec toute la réponse |

Le schéma lisible par machine est livré dans `docs/generated_tests.schema.json`, généré depuis les modèles Pydantic. L’unicité des IDs et les règles sémantiques supplémentaires nécessitent la validation du module ; elles ne sont pas toutes exprimables en JSON Schema.

## Export et vérification

```powershell
python -m ai_generator.cli generate --spec examples/sample_openapi.json --output outputs/mock/generated_tests.json --mode mock
python -m ai_generator.cli validate --tests outputs/mock/generated_tests.json --spec examples/sample_openapi.json
```

Pour une autre spécification, utiliser `--mode live` configuré ou fournir un enregistrement mock correspondant avec `--mock-fixture`. Un mock incompatible échoue explicitement. Ne transmettre à l’exécution que le fichier de tests accepté ; `hypothetical_scenarios.json` est exclu.

## Préconditions de la démonstration

Le module ne démarre aucune API et ne crée aucune donnée distante. Pour exécuter la démonstration dans le module de Rimeh :

1. Fournir une URL de base séparément, sans la stocker dans `endpoint`.
2. Charger un produit `id=1` conforme au schéma (`Notebook`, prix 10) et un produit `id=1000000` (`Upper bound product`, prix 20).
3. Garantir l’absence du produit `id=999999`.
4. Implémenter le GET 200/404 et le POST 201/422 selon la spécification ; un prix négatif ou un nom manquant produit 422.
5. Prévoir une isolation/réinitialisation adaptée aux créations de produits ; aucun test ne consomme l’ID retourné par un autre.

Les fixtures sont spécifiques à cette démonstration. Les nombres 1 et 999999 ne sont pas des garanties universelles.

## Consignes pour Rimeh

Lire le JSON comme des données. Vérifier la version et l’unicité des IDs. Substituer et encoder chaque variable path à partir de `path_params`, puis sérialiser les query params selon l’opération OpenAPI. Les valeurs erronées des tests négatifs doivent être conservées afin de ne pas réparer silencieusement la requête testée.

Envoyer les headers fournis. Si `body` est `null`, ne pas envoyer de corps JSON ; sinon envoyer sa valeur JSON. Comparer le statut réel à l’entier attendu. Si `expected_body` est `null`, aucune assertion de contenu n’est demandée. Pour un objet partiel, vérifier les clés présentes et leurs valeurs ; un objet imbriqué est aussi un sous-ensemble, une liste conservée dans une assertion est comparée comme une valeur JSON complète.

L’authentification et la gestion des secrets appartiennent à la configuration d’exécution. Le générateur classe actuellement les opérations sécurisées comme incertaines ; aucune clé réelle ne doit être générée dans les cas.

Les rapports de génération mesurent la validité et la couverture des opérations proposées. Les résultats HTTP, assertions réelles, latences, performances et rapports QA sont calculés par Rimeh.

## Limites du contrat à discuter ensemble

Pas de variables partagées ni de capture d’ID, dépendances entre tests, scripts de setup/cleanup, cookies dédiés, fichiers binaires, multipart, corps JSON `null` distinct d’une absence de corps, attente d’un ensemble de statuts, assertions de schéma complet, tolérances numériques ou règles temporelles. Les métadonnées de preuve et préconditions restent dans la spécification et les rapports annexes. Les paramètres query structurés nécessitent une convention de sérialisation commune dans l’exécuteur.

Un scénario impossible à exprimer est signalé ou écarté. Toute évolution exige un nouveau contrat concerté ; aucune extension silencieuse du fichier v1.0.

## Consolidation après l’expérience Ollama

Les quatre exports live historiques sont dans `outputs/generated_tests_ollama.json`. Les deux scénarios GET dont le modèle a inventé des noms/prix restent exclus dans `outputs/hypothetical_scenarios.json`. Le rapport live `outputs/generation_report.json` doit être associé au fichier Ollama, tandis que `outputs/generated_tests.json` contient encore les six cas mock.

La [comparaison auditée](MOCK_LIVE_COMPARISON.md) détaille les décisions et les métriques. La [stratégie de données initiales](RIMEH_SEED_STRATEGY.md) propose une référence de dataset confirmée puis des scénarios annotés dans une copie de la spécification côté Mariem. Aucun champ de seed, de preuve ou de rapport n’est ajouté au contrat v1.0 ; le code de Rimeh n’a pas été modifié.
