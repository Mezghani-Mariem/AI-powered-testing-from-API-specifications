# Guide du Runner HTTP (Rimeh)

Ce module lit un fichier JSON de cas de test, vérifie leur validité, exécute les requêtes HTTP sur l'API locale et génère un rapport.

## 1. Lancer l'API cible
Dans un terminal :
```bash
uvicorn app.main:app --reload