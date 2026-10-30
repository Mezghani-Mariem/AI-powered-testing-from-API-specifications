# Données initiales garanties — stratégie d’intégration proposée

Le contrat JSON v1.0 peut transporter des valeurs initiales concrètes dans `path_params`, `query_params`, `body` et `expected_body`. Il ne décrit ni la création des fixtures ni leur durée de validité. La stratégie proposée conserve cette interface et utilise des preuves séparées, versionnées côté Mariem.

## Source de vérité à obtenir de Rimeh

Demander une référence vérifiable au jeu initial réellement chargé par son API : version du dataset, révision ou empreinte du script de seed/fixture, environnement concerné, spécification correspondante et conditions de réinitialisation. Rimeh doit confirmer quels identifiants existent, lesquels sont garantis absents, et quels attributs restent stables pendant l’exécution. Une réponse observée une fois, un exemple OpenAPI ou une valeur par défaut ne constituent pas à eux seuls une garantie de seed.

Conserver cette information dans un manifeste de preuve séparé (par exemple `integration_evidence/rimeh_seed_manifest.json`, à créer seulement quand les valeurs sont confirmées). Ce fichier n’est pas transmis comme contrat de test et n’est pas chargé automatiquement par le générateur actuel. Il peut contenir la version du dataset, la référence du seed, l’empreinte de la spécification, la date de confirmation et les faits garantis. Aucune clé d’authentification n’y est nécessaire.

Le jeu décrit dans `examples/sample_openapi.json` est une demande de fixture pour la démonstration : produit 1, produit 1000000 et absence de 999999. Il n’est pas encore une preuve que l’API de Rimeh charge effectivement ces données. Si son jeu initial diffère, utiliser ses valeurs confirmées ou conserver les scénarios incertains ; ne pas modifier son module pour satisfaire artificiellement un résultat de génération.

## Utilisation simple, sans nouveau contrat ni chargeur complexe

1. Mariem et Rimeh conviennent d’un petit dataset de test, réinitialisable, pour l’environnement d’intégration. Si le seed actuel convient déjà, le référencer sans changer son implémentation.
2. Mariem conserve le manifeste de preuve et une copie annotée de la spécification dans son propre périmètre. Elle conserve les endpoints, schémas et réponses de la spécification de Rimeh et ajoute des `x-test-scenarios` uniquement pour les requêtes dont le résultat et les préconditions sont confirmés. La révision de cette copie et son hash relient l’expérience à la preuve.
3. Pour un GET positif, sélectionner l’ID confirmé existant. Documenter le statut 200 pour cette requête exacte. Commencer par `expected_body={"id": <ID confirmé>}` si cette propriété est stable et garantie ; utiliser `null` si seul le statut est garanti. N’ajouter `name` ou `price` que si leurs valeurs exactes sont confirmées et inscrites dans l’assertion du scénario.
4. Pour un GET inexistant, exiger l’ID confirmé absent et le statut applicable. Une borne maximale de schéma ne prouve ni l’existence ni l’absence d’une ressource. Ne pas créer un GET boundary positif à la valeur maximale si cette ressource n’est pas dans le seed.
5. Générer de nouveaux tests et les auditer contre la copie annotée. Le fichier final reste exactement `{"schema_version":"1.0","tests":[...]}` avec les champs officiels. Transmettre à Rimeh le fichier choisi et une référence séparée au dataset requis, sans ajouter de champ de précondition au contrat.
6. Avant chaque exécution dans son moteur, vérifier que l’environnement contient la bonne version initiale. L’exécution, le reset, l’injection des secrets et les mesures HTTP restent dans le périmètre de Rimeh. Une confirmation de seed n’est valable que tant que les tests et opérations extérieures ne l’ont pas invalidée.

Cette stratégie utilise le support existant des `x-test-scenarios` ; aucun import du code de Rimeh ni fusion automatique de manifeste n’est ajouté. Le template `endpoint` conserve `{id}` et le contrat reçoit uniquement une valeur concrète déjà justifiée dans `path_params`.

## Produire davantage de positifs utiles

Pour les lectures de ressources, préférer quelques IDs confirmés et leurs assertions minimales. Les deux candidats live actuels ne deviennent pas acceptés : ils gardent leurs assertions non prouvées et restent hors de l’export. Une future génération qui limite correctement l’assertion aux faits documentés sera examinée séparément, avec sa propre version de prompt et ses métriques.

Pour les créations, une requête conforme au schéma n’a pas besoin d’un ID préexistant. Vérifier toutefois les contraintes métier supplémentaires : unicité du nom, quotas, références étrangères et état initial. Employer des requêtes documentées indépendantes et isoler les créations ; aucune capture d’ID d’un POST ne doit alimenter implicitement un autre cas, car v1.0 ne représente pas ce lien.

Pour les limites, un POST à un prix minimal autorisé peut être pertinent si son succès est effectivement garanti. Si une ressource située à une borne de schéma n’est pas garantie, conserver seulement un scénario différent dont le résultat est confirmé ; ne pas fabriquer de ressource de lecture pour atteindre une catégorie ou un quota.

## Vérifications à l’intégration

| Sujet | Vérification attendue |
| --- | --- |
| Source | La spécification utilisée décrit bien l’API et la version déployées |
| Seed | Référence de dataset confirmée ; IDs présents/absents et attributs stables vérifiés |
| Statuts | GET 200/404 et POST 201/422 réellement conformes ; expliquer tout écart avec la spécification |
| Indépendance | Réinitialisation ou isolation ; aucune lecture ne dépend d’un POST précédent |
| Requêtes | Chemins relatifs, substitution encodée des variables et headers respectés |
| Négatifs | L’exécuteur conserve volontairement les champs manquants/valeurs invalides et ne les répare pas |
| Assertions | `body=null` n’envoie aucun corps ; `expected_body=null` n’ajoute aucune assertion de contenu ; un objet partiel compare uniquement ses propriétés |
| Provenance | Les tests, leur rapport, leurs hypothèses et le hash OpenAPI appartiennent à la même expérience |

Les hypothèses restent exclues tant que la preuve manque. Ni les bons scores du mock ni une couverture d’opérations de 100 % ne remplacent ces vérifications.
