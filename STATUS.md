# Suivi InfoBridge — 5 septembre 2026

## Priorités : implémentées, validation d’intégration à terminer

Les fonctionnalités suivantes sont présentes dans le code. Leur présence ne vaut
pas validation sur l’environnement déployé.

- Tests PostgreSQL des permissions, sessions et transitions.
- Modification/désactivation des utilisateurs et révocation des sessions.
- Modification/suspension des institutions et révocation des sessions associées.
- Accusés de réception et suivi de lecture idempotents.
- Journaux d’audit et événements de sécurité chargés depuis l’API dans l’interface.
- Relances automatiques via le worker de cycle de vie, avec déduplication.

Les trois anciens points d’attention sont corrigés dans le code : le MFA affiche
« Non implémenté », les journaux utilisent les API et les relances sont planifiées.
Vérifier les migrations et l’activation du worker sur l’environnement cible.

## Fonctionnalités suivantes déjà présentes

- Versions des documents, archivage logique et purge sous condition de conservation.
- Stockage S3/MinIO et chiffrement par enveloppe AWS KMS.
- Exports d’audit CSV/PDF et protections append-only ORM/PostgreSQL.
- Paramètres de sécurité/conservation et référentiels configurables.
- Authentification M2M avec scopes, rotation et suspension.

## Reste à développer ou décider

- Webhooks et imports/exports métier (hors exports d’audit déjà présents).
- MFA : enrôlement, vérification et récupération avant activation obligatoire.
- Clarification ou fusion des rôles CONSULTANT et OBSERVER.

## Validation de cette reprise

- Build frontend : réussi.
- Tests unitaires backend : 11 réussis après correction de trois blocs `with`
  incorrects dans les tests de documents, dont un test d’intégration de purge.
- Ajout d’un test d’intégration des accès aux journaux : refus sans authentification
  ou pour un agent, cloisonnement institutionnel pour un auditeur et accès global
  pour un administrateur système.
- Tests d’intégration PostgreSQL : non exécutés, `TEST_DATABASE_URL` absent.
  PostgreSQL répond côté Windows, mais refuse les identifiants de développement
  par défaut. Docker est inaccessible depuis cette session WSL.
- Ne pas utiliser implicitement la base non locale configurée dans `.env`.
  Utiliser une base dédiée aux tests suivant les instructions du README.
