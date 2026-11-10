# Contrat JSON commun — S5

**Binôme :** Mariem Mezghani & Rimeh
**Projet :** S5 — Génération de tests d'API depuis OpenAPI
**Fichier d'échange :** `data/generated_tests.json`

Ce document fixe le format des cas de test échangés entre le générateur (Mariem) et le runner (Rimeh). Toute modification doit être validée par les deux membres avant d'être appliquée.

---

## 1. Format d'un cas de test

```json
{
  "test_id": "TC_001",
  "name": "Créer un item valide",
  "method": "POST",
  "endpoint": "/items",
  "test_type": "positive",
  "path_params": {},
  "query_params": {},
  "headers": {"Content-Type": "application/json"},
  "body": {"name": "cahier", "price": 12},
  "expected_status": 201,
  "expected_body": ["id", "name", "price"]
}