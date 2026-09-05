Toutes les fonctionnalités exposées et les sept rôles utilisateurs

Version 1.0 • 5 septembre 2026 • Référence de code : 8445ff9 et modifications locales de la reprise

Document de tests à exécuter. Il ne constitue pas un procès-verbal de validation ni une preuve de réussite des scénarios.

81 scénarios détaillés • matrice des habilitations • parcours par rôle • inventaire des routes API • grille de résultats CSV

Environnement : ____________________    Version déployée : ____________________

Responsable de recette : ____________________    Période : ____________________

Aucun mot de passe, jeton, secret M2M ou contenu de .env n’est inclus dans ce document.

# 1. Mode d’emploi et préparation

Exécuter sur un environnement de recette avec base et stockage dédiés. Les scénarios de suspension, verrouillage, purge et mutation SQL utilisent exclusivement des comptes et documents jetables. Conserver un administrateur de secours actif.

Pour chaque scénario : relever la version déployée, vérifier les préconditions, exécuter les étapes dans l’ordre, comparer le résultat attendu, joindre une preuve expurgée de secrets et renseigner le CSV. Les mentions AS/AI/AG/VA/CO/OB/AU sont définies ci-après.

Les scénarios métier se font dans l’interface quand la commande existe. Les contrôles négatifs, filtres avancés, renouvellements de jetons et fonctions techniques se complètent dans /docs ou un client HTTP. Les chemins API indiqués sont relatifs à /api/v1, sauf /health et /docs.

Statuts de recette : NON EXÉCUTÉ, OK, KO, BLOQUÉ, NON APPLICABLE. Une fonction absente est identifiée comme non livrée, pas déclarée OK. Joindre heure, rôle, institution, identifiant du dossier, résultat HTTP et référence d’anomalie ; ne jamais joindre de jeton.

## Jeu de données

Créer quatre institutions actives REC-A, REC-B, REC-C et REC-D. A émet vers B ; C vers D sert de témoin hors périmètre. Prévoir les sept rôles dans A et dans B, un second agent dans B et un AS de secours dans une autre institution. Les mots de passe sont distribués séparément.

Préparer des références REC-2026-001 et suivantes, les quatre classifications, cinq priorités, un dossier par état du workflow et des échéances passée/proche/lointaine. Prévoir fichiers texte, PDF valide, fichier trop volumineux, faux MIME et deux versions distinctes. Pour la purge, trois dossiers : ouvert, archivé non expiré et archivé expiré.

Relever les valeurs effectives dans Administration : seuil de verrouillage, durées des jetons, conservation, délai d’archivage et fréquence des scans. La valeur persistée en base prime sur le défaut d’environnement. Les intégrations S3/KMS nécessitent des ressources de recette opérationnelles.

## Sommaire de la campagne

AUTH-01 à AUTH-08 — Authentification et sessions

ADM-01 à ADM-10 — Institutions et utilisateurs

READ-01 à READ-07 — Consultation, tableau de bord et gouvernance

CASE-01 à CASE-14 — Cycle de vie des dossiers

DOC-01 à REC-03 — Documents et accusés de réception

NOT-01 à NOT-06 — Notifications et planification

AUD-01 à AUD-05 — Audit et événements de sécurité

SET-01 à REF-03 — Paramètres et référentiels

M2M-01 à M2M-08 — Interopérabilité M2M

OPS-01 à OPS-06 — Stockage, chiffrement et exploitation

# 2. Rôles et matrice des habilitations

## AS — Administrateur système (SYSTEM_ADMIN)

Global ; gestion institutions, comptes, paramètres, référentiels et clients globaux. Exception : un reçu exige d’appartenir à l’institution destinataire.

## AI — Administrateur institution (INSTITUTION_ADMIN)

Utilisateurs, règles et clients de son institution ; opérations métier selon le côté émetteur/destinataire. Paramètres en lecture seule.

## AG — Agent (AGENT)

Création et envoi de ses demandes ; réception et traitement des dossiers affectés ; documents selon règles.

## VA — Validateur (VALIDATOR)

Affectation, validation/rejet et clôture selon institution ; pas de création de demande ni de téléversement par défaut.

## CO — Consultant (CONSULTANT)

Lecture et téléchargement dans son périmètre ; accusés et notifications. Identique à OBSERVER dans le code actuel.

## OB — Observateur (OBSERVER)

Lecture et téléchargement dans son périmètre ; accusés et notifications. Pas de mutation de workflow.

## AU — Auditeur (AUDITOR)

Lecture des dossiers accessibles et des journaux de son institution ; exports audit ; accusés et notifications.

P = autorisé sous conditions de périmètre, d’état et de gouvernance ; D = uniquement membre de l’institution destinataire et dossier non DRAFT ; — = interdit par les contrôles de rôle des routes. Oui ne dispense pas des validations de données. Cette matrice décrit le backend actuel, à comparer avec les commandes réellement visibles dans l’interface.

Fonction | AS | AI | AG | VA | CO | OB | AU

Lire dossiers / pièces / workflow | P | P | P | P | P | P | P

Créer / envoyer / recevoir dossier | P | P | P | — | — | — | —

Démarrer / répondre / transmettre | P | P | P | — | — | — | —

Affecter / valider / clôturer | P | P | — | P | — | — | —

Archiver dossier | P | P | — | — | — | — | —

Téléverser / archiver pièce | P | P | P | — | — | — | —

Accuser réception / marquer lu | D | D | D | D | D | D | D

Créer / modifier institution | Oui | — | — | — | — | — | —

Gérer utilisateurs / sessions | Oui | P | — | — | — | — | —

Lire / exporter audit et sécurité | Oui | P | — | — | — | — | P

Configurer règles et clients M2M | Oui | P | — | — | — | — | —

Lire paramètres | Oui | Oui | — | — | — | — | —

Modifier paramètres / référentiels | Oui | — | — | — | — | — | —

Lire référentiels / institutions | Oui | Oui | Oui | Oui | Oui | Oui | Oui

Lire notifications / état worker | P | P | P | P | P | P | P

Déclencher relances manuelles | Oui | P | — | P | — | — | —

Aperçu et purge physique | Oui | — | — | — | — | — | —

Une règle de gouvernance ne remplace pas le contrôle de rôle. Pour un dossier, la règle institutionnelle est recherchée avant la règle globale ; absence de règle ne signifie pas refus par défaut. AS contourne ces règles, mais pas toutes les préconditions métier. La liste des institutions est lisible par tous les utilisateurs authentifiés.

# 3. Parcours minimal par rôle

Rôle | Scénarios à dérouler

AS | AUTH-01 ; ADM-01 à 08 ; READ-04 à 06 ; SET-01/02 ; REF-01/02 ; M2M-01/04/05/06 ; AUD-01 à 03 ; DOC-07 sur environnement jetable.

AI | AUTH-01 ; ADM-05 à 09 ; cycle de dossiers selon A ou B ; AUD-01 à 03 ; SET-01 en lecture ; M2M-01/07.

AG | AUTH-01 à 07 ; CASE-01 à 07 puis CASE-10 ; DOC-01 à 06 ; REC-01/02 ; NOT-01 ; ADM-10 en négatif.

VA | AUTH-01 ; CASE-05/08/09/11 ; NOT-03 ; lecture et téléchargements ; création et téléversement en négatif.

CO | AUTH-01 ; READ-01 à 03 et READ-07 ; DOC-06 ; REC-01 à 03 ; NOT-01/02 ; CASE-13 et ADM-10 en négatif.

OB | Même parcours que CO, avec un compte distinct et les mêmes règles afin de vérifier l’équivalence effective.

AU | AUTH-01 ; READ-01 à 03 ; DOC-06 ; REC-01/02 ; AUD-01 à 04 ; mutations métier et administration en négatif.

Parcours de bout en bout : AG-A crée et envoie ; AG-B réceptionne ; VA-B affecte à AG-B ; AG-B démarre et propose ; VA-B rejette avec motif ; AG-B corrige ; VA-B approuve ; AG-B transmet ; VA-A clôture ; AI-A archive. Contrôler documents, reçus, notifications et audit pendant ce même parcours.

Chaîne nominale : DRAFT → SENT → RECEIVED → ASSIGNED → IN_PROGRESS → PENDING_VALIDATION → APPROVED → RESPONSE_SENT → CLOSED → ARCHIVED. Branche de rejet : PENDING_VALIDATION → REJECTED → PENDING_VALIDATION. IN_REVIEW est un état accepté vers ASSIGNED dans le service ; aucune route dédiée d’entrée dans cet état n’est exposée.

# 4. Authentification et sessions

## AUTH-01 — Connexion nominale

Acteurs : Tous

Préconditions : Compte actif dans une institution active.

Étapes : Ouvrir la connexion ; saisir un e-mail valide et son mot de passe ; se connecter ; actualiser la page.

Attendu : Session ouverte, profil et rôle corrects ; données accessibles ; aucune demande MFA présentée comme effective.

Résultat : NON EXÉCUTÉ

## AUTH-02 — Saisie et mot de passe erronés

Acteurs : Tous

Préconditions : Compte de recette dédié ; seuil de verrouillage connu.

Étapes : Tester champs vides, e-mail mal formé puis un mot de passe faux ; ne pas atteindre le seuil sur le compte principal.

Attendu : Validation explicite ; aucun accès ; un échec connu incrémente le compteur et produit une trace LOGIN_FAILED.

Résultat : NON EXÉCUTÉ

## AUTH-03 — Verrouillage et réactivation

Acteurs : Tous + AS

Préconditions : Compte jetable actif ; administrateur de secours disponible.

Étapes : Atteindre le seuil configuré avec des mots de passe faux ; tenter le bon mot de passe ; faire réactiver le compte par un administrateur ; retester.

Attendu : Compte LOCKED au seuil ; bon mot de passe refusé tant que verrouillé ; connexion possible après réactivation ; événements de sécurité consultables.

Résultat : NON EXÉCUTÉ

## AUTH-04 — Déconnexion

Acteurs : Tous

Préconditions : Session authentifiée ; jeton conservé uniquement dans l’outil de recette.

Étapes : Se déconnecter ; revenir sur une page protégée ; rejouer le jeton contre GET /auth/me.

Attendu : Retour à la connexion ; ancienne session refusée par l’API (401).

Résultat : NON EXÉCUTÉ

## AUTH-05 — Rotation du renouvellement

Acteurs : Tous / API

Préconditions : Session et refresh_token de recette.

Étapes : POST /auth/refresh ; réutiliser l’ancien refresh_token ; utiliser le nouveau ; vérifier le profil.

Attendu : Nouveau jeton émis ; ancien refresh_token refusé ; nouveau jeton utilisable selon la politique de session.

Résultat : NON EXÉCUTÉ

## AUTH-06 — Jetons absents, altérés et expirés

Acteurs : Tous / API

Préconditions : Durées de test connues.

Étapes : Appeler /auth/me sans jeton, avec un jeton modifié, puis après expiration ; tester le renouvellement d’une session expirée.

Attendu : Accès refusé ; aucune donnée utilisateur divulguée ; renouvellement expiré rejeté.

Résultat : NON EXÉCUTÉ

## AUTH-07 — Compte ou institution inactifs

Acteurs : Tous

Préconditions : Compte DISABLED puis institution SUSPENDED, sur données de test.

Étapes : Tenter une connexion avec le bon mot de passe dans chaque situation.

Attendu : Connexion refusée ; après déploiement du correctif UI, message compte ou institution inactive plutôt qu’un faux diagnostic de mot de passe.

Résultat : NON EXÉCUTÉ

## AUTH-08 — Premier administrateur

Acteurs : AS / API

Préconditions : Base vierge isolée uniquement.

Étapes : POST /auth/bootstrap-admin avec un compte de test ; refaire l’appel après création.

Attendu : Premier administrateur créé ; seconde initialisation refusée ; aucun administrateur supplémentaire par cette voie.

Résultat : NON EXÉCUTÉ

# 5. Institutions et utilisateurs

## ADM-01 — Créer une institution

Acteurs : AS

Préconditions : Code REC-A disponible.

Étapes : Administration, Institutions : créer REC-A ; actualiser ; réutiliser le même code.

Attendu : Institution persistée ; code unique ; doublon refusé (409) ; trace de création.

Résultat : NON EXÉCUTÉ

## ADM-02 — Modifier une institution

Acteurs : AS

Préconditions : Institution de recette active.

Étapes : Modifier nom, code et type ; recharger ; essayer un code existant.

Attendu : Changements persistants ; doublon refusé ; événement INSTITUTION_UPDATED.

Résultat : NON EXÉCUTÉ

## ADM-03 — Suspendre et réactiver

Acteurs : AS

Préconditions : Institution B avec plusieurs sessions de test.

Étapes : Suspendre B ; rejouer les jetons de ses membres ; réactiver B ; reconnecter ses comptes.

Attendu : Sessions révoquées à la suspension ; accès refusé ; nouvelle connexion possible après réactivation, sans restauration des anciens jetons.

Résultat : NON EXÉCUTÉ

## ADM-04 — Protection du dernier administrateur

Acteurs : AS

Préconditions : Base de recette avec un seul AS actif.

Étapes : Tenter de désactiver ou rétrograder cet AS ; tenter de suspendre son institution sans AS actif ailleurs.

Attendu : Opérations refusées (409) ; un accès d’administration système reste disponible.

Résultat : NON EXÉCUTÉ

## ADM-05 — Créer les sept rôles

Acteurs : AS, AI

Préconditions : Institutions A et B actives.

Étapes : Créer les comptes du jeu de données ; tester un e-mail déjà utilisé et un mot de passe de moins de 12 caractères.

Attendu : Comptes valides persistés ; doublon et mot de passe trop court rejetés ; AI ne peut pas créer un AS.

Résultat : NON EXÉCUTÉ

## ADM-06 — Modifier un utilisateur

Acteurs : AS, AI

Préconditions : Utilisateur de recette existant.

Étapes : Modifier nom, e-mail, rôle et statut ; recharger ; contrôler son nouveau périmètre avec une nouvelle session.

Attendu : Valeurs persistées et auditées ; nouveaux droits effectifs ; désactivation révoque les sessions ; un changement de rôle est contrôlé à la requête suivante via le profil en base, sans révocation automatique pour un simple changement de rôle ou d’e-mail.

Résultat : NON EXÉCUTÉ

## ADM-07 — Désactiver un utilisateur

Acteurs : AS, AI

Préconditions : Deux sessions ouvertes pour le compte cible.

Étapes : Passer le statut à DISABLED ; utiliser les deux sessions ; tenter une nouvelle connexion.

Attendu : Anciennes sessions et nouvelle connexion refusées ; autres utilisateurs inchangés.

Résultat : NON EXÉCUTÉ

## ADM-08 — Révoquer toutes les sessions

Acteurs : AS, AI

Préconditions : Deux navigateurs connectés avec le compte cible.

Étapes : Cliquer sur la révocation des sessions ; appeler /auth/me dans les deux navigateurs ; reconnecter le compte.

Attendu : Toutes les anciennes sessions refusées ; compte toujours actif et nouvelle connexion possible ; nombre de sessions révoquées annoncé.

Résultat : NON EXÉCUTÉ

## ADM-09 — Cloisonnement administratif

Acteurs : AI

Préconditions : AI de A ; comptes et institutions de B.

Étapes : Lister les utilisateurs ; tenter via API de modifier ou révoquer un compte de B, de gérer un AS ou de modifier une institution.

Attendu : Liste limitée à A ; opérations hors périmètre et gestion des institutions refusées.

Résultat : NON EXÉCUTÉ

## ADM-10 — Administration interdite

Acteurs : AG, VA, CO, OB, AU

Préconditions : Un compte de chaque rôle.

Étapes : Tester menus et appels directs de création/modification utilisateurs et institutions, puis révocation de sessions.

Attendu : Aucune écriture administrative ; API refuse même si une commande est construite manuellement.

Résultat : NON EXÉCUTÉ

# 6. Consultation, tableau de bord et gouvernance

## READ-01 — Tableau de bord

Acteurs : Tous

Préconditions : Dossiers connus dans A, B et C.

Étapes : Se connecter successivement avec les sept rôles ; consulter indicateurs, alertes et journal récent ; comparer avec les listes/API.

Attendu : Écran exploitable ; compteurs cohérents avec leur périmètre ; relever toute donnée de démonstration ou fuite interinstitutionnelle.

Résultat : NON EXÉCUTÉ

## READ-02 — Recherche et filtres

Acteurs : Tous

Préconditions : Dossiers de références, statuts, dates, priorités et classifications variés.

Étapes : Rechercher référence, objet et texte ; combiner filtres disponibles ; compléter par GET /cases avec filtres dates, affectation, limit et offset.

Attendu : Résultats conformes aux filtres et au périmètre ; état vide lisible ; aucun doublon entre pages sur jeu stable.

Résultat : NON EXÉCUTÉ

## READ-03 — Isolation des dossiers

Acteurs : Tous sauf AS

Préconditions : A vers B ; dossier distinct entre C et D ; compte non affecté.

Étapes : Lister les dossiers ; forcer les identifiants C/D dans les routes workflow, documents et receipts.

Attendu : Dossier C/D absent des listes ; lecture directe refusée ; aucune pièce ni historique divulgué.

Résultat : NON EXÉCUTÉ

## READ-04 — Règle de refus

Acteurs : AS, AI + rôles métier

Préconditions : Dossier accessible ; règle cases.send autorisée au départ.

Étapes : Créer une règle cases.send=false pour AG ; tenter un envoi ; remettre la règle à sa valeur initiale.

Attendu : Envoi refusé (403) malgré rôle normalement autorisé ; modification de règle auditée.

Résultat : NON EXÉCUTÉ

## READ-05 — Plafond de classification

Acteurs : AS, AI + rôles métier

Préconditions : Quatre dossiers PUBLIC, INTERNE, CONFIDENTIEL, SECRET.

Étapes : Fixer cases.read au maximum INTERNE pour le rôle testé ; lister et ouvrir les dossiers ; répéter pour documents.read et documents.download.

Attendu : Classements au-dessus du plafond refusés pour la permission testée ; règles de documents testées séparément de cases.read.

Résultat : NON EXÉCUTÉ

## READ-06 — Priorité des règles

Acteurs : AS, AI / API

Préconditions : Règle globale et règle institutionnelle pour même rôle/permission.

Étapes : Définir des valeurs contradictoires ; vérifier le comportement dans A et B ; tenter une règle de B avec AI de A.

Attendu : Règle institutionnelle prioritaire ; règle globale appliquée en son absence ; AI ne modifie que son périmètre et pas le rôle AS.

Résultat : NON EXÉCUTÉ

## READ-07 — Comparer consultant et observateur

Acteurs : CO, OB

Préconditions : Deux comptes dans A avec règles identiques.

Étapes : Exécuter mêmes lectures, téléchargements et actions de workflow ; tester accusés en tant que destinataire.

Attendu : Droits actuellement identiques ; mutations de workflow refusées ; receipts possibles comme destinataire. Toute distinction future nécessite une décision métier.

Résultat : NON EXÉCUTÉ

# 7. Cycle de vie des dossiers

## CASE-01 — Créer une demande

Acteurs : AS, AI, AG

Préconditions : Institutions actives ; utilisateur de A.

Étapes : Créer une référence unique avec objet, description, priorité, classification, destinataire B et échéance ; recharger.

Attendu : Dossier DRAFT persistant ; champs exacts ; une référence dupliquée ou des données invalides sont refusées.

Résultat : NON EXÉCUTÉ

## CASE-02 — Envoyer une demande

Acteurs : AG de A

Préconditions : DRAFT créé par cet agent.

Étapes : Envoyer la demande ; consulter historique ; ouvrir les notifications des responsables de B.

Attendu : Statut SENT, date d’envoi, action CASE_SENT ; notification aux administrateurs/validateurs destinataires.

Résultat : NON EXÉCUTÉ

## CASE-03 — Envoi par un autre agent

Acteurs : AG de A

Préconditions : DRAFT créé par un second agent.

Étapes : Tenter l’envoi avec un agent qui n’est pas créateur.

Attendu : Refus 403 ; statut et historique métier inchangés.

Résultat : NON EXÉCUTÉ

## CASE-04 — Réceptionner

Acteurs : AS, AI, AG de B

Préconditions : Dossier SENT de A vers B.

Étapes : Réceptionner ; consulter historique et reçus.

Attendu : RECEIVED et date de réception ; receipt créé lorsque l’acteur appartient à B.

Résultat : NON EXÉCUTÉ

## CASE-05 — Affecter

Acteurs : AS, AI, VA de B

Préconditions : Dossier RECEIVED ; agent actif de B.

Étapes : Affecter au compte AG-B ; tester séparément un compte inactif ou appartenant à A.

Attendu : ASSIGNED pour AG-B ; notification d’affectation ; destinataire invalide refusé.

Résultat : NON EXÉCUTÉ

## CASE-06 — Démarrer le traitement

Acteurs : AS, AI, AG affecté de B

Préconditions : Dossier ASSIGNED à AG-B.

Étapes : Démarrer avec AG-B ; sur un second dossier tenter avec un autre agent.

Attendu : IN_PROGRESS pour l’agent affecté ; agent non affecté refusé.

Résultat : NON EXÉCUTÉ

## CASE-07 — Proposer une réponse

Acteurs : AS, AI, AG affecté de B

Préconditions : Dossier IN_PROGRESS.

Étapes : Saisir le corps de réponse et le commentaire ; soumettre.

Attendu : PENDING_VALIDATION ; texte persistant ; notification aux responsables de validation.

Résultat : NON EXÉCUTÉ

## CASE-08 — Approuver

Acteurs : AS, AI, VA de B

Préconditions : Dossier PENDING_VALIDATION.

Étapes : Approuver ; consulter historique et dates.

Attendu : APPROVED ; validateur et date enregistrés ; trace RESPONSE_VALIDATED.

Résultat : NON EXÉCUTÉ

## CASE-09 — Rejeter et corriger

Acteurs : AS, AI, VA de B puis AG-B

Préconditions : Dossier PENDING_VALIDATION.

Étapes : Rejeter sans commentaire puis avec motif ; corriger la réponse avec l’agent affecté ; soumettre à nouveau.

Attendu : Sans motif : 422 ; avec motif : REJECTED ; correction ramène à PENDING_VALIDATION.

Résultat : NON EXÉCUTÉ

## CASE-10 — Transmettre la réponse

Acteurs : AS, AI, AG affecté de B

Préconditions : Dossier APPROVED.

Étapes : Envoyer la réponse ; consulter depuis A et vérifier la notification du créateur.

Attendu : RESPONSE_SENT ; date renseignée ; réponse consultable et créateur notifié.

Résultat : NON EXÉCUTÉ

## CASE-11 — Clôturer

Acteurs : AS, AI, VA de A

Préconditions : Dossier RESPONSE_SENT.

Étapes : Clôturer depuis l’institution émettrice A ; tenter depuis B avec un rôle non système sur un second dossier.

Attendu : CLOSED avec date et historique ; clôture par B refusée.

Résultat : NON EXÉCUTÉ

## CASE-12 — Archiver

Acteurs : AS, AI de A

Préconditions : Dossier CLOSED.

Étapes : Archiver avec une date de conservation explicite ; retrouver le dossier dans les archives.

Attendu : ARCHIVED ; retention_until conforme ; visibilité contrôlée par les filtres ; aucune transition sortante de ARCHIVED.

Résultat : NON EXÉCUTÉ

## CASE-13 — Transitions et rôles interdits

Acteurs : Tous / API

Préconditions : Un dossier par état de la chaîne.

Étapes : Tenter DRAFT vers réception, ASSIGNED vers réponse, puis actions après archivage ; répéter chaque mutation avec CO, OB et AU.

Attendu : Transitions invalides : 409 pour acteur autorisé ; rôles interdits : 403 ; aucune mutation partielle.

Résultat : NON EXÉCUTÉ

## CASE-14 — Historique de traitement

Acteurs : Tous

Préconditions : Dossier ayant terminé CASE-01 à CASE-12.

Étapes : Ouvrir l’historique ; comparer acteurs, commentaires et ordre avec le parcours effectué ; tester l’API workflow.

Attendu : Historique cohérent avec les actions persistées et limité au périmètre de lecture autorisé.

Résultat : NON EXÉCUTÉ

# 8. Documents et accusés de réception

## DOC-01 — Ajouter une pièce

Acteurs : AS, AI, AG

Préconditions : Dossier accessible ; fichier texte/PDF valide.

Étapes : Ajouter une pièce REQUEST puis RESPONSE ; télécharger et comparer au fichier original.

Attendu : Métadonnées cohérentes ; contenu restitué identique ; traces DOCUMENT_UPLOADED et DOCUMENT_DOWNLOADED.

Résultat : NON EXÉCUTÉ

## DOC-02 — Valider les fichiers

Acteurs : AS, AI, AG / API

Préconditions : Limites effectives connues ; fichiers de recette.

Étapes : Envoyer un fichier trop volumineux, un MIME interdit et un contenu ne correspondant pas au MIME annoncé.

Attendu : Refus 413 pour taille, 415 pour type/contenu ; aucune pièce valide créée pour ces entrées.

Résultat : NON EXÉCUTÉ

## DOC-03 — Créer une version

Acteurs : AS, AI, AG

Préconditions : Pièce version 1 existante.

Étapes : Ajouter un remplacement ; ouvrir les versions ; télécharger les deux versions.

Attendu : Même logical_document_id ; version incrémentée et lien supersedes_id ; anciennes versions consultables sous réserve d’archivage.

Résultat : NON EXÉCUTÉ

## DOC-04 — Version d’un autre dossier

Acteurs : AS, AI, AG / API

Préconditions : Deux dossiers avec pièces distinctes.

Étapes : Envoyer replaces_attachment_id d’une pièce d’un autre dossier ou déjà archivée.

Attendu : Refus ; aucune association documentaire entre dossiers.

Résultat : NON EXÉCUTÉ

## DOC-05 — Archiver une pièce

Acteurs : AS, AI, AG

Préconditions : Document de recette non purgé.

Étapes : Archiver ; rafraîchir la liste ; appeler son téléchargement direct ; vérifier le stockage.

Attendu : Pièce masquée des listes actives ; téléchargement refusé ; suppression logique, sans purge immédiate du fichier.

Résultat : NON EXÉCUTÉ

## DOC-06 — Accès aux pièces

Acteurs : Tous

Préconditions : Dossier accessible puis hors périmètre ; règles documents distinctes.

Étapes : Tester liste, versions et téléchargement pour chaque rôle ; refuser documents.download par gouvernance.

Attendu : Lecture autorisée seulement selon périmètre et règles ; CO/OB/AU ne peuvent pas téléverser ni archiver.

Résultat : NON EXÉCUTÉ

## DOC-07 — Aperçu et purge contrôlée

Acteurs : AS / technique

Préconditions : Base et stockage jetables ; trois dossiers : ouvert, archivé non expiré, archivé expiré.

Étapes : Consulter purge-preview ; tenter confirmation incorrecte ; purger avec PURGE_EXPIRED_DOCUMENTS.

Attendu : Seuls fichiers éligibles supprimés ; dossiers ouverts/non expirés préservés ; compteurs et audit ; métadonnées et empreintes conservées.

Résultat : NON EXÉCUTÉ

## DOC-08 — Purge répétée et panne stockage

Acteurs : AS / technique

Préconditions : Document expiré de test ; stockage contrôlable.

Étapes : Purger deux fois ; simuler échec de suppression sur un autre fichier ; relancer après rétablissement.

Attendu : Pas de double purge effective ; échec comptabilisé ; document non marqué purgé à tort ; reprise possible.

Résultat : NON EXÉCUTÉ

## REC-01 — Accuser réception

Acteurs : Tous les rôles de B

Préconditions : Dossier SENT de A vers B.

Étapes : Créer un accusé ; refaire l’action ; consulter les reçus depuis A.

Attendu : Même reçu pour le même acteur ; pas de doublon ; reçu visible par les lecteurs autorisés de A.

Résultat : NON EXÉCUTÉ

## REC-02 — Marquer comme lu

Acteurs : Tous les rôles de B

Préconditions : Dossier non brouillon, reçu existant ou absent.

Étapes : Marquer lu ; noter read_at ; répéter.

Attendu : Reçu créé si nécessaire ; date de lecture renseignée une seule fois.

Résultat : NON EXÉCUTÉ

## REC-03 — Limiter les accusés au destinataire

Acteurs : Tous / API

Préconditions : Compte de A, compte de C, AS hors B et dossier DRAFT.

Étapes : Tenter d’accuser depuis A/C/AS hors B ; depuis B tenter sur DRAFT.

Attendu : Hors B : 403, même pour AS ; DRAFT : 409 ; aucun reçu indûment créé.

Résultat : NON EXÉCUTÉ

# 9. Notifications et planification

## NOT-01 — Consulter et lire les notifications

Acteurs : Tous

Préconditions : Notifications personnelles et institutionnelles de test.

Étapes : Ouvrir les notifications ; filtrer si proposé ; marquer une notification puis toutes comme lues ; rafraîchir.

Attendu : État persistant ; compteur cohérent ; seules notifications personnelles ou de l’institution concernées.

Résultat : NON EXÉCUTÉ

## NOT-02 — Notification étrangère

Acteurs : Tous / API

Préconditions : Notification privée d’un autre utilisateur hors institution.

Étapes : Forcer son identifiant dans PATCH /notifications/{id}/read.

Attendu : 404 ; aucune modification étrangère.

Résultat : NON EXÉCUTÉ

## NOT-03 — Scanner manuellement

Acteurs : AS, AI, VA

Préconditions : Dossier proche échéance, dossier en retard et dossier clôturé.

Étapes : Lancer les alertes ; relancer le même jour ; comparer les notifications.

Attendu : Alertes adaptées aux dossiers ouverts ; pas de duplication journalière ; périmètre institutionnel pour AI/VA.

Résultat : NON EXÉCUTÉ

## NOT-04 — Relances automatiques

Acteurs : Technique + AS

Préconditions : Worker actif ; intervalle de recette 60 secondes ; échéances préparées.

Étapes : Démarrer le backend ; attendre un scan sans cliquer sur Scanner ; consulter /operations/lifecycle-status et les notifications.

Attendu : Scan au démarrage puis périodique ; last_completed_at renseigné ; alertes créées automatiquement ; last_error absent en fonctionnement nominal.

Résultat : NON EXÉCUTÉ

## NOT-05 — Concurrence et reprise

Acteurs : Technique + AS

Préconditions : Deux instances backend sur la base jetable.

Étapes : Déclencher deux scans simultanés ; vérifier le verrou ; provoquer puis corriger une indisponibilité temporaire.

Attendu : Un scan concurrent peut être ignoré ; pas de doublons ; erreur journalisée puis reprise au scan suivant.

Résultat : NON EXÉCUTÉ

## NOT-06 — Archivage automatique

Acteurs : Technique + AS

Préconditions : Dossier CLOSED plus ancien que auto_archive_days ; dossier récent témoin.

Étapes : Exécuter un cycle automatique ; consulter statuts et dates de conservation.

Attendu : Ancien dossier archivé avec politique de conservation ; dossier récent conservé dans son état.

Résultat : NON EXÉCUTÉ

# 10. Audit et événements de sécurité

## AUD-01 — Journal réel et filtres

Acteurs : AS, AI, AU

Préconditions : Action de création puis connexion échouée sur compte test.

Étapes : Ouvrir Journal d’audit ; rechercher l’action, le type d’entité et la date ; comparer à l’API.

Attendu : Traces issues de la base, acteur/date/action cohérents ; filtres API action/entity_type et limites respectés.

Résultat : NON EXÉCUTÉ

## AUD-02 — Cloisonnement des journaux

Acteurs : AS, AI, AU

Préconditions : Traces de A, de B et traces globales.

Étapes : Comparer AS, AI-A et AU-A ; appeler les API avec AG/VA/CO/OB et sans jeton.

Attendu : AS voit le global ; AI/AU limités à leur institution ; autres rôles et anonymes refusés.

Résultat : NON EXÉCUTÉ

## AUD-03 — Export CSV et PDF

Acteurs : AS, AI, AU

Préconditions : Journal avec accents et métadonnées.

Étapes : Exporter dans les deux formats ; ouvrir les fichiers ; filtrer dates/actions via API ; vérifier l’audit de l’export.

Attendu : CSV UTF-8 lisible et PDF valide ; périmètre identique au journal ; événement AUDIT_EXPORTED ; aucun secret dans l’export.

Résultat : NON EXÉCUTÉ

## AUD-04 — Événements de sécurité

Acteurs : AS, AI, AU

Préconditions : Échecs de connexion atteignant seuil d’alerte.

Étapes : Consulter les événements ; filtrer par sévérité via API ; comparer institution et compteur d’échecs.

Attendu : FAILED_LOGIN_THRESHOLD et niveau approprié ; isolation institutionnelle ; données réelles.

Résultat : NON EXÉCUTÉ

## AUD-05 — Journal append-only

Acteurs : Technique

Préconditions : Base jetable migrée ; rôle SQL d’exécution non superutilisateur.

Étapes : Tenter UPDATE, DELETE et TRUNCATE sur audit_logs ; tenter mutation ORM ; vérifier insertion et lecture.

Attendu : Mutations refusées par triggers/ORM ; INSERT et SELECT possibles ; noter qu’un superutilisateur contrôle toujours la base.

Résultat : NON EXÉCUTÉ

# 11. Paramètres et référentiels

## SET-01 — Lire et modifier les paramètres

Acteurs : AS, AI

Préconditions : Administration accessible.

Étapes : AS modifie un paramètre puis recharge ; AI consulte et tente le même PUT par API.

Attendu : AS persiste et audite la valeur ; AI lecture seule ; source database après enregistrement.

Résultat : NON EXÉCUTÉ

## SET-02 — Bornes de configuration

Acteurs : AS / API

Préconditions : Valeurs initiales consignées.

Étapes : Pour chaque paramètre entier, essayer minimum-1, maximum+1 et texte ; pour un booléen envoyer un entier ; restaurer les valeurs.

Attendu : 422 pour type/bornes invalides ; valeur précédente conservée ; valeurs légales acceptées.

Résultat : NON EXÉCUTÉ

## SET-03 — MFA honnêtement présenté

Acteurs : Tous

Préconditions : Écran sécurité de la version testée.

Étapes : Lire le statut MFA ; se connecter avec un compte mfa_enabled=true provenant d’un seed.

Attendu : MFA affiché Non implémenté ; aucun second facteur effectif ; ne pas déclarer la fonctionnalité livrée.

Résultat : NON EXÉCUTÉ

## REF-01 — Personnaliser les référentiels

Acteurs : AS

Préconditions : Types institutions, priorités, classifications et usages de pièces existants.

Étapes : Modifier libellé, description et ordre dans chaque catalogue ; recharger les formulaires.

Attendu : Affichage mis à jour ; codes stables inchangés ; trace REFERENCE_ITEM_UPDATED.

Résultat : NON EXÉCUTÉ

## REF-02 — Désactiver une valeur

Acteurs : AS + AG

Préconditions : Valeur non obligatoire utilisée dans un dossier historique.

Étapes : Désactiver ; tenter une nouvelle création utilisant le code via API ; consulter l’ancien dossier.

Attendu : Nouvelle utilisation refusée ; historique lisible ; valeurs obligatoires protégées.

Résultat : NON EXÉCUTÉ

## REF-03 — Référentiels en lecture seule

Acteurs : AI, AG, VA, CO, OB, AU

Préconditions : Compte de chaque rôle.

Étapes : Lire GET /reference-data ; tenter PUT sur une entrée.

Attendu : Lecture authentifiée autorisée ; écriture réservée à AS.

Résultat : NON EXÉCUTÉ

# 12. Interopérabilité M2M

## M2M-01 — Créer un client API

Acteurs : AS, AI

Préconditions : Institution active ; écran Interopérabilité.

Étapes : Créer un client cases:read ; relever le secret dans un coffre de recette ; recharger la liste.

Attendu : Client créé ; secret affiché à la création seulement ; AI limité à son institution ; seul AS peut créer un client global.

Résultat : NON EXÉCUTÉ

## M2M-02 — Obtenir un jeton

Acteurs : Client API

Préconditions : Client actif, clé et secret de test.

Étapes : POST /integrations/token ; appeler /external/cases et /external/cases/{id}.

Attendu : Jeton utilisable ; dossiers limités au périmètre du client ; détail hors périmètre refusé.

Résultat : NON EXÉCUTÉ

## M2M-03 — Scopes documentaires

Acteurs : Client API

Préconditions : Client cases:read seul puis client documents:read.

Étapes : Tester liste/téléchargement des pièces via /external ; répéter avec scope documentaire.

Attendu : Scope manquant refusé ; scope requis autorise uniquement les pièces du périmètre autorisé.

Résultat : NON EXÉCUTÉ

## M2M-04 — Réduire les scopes

Acteurs : AS, AI + client

Préconditions : Jeton existant avec deux scopes.

Étapes : Retirer documents:read ; réutiliser l’ancien jeton ; obtenir un nouveau jeton et retester.

Attendu : Ancien jeton invalidé ; nouveau limité aux scopes conservés.

Résultat : NON EXÉCUTÉ

## M2M-05 — Rotation du secret

Acteurs : AS, AI + client

Préconditions : Client actif et jeton existant.

Étapes : Faire tourner le secret ; essayer l’ancien secret et l’ancien jeton ; utiliser le nouveau secret.

Attendu : Anciens identifiants/jetons refusés ; nouveau secret fonctionnel et non réaffiché dans la liste.

Résultat : NON EXÉCUTÉ

## M2M-06 — Suspension

Acteurs : AS, AI + client

Préconditions : Client institutionnel et jeton actif.

Étapes : Suspendre le client ; retester ; réactiver puis suspendre son institution dans un second essai.

Attendu : Jetons refusés immédiatement pendant suspension du client ou de l’institution.

Résultat : NON EXÉCUTÉ

## M2M-07 — Contrôles de gestion

Acteurs : AI, autres rôles / API

Préconditions : Clients A et B.

Étapes : AI-A tente lecture/modification/rotation du client B ; autres rôles tentent création ; soumettre un scope inventé.

Attendu : Accès hors périmètre et rôles non administrateurs refusés ; scope non supporté rejeté.

Résultat : NON EXÉCUTÉ

## M2M-08 — Authentification erronée et séparation

Acteurs : Client API

Préconditions : Client de recette ; jeton utilisateur distinct.

Étapes : Utiliser un mauvais secret ; présenter un jeton M2M à /auth/me et un jeton utilisateur à une route externe.

Attendu : Mauvais secret refusé et événement de sécurité ; types de jetons non interchangeables.

Résultat : NON EXÉCUTÉ

# 13. Stockage, chiffrement et exploitation

## OPS-01 — Stockage local et S3/MinIO

Acteurs : Technique

Préconditions : Stockages de recette configurés séparément.

Étapes : Téléverser/télécharger en local puis S3 ; redémarrer ; télécharger une ancienne pièce locale après bascule.

Attendu : Pièces persistantes ; chaque pièce utilise son backend enregistré ; anciennes pièces locales lisibles si leur volume reste monté.

Résultat : NON EXÉCUTÉ

## OPS-02 — Rotation Fernet

Acteurs : Technique

Préconditions : Trousseau avec clé V1 ; pièce V1 existante.

Étapes : Ajouter V2 et la rendre active ; téléverser ; lire anciennes et nouvelles pièces ; retirer V1 dans un environnement jetable.

Attendu : Nouveaux fichiers utilisent V2 ; anciens lisibles tant que V1 disponible ; erreur explicite sans ancienne clé, jamais de contenu clair retourné à tort.

Résultat : NON EXÉCUTÉ

## OPS-03 — AWS KMS

Acteurs : Technique

Préconditions : Clé KMS et droits GenerateDataKey/Decrypt de recette.

Étapes : Téléverser en mode aws_kms ; inspecter métadonnées et stockage ; télécharger ; retirer temporairement Decrypt.

Attendu : AES256_GCM_AWS_KMS ; clé de données stockée enveloppée ; lecture fidèle autorisée ; refus/erreur sans droit de déchiffrement.

Résultat : NON EXÉCUTÉ

## OPS-04 — Déploiement et migrations

Acteurs : Technique

Préconditions : Environnement jetable et configuration relevée.

Étapes : Appliquer alembic upgrade head ; démarrer backend/frontend ; vérifier /health et /docs ; redémarrer.

Attendu : Migrations jusqu’à 0016 ; santé répond ; schémas et écrans accessibles ; persistance après redémarrage.

Résultat : NON EXÉCUTÉ

## OPS-05 — Navigation et erreurs réseau

Acteurs : Tous

Préconditions : Navigateur bureau puis largeur mobile.

Étapes : Parcourir menus accessibles ; actualiser une route ; tester listes vides ; couper puis rétablir l’API.

Attendu : Navigation adaptée ; erreurs lisibles ; aucune réussite affichée pour une opération échouée ; reprise possible.

Résultat : NON EXÉCUTÉ

## OPS-06 — Modules non livrés

Acteurs : Tous + responsable recette

Préconditions : Raccourcis de l’interface visibles.

Étapes : Examiner MFA, webhooks, imports/exports métier et éventuels écrans À brancher ; rechercher une messagerie autonome.

Attendu : Consigner comme non livré tout module sans parcours/API ; ne pas confondre réponse de dossier avec messagerie ni export audit avec export métier.

Résultat : NON EXÉCUTÉ

# Annexe A. Inventaire des routes et couverture

Inventaire extrait du routeur du code de référence. Les routes de cette annexe sont couvertes par les familles indiquées ; chaque scénario doit aussi être exécuté avec les rôles interdits pertinents. Les payloads exacts et champs requis sont disponibles dans /docs de la version déployée.

Méthode et chemin relatif | Famille

GET /dashboard | READ

POST /auth/login | AUTH

POST /auth/refresh | AUTH

POST /auth/logout | AUTH

POST /auth/bootstrap-admin | AUTH

GET /auth/me | AUTH

GET /institutions | ADM

POST /institutions | ADM

GET /users | ADM

GET /audit-logs | AUD

GET /audit-logs/export | AUD

GET /security-events | AUD

GET /users/assignees | ADM

POST /users | ADM

PATCH /users/{user_id} | ADM

POST /users/{user_id}/sessions/revoke | ADM

PATCH /institutions/{institution_id} | ADM

GET /cases | CASE / READ

POST /cases | CASE / READ

POST /cases/{case_id}/send | CASE / READ

POST /cases/{case_id}/receive | CASE / READ

POST /cases/{case_id}/assign | CASE / READ

POST /cases/{case_id}/response | CASE / READ

POST /cases/{case_id}/start | CASE / READ

POST /cases/{case_id}/validate | CASE / READ

POST /cases/{case_id}/send-response | CASE / READ

POST /cases/{case_id}/close | CASE / READ

POST /cases/{case_id}/archive | CASE / READ

GET /cases/{case_id}/workflow | CASE / READ

GET /documents/purge-preview | DOC

POST /documents/purge-expired | DOC

POST /cases/{case_id}/attachments | DOC

GET /cases/{case_id}/attachments/{attachment_id}/versions | DOC

POST /cases/{case_id}/attachments/{attachment_id}/archive | DOC

GET /cases/{case_id}/receipts | REC

POST /cases/{case_id}/receipts | REC

PATCH /cases/{case_id}/receipts/read | REC

GET /cases/{case_id}/attachments | DOC

GET /cases/{case_id}/attachments/{attachment_id}/download | DOC

GET /notifications | NOT

PATCH /notifications/{notification_id}/read | NOT

PATCH /notifications/read-all | NOT

POST /notifications/due-alerts/run | NOT

GET /operations/lifecycle-status | NOT

GET /integrations/scopes | M2M

POST /integrations/api-clients | M2M

GET /integrations/api-clients | M2M

PATCH /integrations/api-clients/{client_id} | M2M

POST /integrations/api-clients/{client_id}/rotate-secret | M2M

POST /integrations/token | M2M

GET /external/cases | M2M

GET /external/cases/{case_id} | M2M

GET /external/cases/{case_id}/attachments | M2M

GET /external/cases/{case_id}/attachments/{attachment_id}/download | M2M

GET /governance/access-rules | READ

PUT /governance/access-rules | READ

GET /settings | SET

PUT /settings/{setting_key} | SET

GET /reference-data | REF

PUT /reference-data/{catalog}/{code} | REF

GET /health (hors préfixe API) | OPS

# Annexe B. Bornes à tester

Paramètre | Minimum | Maximum

access_token_minutes | 5 | 1440

refresh_token_days | 1 | 90

login_lock_threshold | 3 | 20

auto_archive_days | 1 | 3650

default_retention_days | 1 | 36500

due_soon_hours | 1 | 720

lifecycle_interval_seconds | 60 | 86400

Booléens : document_purge_enabled et due_alerts_enabled. La taille et les MIME de fichiers dépendent de la configuration effective ; le défaut du code est 25 Mio. Ne pas réduire une politique réelle de conservation pour accélérer un test.

# Annexe C. Limites et critères de clôture

Non livrés dans le code examiné : MFA opérationnel, webhooks et imports/exports métier génériques. Les modèles de messages ne constituent pas à eux seuls une messagerie autonome livrée. Pas de route de restauration documentaire ni de changement de mot de passe utilisateur dans le routeur examiné ; ne pas promettre ces parcours. CONSULTANT/OBSERVER restent à clarifier métier.

Points à observer : droits API versus boutons UI ; pagination après filtrage de gouvernance ; visibilité des brouillons pour le destinataire ; compteurs globaux du tableau de bord ; lecture partagée des notifications institutionnelles ; conservation explicite lors de l’archivage manuel. Consigner les écarts aux exigences métier même si le comportement correspond au code.

Historique de vérification de la reprise : build frontend réussi ; 11 tests unitaires backend réussis ; tests PostgreSQL d’intégration non exécutés faute de base de test configurée. Aucun scénario manuel de ce document n’est présenté comme exécuté. Les tests KMS existants utilisent un faux client et ne prouvent pas une intégration AWS réelle.

Clôture proposée : tous les parcours nominaux des sept rôles exécutés ; aucun accès hors périmètre, contournement de rôle, session révoquée acceptée ou perte de document ; anomalies bloquantes corrigées et retestées ; fonctions non livrées acceptées explicitement hors périmètre. Joindre le CSV final et les preuves.

Bilan : OK ____  KO ____  BLOQUÉ ____  NON APPLICABLE ____  NON EXÉCUTÉ ____

Décision : ACCEPTÉ / ACCEPTÉ AVEC RÉSERVES / REFUSÉ     Responsable : ____________________

## Sources de référence

backend/app/api/routes.py

backend/app/api/deps.py

backend/app/models/common.py

backend/app/services/workflow.py

backend/app/services/permissions.py

backend/app/services/documents.py

backend/app/services/lifecycle.py

backend/app/services/platform_settings.py

backend/app/services/reference_data.py

backend/tests/test_api_integration.py

frontend/src/App.tsx

README.md
