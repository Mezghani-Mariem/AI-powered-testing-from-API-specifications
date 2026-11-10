import json
import argparse
from pathlib import Path
from collections import Counter

def load_json(filepath: str) -> dict | list:
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)

def calculate_metrics(results_file: str, openapi_file: str, out_file: str):
    results = load_json(results_file)
    openapi_spec = load_json(openapi_file)
    
    total_tests = len(results)
    if total_tests == 0:
        print("Aucun résultat à analyser.")
        return

    # 1. Taux de réussite
    passed_tests = sum(1 for r in results if r["passed"])
    success_rate = round((passed_tests / total_tests) * 100, 2)

    # 2. Taux de validité (tests exécutables vs rejetés)
    valid_tests = sum(1 for r in results if r["error_type"] != "invalid_test")
    validity_rate = round((valid_tests / total_tests) * 100, 2)

    # 3. Répartition par catégorie
    categories = Counter(r["test_type"] for r in results)

    # 4. Temps d'exécution
    total_time = sum(r["duration_ms"] for r in results)
    avg_time = round(total_time / total_tests, 2)

    # 5. Couverture des opérations
    # On extrait les chemins testés depuis les résultats (en enlevant les IDs)
    # ex: GET /items/1 devient GET /items/{item_id}
    tested_ops = set()
    for r in results:
        if r["error_type"] != "invalid_test":
            # On simplifie le path pour matcher l'openapi (ex: /items/1 -> /items/{item_id})
            # Pour faire simple, on regarde si un path de l'openapi matche le début
            pass 
            
    # Note: Pour une vraie couverture, il faudrait passer le endpoint dans les résultats.
    # Ici, on fait une estimation basée sur les paths de l'OpenAPI qui ont reçu au moins une requête (via les logs ou une modif du runner).
    # Pour simplifier, on va compter les opérations uniques basées sur le nom du test ou on l'estime.
    
    # --- (Pour faire propre, il faudrait que le runner sauvegarde le 'method' et 'endpoint' dans le résultat. 
    # Mais comme on ne veut pas casser le runner, on va utiliser une méthode simple basée sur l'OpenAPI) ---
    total_ops = sum(len(methods) for methods in openapi_spec.get("paths", {}).values())
    
    # On va dire que la couverture est le nombre d'opérations distinctes testées par rapport au total.
    # (Dans une version avancée, on extrait ça du runner, mais ici on le déduit des tests réussis)
    # Pour l'instant, on met une valeur approximative basée sur les tests qui ne sont pas 'invalid'.
    # Idéalement, le runner devrait logger l'endpoint exact.
    
    summary = {
        "total_tests": total_tests,
        "passed_tests": passed_tests,
        "success_rate_percent": success_rate,
        "validity_rate_percent": validity_rate,
        "categories_distribution": dict(categories),
        "execution_time": {
            "total_ms": round(total_time, 2),
            "average_ms": avg_time
        },
        "operations_coverage": {
            "total_operations_in_spec": total_ops,
            "note": "Couverture détaillée à calculer si le runner exporte les endpoints."
        }
    }

    # Sauvegarde
    Path(out_file).parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print(f"Métriques calculées avec succès dans {out_file}")
    print(f"Taux de réussite : {success_rate}% ({passed_tests}/{total_tests})")
    print(f"Taux de validité : {validity_rate}%")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Calcul des métriques")
    parser.add_argument("-results", default="reports/results.json", help="Fichier des résultats")
    parser.add_argument("-spec", default="data/openapi.json", help="Fichier OpenAPI")
    parser.add_argument("-out", default="reports/summary.json", help="Fichier de sortie")
    
    args = parser.parse_args()
    calculate_metrics(args.results, args.spec, args.out)