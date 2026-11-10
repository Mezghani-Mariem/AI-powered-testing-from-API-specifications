import json

def adapter_fichier(entree: str, sortie: str):
    with open(entree, "r", encoding="utf-8") as f:
        data = json.load(f)

    # On récupère la liste de tests
    if isinstance(data, dict) and "tests" in data:
        data = data["tests"]

    adapted = []
    for i, case in enumerate(data):
        # 1. Adaptation des endpoints
        endpoint = case.get("endpoint", "")
        # On mappe /products de son API vers /items de ton API
        if endpoint.startswith("/products"):
            endpoint = endpoint.replace("/products", "/items")

        # 2. Adaptation de expected_body
        expected_body = case.get("expected_body")
        if isinstance(expected_body, dict):
            # Si c'est un dict (ex: {"id": 1}), on prend juste les clés (ex: ["id"])
            expected_body = list(expected_body.keys())
        elif expected_body is None:
            expected_body = []

        new_case = {
            "test_id": case.get("test_id", f"MAR_{i+1}"),
            "name": case.get("name", f"Test {i+1}"),
            "method": case.get("method", "GET").upper(),
            "endpoint": endpoint,
            "test_type": case.get("test_type", "positive").lower(),
            "path_params": case.get("path_params", {}),
            "query_params": case.get("query_params", {}),
            "headers": case.get("headers", {}),
            "body": case.get("body", None),
            "expected_status": case.get("expected_status", 200),
            "expected_body": expected_body
        }
        
        adapted.append(new_case)

    with open(sortie, "w", encoding="utf-8") as f:
        json.dump(adapted, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Fichier adapté avec succès : {len(adapted)} tests convertis dans {sortie}")

if __name__ == "__main__":
    adapter_fichier("data/mariem_cases.json", "data/mariem_cases_adapted.json")