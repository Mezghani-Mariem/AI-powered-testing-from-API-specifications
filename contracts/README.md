# Contrat commun S5 — version 1.0

Ce contrat relie le générateur IA de Mariem Mezghani au moteur d’exécution et aux
rapports QA de Rimeh Abidi, sans import des modules internes de l’autre partie.

Le fichier échangé est `generated_tests.json`. Son schéma machine est
[generated_tests_v1.schema.json](generated_tests_v1.schema.json).

```json
{
  "schema_version": "1.0",
  "tests": [
    {
      "test_id": "TC_001",
      "name": "Get documented demo product",
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

Tous les champs sont obligatoires, sans ajout à l’enveloppe ou aux cas. Les IDs
sont uniques ; `test_type` vaut `positive`, `negative` ou `boundary`. Les endpoints
restent relatifs et conservent leurs variables, fournies dans `path_params`.
`body=null` signifie absence de corps. `expected_body=null` signifie absence
d’assertion de contenu ; un objet attendu est un sous-ensemble de la réponse.

Les endpoints, méthodes, contraintes et statuts doivent être justifiés par la
spécification. Cet exemple suppose un produit 1 garanti par le dataset de test ;
il ne garantit aucune donnée dans une API arbitraire. Le schéma machine seul ne
vérifie ni l’unicité des IDs ni la cohérence sémantique avec OpenAPI.

Organisation prévue : `main` pour l’intégration finale,
`feature/mariem-ai-generator` pour Mariem et `feature/rimeh-api-runner` pour Rimeh.
Chaque personne gère sa branche ; l’intégration est réalisée après revue.
