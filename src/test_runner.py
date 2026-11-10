import json
import time
import httpx
import argparse
from pathlib import Path
from typing import Any

# Configuration de sécurité (Plan Rimeh §4)
BASE_URL = "http://localhost:8000"
ALLOWED_METHODS = {"GET", "POST", "PUT", "DELETE"}
TIMEOUT_SECONDS = 5.0

def load_json(filepath: str) -> Any:
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)

def validate_test_case(case: dict, openapi_spec: dict) -> tuple[bool, str]:
    """Vérifie si le cas respecte le contrat JSON et existe dans l'OpenAPI."""
    required_fields = ["test_id", "name", "method", "endpoint", "test_type", 
                       "path_params", "query_params", "headers", "body", "expected_status"]
    
    for field in required_fields:
        if field not in case:
            return False, f"Champ manquant : {field}"
            
    if case["test_type"] not in {"positive", "negative", "boundary"}:
        return False, f"test_type invalide : {case['test_type']}"
        
    if case["method"] not in ALLOWED_METHODS:
        return False, f"Méthode HTTP non autorisée : {case['method']}"
        
    # Vérifier si l'endpoint existe dans l'OpenAPI
    endpoint_exists = False
    for path in openapi_spec.get("paths", {}).keys():
        # On remplace {item_id} par un format regex simple pour comparer
        # ex: /items/{item_id} correspond à /items/1
        base_path = path.split("{")[0]
        if case["endpoint"].startswith(base_path) and case["method"].lower() in openapi_spec["paths"][path]:
            endpoint_exists = True
            break
            
    if not endpoint_exists:
        return False, f"Endpoint {case['endpoint']} avec méthode {case['method']} absent de l'OpenAPI"
        
    return True, "OK"

def run_tests(cases_file: str, openapi_file: str, out_file: str):
    cases = load_json(cases_file)
    openapi_spec = load_json(openapi_file)
    
    results = []
    
    with httpx.Client(base_url=BASE_URL, timeout=TIMEOUT_SECONDS) as client:
        for case in cases:
            # 1. Validation
            is_valid, error_msg = validate_test_case(case, openapi_spec)
            if not is_valid:
                results.append({
                    "test_id": case.get("test_id", "UNKNOWN"),
                    "name": case.get("name", "UNKNOWN"),
                    "test_type": case.get("test_type", "UNKNOWN"),
                    "status_expected": case.get("expected_status", 0),
                    "status_observed": None,
                    "passed": False,
                    "duration_ms": 0,
                    "failure_reason": error_msg,
                    "error_type": "invalid_test"
                })
                continue
                
            # 2. Construction de l'URL (remplacement des path_params)
            endpoint = case["endpoint"]
            for k, v in case["path_params"].items():
                endpoint = endpoint.replace(f"{{{k}}}", str(v))
                
            # 3. Préparation des headers
            headers = case.get("headers", {})
            if case.get("body") is not None and "Content-Type" not in headers:
                headers["Content-Type"] = "application/json"
                
            # 4. Exécution de la requête
            start_time = time.perf_counter()
            try:
                response = client.request(
                    method=case["method"],
                    url=endpoint,
                    params=case["query_params"],
                    headers=headers,
                    json=case["body"] if case["body"] is not None else None
                )
                duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
                
                # 5. Comparaison
                passed = (response.status_code == case["expected_status"])
                failure_reason = ""
                passed = (response.status_code == case["expected_status"])
                
                error_type = None 
                
                if not passed:
                    failure_reason = f"Attendu {case['expected_status']}, obtenu {response.status_code}"
                    error_type = "executable_failure"
                else:
                    # Vérification du corps (expected_body)
                    if response.status_code != 204 and case.get("expected_body"):
                        try:
                            resp_json = response.json()
                            missing_keys = [k for k in case["expected_body"] if k not in resp_json]
                            if missing_keys:
                                passed = False
                                failure_reason = f"Clés manquantes dans la réponse : {missing_keys}"
                                error_type = "executable_failure"
                        except json.JSONDecodeError:
                            passed = False
                            failure_reason = "La réponse n'est pas un JSON valide"
                            error_type = "executable_failure"
                    else:
                        error_type = None

            except httpx.RequestError as exc:
                duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
                passed = False
                failure_reason = f"Erreur réseau/API : {str(exc)}"
                error_type = "infrastructure"
                response = None

            # 6. Enregistrement du résultat
            results.append({
                "test_id": case["test_id"],
                "name": case["name"],
                "test_type": case["test_type"],
                "status_expected": case["expected_status"],
                "status_observed": response.status_code if response else None,
                "passed": passed,
                "duration_ms": duration_ms,
                "failure_reason": failure_reason,
                "error_type": error_type
            })
            
    # 7. Sauvegarde
    Path(out_file).parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
        
    print(f"Terminé. {len(results)} tests exécutés. Résultats sauvegardés dans {out_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Runner de tests HTTP")
    parser.add_argument("-cases", default="data/generated_tests.json", help="Fichier des cas de test")
    parser.add_argument("-spec", default="data/openapi.json", help="Fichier OpenAPI")
    parser.add_argument("-out", default="reports/results.json", help="Fichier de sortie des résultats")
    
    args = parser.parse_args()
    run_tests(args.cases, args.spec, args.out)