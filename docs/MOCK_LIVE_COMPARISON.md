# Consolidation S5 — comparaison mock et Ollama

Date de l’analyse : 30 octobre 2026. Module Mariem uniquement.

Suivi postérieur à cette consolidation : un nouvel essai live du prompt 1.1.0 a réellement été effectué et conservé séparément. Voir [LIVE_PROMPT_1_0_VS_1_1.md](LIVE_PROMPT_1_0_VS_1_1.md). Les chiffres et conclusions ci-dessous décrivent toujours la comparaison historique entre le mock et la première génération live 1.0.0.

Le résultat live fourni est **cohérent** : quatre tests exportés sont acceptables au regard de la spécification et deux candidats sont correctement exclus à cause d’assertions de contenu sans preuve. Aucun candidat n’a été réparé, promu ou ajouté à l’export durant cet audit. Aucune API cible et aucun nouveau modèle n’ont été appelés.

## Sources et portée de la vérification

| Élément | Fichier analysé |
| --- | --- |
| Spécification commune | `examples/sample_openapi.json` |
| Six tests mock historiques | `outputs/generated_tests.json` |
| Preuve de reproductibilité du mock historique | `outputs/reproducibility_report.json`, jeu `products_recording.json` |
| Quatre tests live | `outputs/generated_tests_ollama.json` |
| Rapport de cette génération live | `outputs/generation_report.json` |
| Deux candidats live exclus | `outputs/hypothetical_scenarios.json` |
| Audit live détaillé | `outputs/consolidation/live_audit.json` |
| Replay mock isolé et son audit | `outputs/consolidation/mock_replay/` et `outputs/consolidation/mock_audit.json` |
| Comparatif et empreintes des sources | `outputs/consolidation/comparison.json` |

La spécification porte l’empreinte SHA-256 `2631c00425836bdd7b6c97ea81ef91f9181ac22fa24dafb041e41e7cb7372c88`, identique à celle du rapport live. Le mock rejoué est identique octet pour octet au mock historique, dont l’empreinte est également confirmée par le rapport de reproductibilité antérieur. Les fichiers sources de l’expérience ont été conservés sans modification.

L’utilisation d’Ollama `qwen2.5-coder:7b` est déclarée par Mariem et correspond au champ `model` des artefacts live. L’audit confirme leur cohérence interne ; il ne constitue pas une trace indépendante du processus Ollama. Les sorties disponibles ne contiennent pas la réponse brute complète du modèle, ses versions/digest matériels ni tous les réglages d’inférence. L’expérience analysée a utilisé le prompt **1.0.0**. Le prompt **1.1.0** ajouté pendant la consolidation n’a pas encore été évalué en live.

## Comparaison quantitative

| Mesure | Mock historique | Live Ollama observé |
| --- | ---: | ---: |
| Opérations analysées | 2 | 2 |
| Cas proposés/rejoués | 6 | 6 |
| Cas structurellement valides | 6 | 6 |
| Cas exportés uniques | 6 | 4 |
| Scénarios hypothétiques exclus | 0 | 2 |
| Rejets structurels / sémantiques stricts | 0 / 0 | 0 / 0 |
| « Rejetés » au sens agrégé du rapport | 0 | 2, tous hypothétiques |
| Doublons | 0 | 0 |
| Validité structurelle | 6/6 = 100 % | 6/6 = 100 % |
| Acceptation sémantique, avant déduplication | 6/6 = 100 % | 4/6 = 66,6667 % |
| Couverture des opérations par au moins un export | 2/2 = 100 % | 2/2 = 100 % |
| Positifs / négatifs / boundary exportés | 2 / 2 / 2 | 1 / 2 / 1 |
| Appels LLM réels déclarés | 0 | 2, sans échec déclaré |
| Temps de génération enregistré | Non disponible pour le jeu A historique | 26,728039 s, soit 26,73 s |

Le rapport de génération mock A a été remplacé par le rapport live dans le répertoire partagé. Le rapport de reproductibilité historique conserve ses métriques, mais exclut volontairement les durées. Le nouveau replay technique possède sa propre durée dans son répertoire isolé ; elle n’est pas substituée à une durée historique manquante et ne mesure aucune inférence. Le jeu mock B a aussi un rapport historique, mais ce n’est pas la source temporelle du jeu A comparé ici.

Les dénominateurs sont contrôlés dans l’audit : tous les candidats d’une enveloppe valide pour le taux structurel ; tous les candidats structurellement valides pour l’acceptation sémantique ; toutes les opérations analysées pour la couverture. Les quatre comportements exportés en live sont présents à l’identique dans le mock, en ignorant leurs noms et leurs IDs attribués après filtrage.

Le mock est écrit à la main à partir des mêmes scénarios que le validateur. Son taux de 100 % confirme un fonctionnement déterministe du pipeline et sert à la non-régression. Le live met effectivement à l’épreuve les propositions d’un modèle : il révèle ici une tendance à compléter les assertions avec des valeurs inventées. Ces deux pourcentages ne permettent donc pas de classer deux méthodes de génération sur un pied d’égalité. Une seule expérience de six cas, sur deux opérations et une spécification déjà pourvue de scénarios, ne permet aucune conclusion générale sur la qualité du modèle.

## Analyse des deux scénarios hypothétiques

| Candidat source | Requête et statut | Assertion proposée | Preuve structurée disponible | Décision |
| --- | --- | --- | --- | --- |
| ID source `1`, GET index 0, positif | `GET /products/{id}`, `id=1`, attendu 200 | `{"id":1,"name":"Product 1","price":9.99}` | `x-test-scenarios` justifie cette requête et 200, mais seulement `expected_body={"id":1}` | Maintien en hypothèse |
| ID source `3`, GET index 2, boundary | `GET /products/{id}`, `id=1000000`, attendu 200 | `{"id":1000000,"name":"Product 1000000","price":99.99}` | Le scénario justifie cette requête à la borne maximale et 200, mais seulement `expected_body={"id":1000000}` | Maintien en hypothèse |

Le motif enregistré et reproduit par le validateur est, dans les deux cas, `Concrete response assertion values lack scenario evidence`. Les requêtes ne violent pas les schémas et leurs statuts correspondent à des scénarios exacts. Le problème se situe dans les valeurs attendues de `name` et `price`.

Le schéma de réponse exige des propriétés dans une réponse complète, mais il ne donne pas leurs valeurs stockées. Le contrat v1.0 autorise une assertion partielle : il n’est pas nécessaire de remplir tous les champs requis du schéma de réponse dans `expected_body`.

En outre, le texte de précondition de la démonstration indique `Notebook`, prix 10, pour le produit 1 et `Upper bound product`, prix 20, pour le produit 1000000. Les valeurs inventées sont donc aussi différentes de ces préconditions textuelles. Ces informations ne justifient pas une réparation automatique : leur implémentation par l’API de Rimeh doit encore être confirmée, et la preuve structurée des assertions se limite actuellement aux IDs.

Une nouvelle génération pourrait proposer les seuls IDs déjà documentés, ou aucune assertion de contenu avec `expected_body=null`, pour ces requêtes exactes. Ce serait une nouvelle proposition à valider avec une preuve existante, pas une promotion rétrospective des deux candidats actuels. Aucun fichier de candidat ou d’export historique n’a été modifié.

## Vérification individuelle des quatre exports live

| ID exporté | Cas | Vérification OpenAPI et preuve | Précondition à confirmer avec Rimeh |
| --- | --- | --- | --- |
| `TC_001` | GET `id=999999`, négatif, 404 | Entier entre 1 et 1000000 ; requête et 404 correspondent au scénario exact d’absence ; aucun corps/assertion ajoutés | Le produit 999999 doit rester absent dans le jeu de données d’exécution |
| `TC_002` | POST `{"name":"Test product","price":10}`, positif, 201 | Champs requis présents, longueur et prix valides, pas de propriété inconnue, `Content-Type` correct ; scénario exact de création | Le nom et la création doivent être acceptés dans l’état initial ; vérifier une éventuelle unicité non décrite |
| `TC_003` | POST `{"price":10}`, négatif, 422 | Violation intentionnelle de `required: name` ; scénario exact et `x-validation-error-status=422` | L’API doit effectivement retourner 422 pour cette violation |
| `TC_004` | POST `{"name":"Test product","price":-1}`, boundary, 422 | Valeur juste sous `minimum=0` ; les autres contraintes sont satisfaites ; scénario exact et statut de validation 422 | Vérifier le rejet effectif et le code 422 |

Chaque endpoint conserve son template relatif, les `path_params` correspondent exactement aux variables, les IDs exportés sont uniques et tous les champs du contrat v1.0 sont présents sans ajout. Les quatre `expected_body` valent `null` : le moteur de Rimeh devra vérifier les statuts, sans inférer d’assertions de contenu supplémentaires.

| Opération | Positifs mock/live | Négatifs mock/live | Boundary mock/live |
| --- | ---: | ---: | ---: |
| GET `/products/{id}` | 1 / 0 | 1 / 1 | 1 / 0 |
| POST `/products` | 1 / 1 | 1 / 1 | 1 / 1 |

La couverture de génération à 100 % masque donc l’absence de GET positif et de GET boundary dans l’export live. Une seule des deux opérations possède un positif exporté. Aucun de ces chiffres n’est une couverture du code, des règles métier ou de comportements exécutés.

## Cohérence des rapports

L’audit vérifie notamment les égalités suivantes pour le live :

- Structure : `6 proposés = 6 valides + 0 rejet structurel`.
- Sémantique : `6 valides = 4 acceptés + 0 rejet sémantique strict + 2 hypothèses`.
- Export : `4 acceptés = 4 exports + 0 doublon`.
- Bilan : `6 proposés = 4 exports + 2 rejetés au sens agrégé + 0 doublon`.
- Le fichier d’hypothèses contient exactement deux candidats, tous deux `hypothetical`, sans violation de requête et avec le motif reproduit.
- Les deux rapports portent le mode `live`, `executable=false` pour les hypothèses, aucun échec d’opération, deux appels déclarés et zéro playback mock.

`rejections=[]` est cohérent : cette liste contient les refus structurels/sémantiques stricts, tandis que les hypothèses sont dans un fichier séparé. Le compteur agrégé `rejected_tests=2` inclut ces hypothèses par définition. `status=completed` signifie que la génération a terminé sans échec d’appel, pas que toutes les propositions sont acceptées.

Il existe une ambiguïté de nommage à préserver dans l’analyse : **`outputs/generation_report.json` décrit `generated_tests_ollama.json`, pas `generated_tests.json`**. Ce dernier reste le mock de six tests. `outputs/validation_report.json` est également une ancienne validation du mock, pas une validation des quatre exports live. L’audit détecte l’association incorrecte entre les six tests mock et le rapport live.

Les anciens rapports ne contiennent pas de lien cryptographique historique vers leurs sorties. Les empreintes calculées pendant l’audit fixent l’état analysé, sans prouver rétrospectivement la provenance. Pour les futures générations, le rapport lie désormais les chemins et SHA-256 de l’export et des hypothèses. Conserver chaque expérience dans son propre répertoire évite d’écraser un autre rapport.

## Améliorations effectivement apportées

Le prompt **1.1.0** donne la priorité à un scénario positif documenté et souligne que les champs requis d’une réponse complète ne doivent jamais compléter une assertion partielle. Une politique explicite désigne `x-test-scenarios[].expected_body` comme source des valeurs d’assertion. Le validateur n’est pas assoupli et ne répare pas les candidats.

Une commande `audit` contrôle ensemble le contrat, les décisions sémantiques, les motifs d’hypothèse, les métriques, les dénominateurs, les catégories, les doublons, les modes et les associations de fichiers. Les futurs rapports de génération enregistrent les chemins et empreintes des deux sorties annexées. Le contrat `generated_tests.json` reste inchangé.

Des tests de non-régression utilisent une copie des artefacts live observés, clairement distinguée d’une réponse brute ou d’un nouvel appel. Ils confirment les quatre acceptations, les deux exclusions, la détection des compteurs incohérents, des fichiers mélangés et des sorties modifiées après génération. Le comparatif peut être reconstruit sans réseau avec `python -m scripts.compare_mock_live`.

## Suite de l’expérience et intégration

La stratégie de données garanties, proposée sans modifier le code de Rimeh ni le contrat v1.0, est détaillée dans [RIMEH_SEED_STRATEGY.md](RIMEH_SEED_STRATEGY.md). Elle repose sur une référence de jeu initial confirmée par Rimeh, puis des scénarios exacts annotés dans une copie de la spécification côté Mariem.

Pour mesurer l’effet du prompt 1.1.0, conserver la spécification, le modèle et ses réglages, enregistrer la version/digest d’Ollama et du modèle ainsi que les conditions matérielles, puis refaire une expérience dans un nouveau répertoire. Comparer les taux, les motifs et les positifs par opération sur plusieurs répétitions ; ne pas réutiliser les quatre exports historiques comme s’ils provenaient du nouveau prompt. Ne pas annoncer un gain avant cette mesure.

La vérification finale de consolidation donne **145 tests pytest réussis**, sans réseau. L’intégration doit encore confirmer les données initiales, l’absence de 999999, les codes réels 200/201/404/422, l’isolation des créations, l’encodage des variables et l’absence de corps pour `body=null`. Les audits livrés ne remplacent pas ces exécutions.
