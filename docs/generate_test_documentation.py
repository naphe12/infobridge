"""Generate the French acceptance test handbook, source Markdown and execution CSV."""
from pathlib import Path
from xml.sax.saxutils import escape
import ast
import csv
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs'
sections = []
def group(title, rows):
    sections.append((title, [line.split('|') for line in rows.strip().splitlines()]))

group('Authentification et sessions', '''
AUTH-01|Tous|Connexion nominale|Compte actif dans une institution active.|Ouvrir la connexion ; saisir un e-mail valide et son mot de passe ; se connecter ; actualiser la page.|Session ouverte, profil et rôle corrects ; données accessibles ; aucune demande MFA présentée comme effective.
AUTH-02|Tous|Saisie et mot de passe erronés|Compte de recette dédié ; seuil de verrouillage connu.|Tester champs vides, e-mail mal formé puis un mot de passe faux ; ne pas atteindre le seuil sur le compte principal.|Validation explicite ; aucun accès ; un échec connu incrémente le compteur et produit une trace LOGIN_FAILED.
AUTH-03|Tous + AS|Verrouillage et réactivation|Compte jetable actif ; administrateur de secours disponible.|Atteindre le seuil configuré avec des mots de passe faux ; tenter le bon mot de passe ; faire réactiver le compte par un administrateur ; retester.|Compte LOCKED au seuil ; bon mot de passe refusé tant que verrouillé ; connexion possible après réactivation ; événements de sécurité consultables.
AUTH-04|Tous|Déconnexion|Session authentifiée ; jeton conservé uniquement dans l’outil de recette.|Se déconnecter ; revenir sur une page protégée ; rejouer le jeton contre GET /auth/me.|Retour à la connexion ; ancienne session refusée par l’API (401).
AUTH-05|Tous / API|Rotation du renouvellement|Session et refresh_token de recette.|POST /auth/refresh ; réutiliser l’ancien refresh_token ; utiliser le nouveau ; vérifier le profil.|Nouveau jeton émis ; ancien refresh_token refusé ; nouveau jeton utilisable selon la politique de session.
AUTH-06|Tous / API|Jetons absents, altérés et expirés|Durées de test connues.|Appeler /auth/me sans jeton, avec un jeton modifié, puis après expiration ; tester le renouvellement d’une session expirée.|Accès refusé ; aucune donnée utilisateur divulguée ; renouvellement expiré rejeté.
AUTH-07|Tous|Compte ou institution inactifs|Compte DISABLED puis institution SUSPENDED, sur données de test.|Tenter une connexion avec le bon mot de passe dans chaque situation.|Connexion refusée ; après déploiement du correctif UI, message compte ou institution inactive plutôt qu’un faux diagnostic de mot de passe.
AUTH-08|AS / API|Premier administrateur|Base vierge isolée uniquement.|POST /auth/bootstrap-admin avec un compte de test ; refaire l’appel après création.|Premier administrateur créé ; seconde initialisation refusée ; aucun administrateur supplémentaire par cette voie.
''')
group('Institutions et utilisateurs', '''
ADM-01|AS|Créer une institution|Code REC-A disponible.|Administration, Institutions : créer REC-A ; actualiser ; réutiliser le même code.|Institution persistée ; code unique ; doublon refusé (409) ; trace de création.
ADM-02|AS|Modifier une institution|Institution de recette active.|Modifier nom, code et type ; recharger ; essayer un code existant.|Changements persistants ; doublon refusé ; événement INSTITUTION_UPDATED.
ADM-03|AS|Suspendre et réactiver|Institution B avec plusieurs sessions de test.|Suspendre B ; rejouer les jetons de ses membres ; réactiver B ; reconnecter ses comptes.|Sessions révoquées à la suspension ; accès refusé ; nouvelle connexion possible après réactivation, sans restauration des anciens jetons.
ADM-04|AS|Protection du dernier administrateur|Base de recette avec un seul AS actif.|Tenter de désactiver ou rétrograder cet AS ; tenter de suspendre son institution sans AS actif ailleurs.|Opérations refusées (409) ; un accès d’administration système reste disponible.
ADM-05|AS, AI|Créer les sept rôles|Institutions A et B actives.|Créer les comptes du jeu de données ; tester un e-mail déjà utilisé et un mot de passe de moins de 12 caractères.|Comptes valides persistés ; doublon et mot de passe trop court rejetés ; AI ne peut pas créer un AS.
ADM-06|AS, AI|Modifier un utilisateur|Utilisateur de recette existant.|Modifier nom, e-mail, rôle et statut ; recharger ; contrôler son nouveau périmètre avec une nouvelle session.|Valeurs persistées et auditées ; nouveaux droits effectifs ; désactivation révoque les sessions ; un changement de rôle est contrôlé à la requête suivante via le profil en base, sans révocation automatique pour un simple changement de rôle ou d’e-mail.
ADM-07|AS, AI|Désactiver un utilisateur|Deux sessions ouvertes pour le compte cible.|Passer le statut à DISABLED ; utiliser les deux sessions ; tenter une nouvelle connexion.|Anciennes sessions et nouvelle connexion refusées ; autres utilisateurs inchangés.
ADM-08|AS, AI|Révoquer toutes les sessions|Deux navigateurs connectés avec le compte cible.|Cliquer sur la révocation des sessions ; appeler /auth/me dans les deux navigateurs ; reconnecter le compte.|Toutes les anciennes sessions refusées ; compte toujours actif et nouvelle connexion possible ; nombre de sessions révoquées annoncé.
ADM-09|AI|Cloisonnement administratif|AI de A ; comptes et institutions de B.|Lister les utilisateurs ; tenter via API de modifier ou révoquer un compte de B, de gérer un AS ou de modifier une institution.|Liste limitée à A ; opérations hors périmètre et gestion des institutions refusées.
ADM-10|AG, VA, CO, OB, AU|Administration interdite|Un compte de chaque rôle.|Tester menus et appels directs de création/modification utilisateurs et institutions, puis révocation de sessions.|Aucune écriture administrative ; API refuse même si une commande est construite manuellement.
''')
group('Consultation, tableau de bord et gouvernance', '''
READ-01|Tous|Tableau de bord|Dossiers connus dans A, B et C.|Se connecter successivement avec les sept rôles ; consulter indicateurs, alertes et journal récent ; comparer avec les listes/API.|Écran exploitable ; compteurs cohérents avec leur périmètre ; relever toute donnée de démonstration ou fuite interinstitutionnelle.
READ-02|Tous|Recherche et filtres|Dossiers de références, statuts, dates, priorités et classifications variés.|Rechercher référence, objet et texte ; combiner filtres disponibles ; compléter par GET /cases avec filtres dates, affectation, limit et offset.|Résultats conformes aux filtres et au périmètre ; état vide lisible ; aucun doublon entre pages sur jeu stable.
READ-03|Tous sauf AS|Isolation des dossiers|A vers B ; dossier distinct entre C et D ; compte non affecté.|Lister les dossiers ; forcer les identifiants C/D dans les routes workflow, documents et receipts.|Dossier C/D absent des listes ; lecture directe refusée ; aucune pièce ni historique divulgué.
READ-04|AS, AI + rôles métier|Règle de refus|Dossier accessible ; règle cases.send autorisée au départ.|Créer une règle cases.send=false pour AG ; tenter un envoi ; remettre la règle à sa valeur initiale.|Envoi refusé (403) malgré rôle normalement autorisé ; modification de règle auditée.
READ-05|AS, AI + rôles métier|Plafond de classification|Quatre dossiers PUBLIC, INTERNE, CONFIDENTIEL, SECRET.|Fixer cases.read au maximum INTERNE pour le rôle testé ; lister et ouvrir les dossiers ; répéter pour documents.read et documents.download.|Classements au-dessus du plafond refusés pour la permission testée ; règles de documents testées séparément de cases.read.
READ-06|AS, AI / API|Priorité des règles|Règle globale et règle institutionnelle pour même rôle/permission.|Définir des valeurs contradictoires ; vérifier le comportement dans A et B ; tenter une règle de B avec AI de A.|Règle institutionnelle prioritaire ; règle globale appliquée en son absence ; AI ne modifie que son périmètre et pas le rôle AS.
READ-07|CO, OB|Comparer consultant et observateur|Deux comptes dans A avec règles identiques.|Exécuter mêmes lectures, téléchargements et actions de workflow ; tester accusés en tant que destinataire.|Droits actuellement identiques ; mutations de workflow refusées ; receipts possibles comme destinataire. Toute distinction future nécessite une décision métier.
''')
group('Cycle de vie des dossiers', '''
CASE-01|AS, AI, AG|Créer une demande|Institutions actives ; utilisateur de A.|Créer une référence unique avec objet, description, priorité, classification, destinataire B et échéance ; recharger.|Dossier DRAFT persistant ; champs exacts ; une référence dupliquée ou des données invalides sont refusées.
CASE-02|AG de A|Envoyer une demande|DRAFT créé par cet agent.|Envoyer la demande ; consulter historique ; ouvrir les notifications des responsables de B.|Statut SENT, date d’envoi, action CASE_SENT ; notification aux administrateurs/validateurs destinataires.
CASE-03|AG de A|Envoi par un autre agent|DRAFT créé par un second agent.|Tenter l’envoi avec un agent qui n’est pas créateur.|Refus 403 ; statut et historique métier inchangés.
CASE-04|AS, AI, AG de B|Réceptionner|Dossier SENT de A vers B.|Réceptionner ; consulter historique et reçus.|RECEIVED et date de réception ; receipt créé lorsque l’acteur appartient à B.
CASE-05|AS, AI, VA de B|Affecter|Dossier RECEIVED ; agent actif de B.|Affecter au compte AG-B ; tester séparément un compte inactif ou appartenant à A.|ASSIGNED pour AG-B ; notification d’affectation ; destinataire invalide refusé.
CASE-06|AS, AI, AG affecté de B|Démarrer le traitement|Dossier ASSIGNED à AG-B.|Démarrer avec AG-B ; sur un second dossier tenter avec un autre agent.|IN_PROGRESS pour l’agent affecté ; agent non affecté refusé.
CASE-07|AS, AI, AG affecté de B|Proposer une réponse|Dossier IN_PROGRESS.|Saisir le corps de réponse et le commentaire ; soumettre.|PENDING_VALIDATION ; texte persistant ; notification aux responsables de validation.
CASE-08|AS, AI, VA de B|Approuver|Dossier PENDING_VALIDATION.|Approuver ; consulter historique et dates.|APPROVED ; validateur et date enregistrés ; trace RESPONSE_VALIDATED.
CASE-09|AS, AI, VA de B puis AG-B|Rejeter et corriger|Dossier PENDING_VALIDATION.|Rejeter sans commentaire puis avec motif ; corriger la réponse avec l’agent affecté ; soumettre à nouveau.|Sans motif : 422 ; avec motif : REJECTED ; correction ramène à PENDING_VALIDATION.
CASE-10|AS, AI, AG affecté de B|Transmettre la réponse|Dossier APPROVED.|Envoyer la réponse ; consulter depuis A et vérifier la notification du créateur.|RESPONSE_SENT ; date renseignée ; réponse consultable et créateur notifié.
CASE-11|AS, AI, VA de A|Clôturer|Dossier RESPONSE_SENT.|Clôturer depuis l’institution émettrice A ; tenter depuis B avec un rôle non système sur un second dossier.|CLOSED avec date et historique ; clôture par B refusée.
CASE-12|AS, AI de A|Archiver|Dossier CLOSED.|Archiver avec une date de conservation explicite ; retrouver le dossier dans les archives.|ARCHIVED ; retention_until conforme ; visibilité contrôlée par les filtres ; aucune transition sortante de ARCHIVED.
CASE-13|Tous / API|Transitions et rôles interdits|Un dossier par état de la chaîne.|Tenter DRAFT vers réception, ASSIGNED vers réponse, puis actions après archivage ; répéter chaque mutation avec CO, OB et AU.|Transitions invalides : 409 pour acteur autorisé ; rôles interdits : 403 ; aucune mutation partielle.
CASE-14|Tous|Historique de traitement|Dossier ayant terminé CASE-01 à CASE-12.|Ouvrir l’historique ; comparer acteurs, commentaires et ordre avec le parcours effectué ; tester l’API workflow.|Historique cohérent avec les actions persistées et limité au périmètre de lecture autorisé.
''')
group('Documents et accusés de réception', '''
DOC-01|AS, AI, AG|Ajouter une pièce|Dossier accessible ; fichier texte/PDF valide.|Ajouter une pièce REQUEST puis RESPONSE ; télécharger et comparer au fichier original.|Métadonnées cohérentes ; contenu restitué identique ; traces DOCUMENT_UPLOADED et DOCUMENT_DOWNLOADED.
DOC-02|AS, AI, AG / API|Valider les fichiers|Limites effectives connues ; fichiers de recette.|Envoyer un fichier trop volumineux, un MIME interdit et un contenu ne correspondant pas au MIME annoncé.|Refus 413 pour taille, 415 pour type/contenu ; aucune pièce valide créée pour ces entrées.
DOC-03|AS, AI, AG|Créer une version|Pièce version 1 existante.|Ajouter un remplacement ; ouvrir les versions ; télécharger les deux versions.|Même logical_document_id ; version incrémentée et lien supersedes_id ; anciennes versions consultables sous réserve d’archivage.
DOC-04|AS, AI, AG / API|Version d’un autre dossier|Deux dossiers avec pièces distinctes.|Envoyer replaces_attachment_id d’une pièce d’un autre dossier ou déjà archivée.|Refus ; aucune association documentaire entre dossiers.
DOC-05|AS, AI, AG|Archiver une pièce|Document de recette non purgé.|Archiver ; rafraîchir la liste ; appeler son téléchargement direct ; vérifier le stockage.|Pièce masquée des listes actives ; téléchargement refusé ; suppression logique, sans purge immédiate du fichier.
DOC-06|Tous|Accès aux pièces|Dossier accessible puis hors périmètre ; règles documents distinctes.|Tester liste, versions et téléchargement pour chaque rôle ; refuser documents.download par gouvernance.|Lecture autorisée seulement selon périmètre et règles ; CO/OB/AU ne peuvent pas téléverser ni archiver.
DOC-07|AS / technique|Aperçu et purge contrôlée|Base et stockage jetables ; trois dossiers : ouvert, archivé non expiré, archivé expiré.|Consulter purge-preview ; tenter confirmation incorrecte ; purger avec PURGE_EXPIRED_DOCUMENTS.|Seuls fichiers éligibles supprimés ; dossiers ouverts/non expirés préservés ; compteurs et audit ; métadonnées et empreintes conservées.
DOC-08|AS / technique|Purge répétée et panne stockage|Document expiré de test ; stockage contrôlable.|Purger deux fois ; simuler échec de suppression sur un autre fichier ; relancer après rétablissement.|Pas de double purge effective ; échec comptabilisé ; document non marqué purgé à tort ; reprise possible.
REC-01|Tous les rôles de B|Accuser réception|Dossier SENT de A vers B.|Créer un accusé ; refaire l’action ; consulter les reçus depuis A.|Même reçu pour le même acteur ; pas de doublon ; reçu visible par les lecteurs autorisés de A.
REC-02|Tous les rôles de B|Marquer comme lu|Dossier non brouillon, reçu existant ou absent.|Marquer lu ; noter read_at ; répéter.|Reçu créé si nécessaire ; date de lecture renseignée une seule fois.
REC-03|Tous / API|Limiter les accusés au destinataire|Compte de A, compte de C, AS hors B et dossier DRAFT.|Tenter d’accuser depuis A/C/AS hors B ; depuis B tenter sur DRAFT.|Hors B : 403, même pour AS ; DRAFT : 409 ; aucun reçu indûment créé.
''')
group('Notifications et planification', '''
NOT-01|Tous|Consulter et lire les notifications|Notifications personnelles et institutionnelles de test.|Ouvrir les notifications ; filtrer si proposé ; marquer une notification puis toutes comme lues ; rafraîchir.|État persistant ; compteur cohérent ; seules notifications personnelles ou de l’institution concernées.
NOT-02|Tous / API|Notification étrangère|Notification privée d’un autre utilisateur hors institution.|Forcer son identifiant dans PATCH /notifications/{id}/read.|404 ; aucune modification étrangère.
NOT-03|AS, AI, VA|Scanner manuellement|Dossier proche échéance, dossier en retard et dossier clôturé.|Lancer les alertes ; relancer le même jour ; comparer les notifications.|Alertes adaptées aux dossiers ouverts ; pas de duplication journalière ; périmètre institutionnel pour AI/VA.
NOT-04|Technique + AS|Relances automatiques|Worker actif ; intervalle de recette 60 secondes ; échéances préparées.|Démarrer le backend ; attendre un scan sans cliquer sur Scanner ; consulter /operations/lifecycle-status et les notifications.|Scan au démarrage puis périodique ; last_completed_at renseigné ; alertes créées automatiquement ; last_error absent en fonctionnement nominal.
NOT-05|Technique + AS|Concurrence et reprise|Deux instances backend sur la base jetable.|Déclencher deux scans simultanés ; vérifier le verrou ; provoquer puis corriger une indisponibilité temporaire.|Un scan concurrent peut être ignoré ; pas de doublons ; erreur journalisée puis reprise au scan suivant.
NOT-06|Technique + AS|Archivage automatique|Dossier CLOSED plus ancien que auto_archive_days ; dossier récent témoin.|Exécuter un cycle automatique ; consulter statuts et dates de conservation.|Ancien dossier archivé avec politique de conservation ; dossier récent conservé dans son état.
''')
group('Audit et événements de sécurité', '''
AUD-01|AS, AI, AU|Journal réel et filtres|Action de création puis connexion échouée sur compte test.|Ouvrir Journal d’audit ; rechercher l’action, le type d’entité et la date ; comparer à l’API.|Traces issues de la base, acteur/date/action cohérents ; filtres API action/entity_type et limites respectés.
AUD-02|AS, AI, AU|Cloisonnement des journaux|Traces de A, de B et traces globales.|Comparer AS, AI-A et AU-A ; appeler les API avec AG/VA/CO/OB et sans jeton.|AS voit le global ; AI/AU limités à leur institution ; autres rôles et anonymes refusés.
AUD-03|AS, AI, AU|Export CSV et PDF|Journal avec accents et métadonnées.|Exporter dans les deux formats ; ouvrir les fichiers ; filtrer dates/actions via API ; vérifier l’audit de l’export.|CSV UTF-8 lisible et PDF valide ; périmètre identique au journal ; événement AUDIT_EXPORTED ; aucun secret dans l’export.
AUD-04|AS, AI, AU|Événements de sécurité|Échecs de connexion atteignant seuil d’alerte.|Consulter les événements ; filtrer par sévérité via API ; comparer institution et compteur d’échecs.|FAILED_LOGIN_THRESHOLD et niveau approprié ; isolation institutionnelle ; données réelles.
AUD-05|Technique|Journal append-only|Base jetable migrée ; rôle SQL d’exécution non superutilisateur.|Tenter UPDATE, DELETE et TRUNCATE sur audit_logs ; tenter mutation ORM ; vérifier insertion et lecture.|Mutations refusées par triggers/ORM ; INSERT et SELECT possibles ; noter qu’un superutilisateur contrôle toujours la base.
''')
group('Paramètres et référentiels', '''
SET-01|AS, AI|Lire et modifier les paramètres|Administration accessible.|AS modifie un paramètre puis recharge ; AI consulte et tente le même PUT par API.|AS persiste et audite la valeur ; AI lecture seule ; source database après enregistrement.
SET-02|AS / API|Bornes de configuration|Valeurs initiales consignées.|Pour chaque paramètre entier, essayer minimum-1, maximum+1 et texte ; pour un booléen envoyer un entier ; restaurer les valeurs.|422 pour type/bornes invalides ; valeur précédente conservée ; valeurs légales acceptées.
SET-03|Tous|MFA honnêtement présenté|Écran sécurité de la version testée.|Lire le statut MFA ; se connecter avec un compte mfa_enabled=true provenant d’un seed.|MFA affiché Non implémenté ; aucun second facteur effectif ; ne pas déclarer la fonctionnalité livrée.
REF-01|AS|Personnaliser les référentiels|Types institutions, priorités, classifications et usages de pièces existants.|Modifier libellé, description et ordre dans chaque catalogue ; recharger les formulaires.|Affichage mis à jour ; codes stables inchangés ; trace REFERENCE_ITEM_UPDATED.
REF-02|AS + AG|Désactiver une valeur|Valeur non obligatoire utilisée dans un dossier historique.|Désactiver ; tenter une nouvelle création utilisant le code via API ; consulter l’ancien dossier.|Nouvelle utilisation refusée ; historique lisible ; valeurs obligatoires protégées.
REF-03|AI, AG, VA, CO, OB, AU|Référentiels en lecture seule|Compte de chaque rôle.|Lire GET /reference-data ; tenter PUT sur une entrée.|Lecture authentifiée autorisée ; écriture réservée à AS.
''')
group('Interopérabilité M2M', '''
M2M-01|AS, AI|Créer un client API|Institution active ; écran Interopérabilité.|Créer un client cases:read ; relever le secret dans un coffre de recette ; recharger la liste.|Client créé ; secret affiché à la création seulement ; AI limité à son institution ; seul AS peut créer un client global.
M2M-02|Client API|Obtenir un jeton|Client actif, clé et secret de test.|POST /integrations/token ; appeler /external/cases et /external/cases/{id}.|Jeton utilisable ; dossiers limités au périmètre du client ; détail hors périmètre refusé.
M2M-03|Client API|Scopes documentaires|Client cases:read seul puis client documents:read.|Tester liste/téléchargement des pièces via /external ; répéter avec scope documentaire.|Scope manquant refusé ; scope requis autorise uniquement les pièces du périmètre autorisé.
M2M-04|AS, AI + client|Réduire les scopes|Jeton existant avec deux scopes.|Retirer documents:read ; réutiliser l’ancien jeton ; obtenir un nouveau jeton et retester.|Ancien jeton invalidé ; nouveau limité aux scopes conservés.
M2M-05|AS, AI + client|Rotation du secret|Client actif et jeton existant.|Faire tourner le secret ; essayer l’ancien secret et l’ancien jeton ; utiliser le nouveau secret.|Anciens identifiants/jetons refusés ; nouveau secret fonctionnel et non réaffiché dans la liste.
M2M-06|AS, AI + client|Suspension|Client institutionnel et jeton actif.|Suspendre le client ; retester ; réactiver puis suspendre son institution dans un second essai.|Jetons refusés immédiatement pendant suspension du client ou de l’institution.
M2M-07|AI, autres rôles / API|Contrôles de gestion|Clients A et B.|AI-A tente lecture/modification/rotation du client B ; autres rôles tentent création ; soumettre un scope inventé.|Accès hors périmètre et rôles non administrateurs refusés ; scope non supporté rejeté.
M2M-08|Client API|Authentification erronée et séparation|Client de recette ; jeton utilisateur distinct.|Utiliser un mauvais secret ; présenter un jeton M2M à /auth/me et un jeton utilisateur à une route externe.|Mauvais secret refusé et événement de sécurité ; types de jetons non interchangeables.
''')
group('Stockage, chiffrement et exploitation', '''
OPS-01|Technique|Stockage local et S3/MinIO|Stockages de recette configurés séparément.|Téléverser/télécharger en local puis S3 ; redémarrer ; télécharger une ancienne pièce locale après bascule.|Pièces persistantes ; chaque pièce utilise son backend enregistré ; anciennes pièces locales lisibles si leur volume reste monté.
OPS-02|Technique|Rotation Fernet|Trousseau avec clé V1 ; pièce V1 existante.|Ajouter V2 et la rendre active ; téléverser ; lire anciennes et nouvelles pièces ; retirer V1 dans un environnement jetable.|Nouveaux fichiers utilisent V2 ; anciens lisibles tant que V1 disponible ; erreur explicite sans ancienne clé, jamais de contenu clair retourné à tort.
OPS-03|Technique|AWS KMS|Clé KMS et droits GenerateDataKey/Decrypt de recette.|Téléverser en mode aws_kms ; inspecter métadonnées et stockage ; télécharger ; retirer temporairement Decrypt.|AES256_GCM_AWS_KMS ; clé de données stockée enveloppée ; lecture fidèle autorisée ; refus/erreur sans droit de déchiffrement.
OPS-04|Technique|Déploiement et migrations|Environnement jetable et configuration relevée.|Appliquer alembic upgrade head ; démarrer backend/frontend ; vérifier /health et /docs ; redémarrer.|Migrations jusqu’à 0016 ; santé répond ; schémas et écrans accessibles ; persistance après redémarrage.
OPS-05|Tous|Navigation et erreurs réseau|Navigateur bureau puis largeur mobile.|Parcourir menus accessibles ; actualiser une route ; tester listes vides ; couper puis rétablir l’API.|Navigation adaptée ; erreurs lisibles ; aucune réussite affichée pour une opération échouée ; reprise possible.
OPS-06|Tous + responsable recette|Modules non livrés|Raccourcis de l’interface visibles.|Examiner MFA, webhooks, imports/exports métier et éventuels écrans À brancher ; rechercher une messagerie autonome.|Consigner comme non livré tout module sans parcours/API ; ne pas confondre réponse de dossier avec messagerie ni export audit avec export métier.
''')

roles = [
('AS','SYSTEM_ADMIN','Administrateur système','Global ; gestion institutions, comptes, paramètres, référentiels et clients globaux. Exception : un reçu exige d’appartenir à l’institution destinataire.'),
('AI','INSTITUTION_ADMIN','Administrateur institution','Utilisateurs, règles et clients de son institution ; opérations métier selon le côté émetteur/destinataire. Paramètres en lecture seule.'),
('AG','AGENT','Agent','Création et envoi de ses demandes ; réception et traitement des dossiers affectés ; documents selon règles.'),
('VA','VALIDATOR','Validateur','Affectation, validation/rejet et clôture selon institution ; pas de création de demande ni de téléversement par défaut.'),
('CO','CONSULTANT','Consultant','Lecture et téléchargement dans son périmètre ; accusés et notifications. Identique à OBSERVER dans le code actuel.'),
('OB','OBSERVER','Observateur','Lecture et téléchargement dans son périmètre ; accusés et notifications. Pas de mutation de workflow.'),
('AU','AUDITOR','Auditeur','Lecture des dossiers accessibles et des journaux de son institution ; exports audit ; accusés et notifications.')]
matrix = [
('Lire dossiers / pièces / workflow','P','P','P','P','P','P','P'),
('Créer / envoyer / recevoir dossier','P','P','P','—','—','—','—'),
('Démarrer / répondre / transmettre','P','P','P','—','—','—','—'),
('Affecter / valider / clôturer','P','P','—','P','—','—','—'),
('Archiver dossier','P','P','—','—','—','—','—'),
('Téléverser / archiver pièce','P','P','P','—','—','—','—'),
('Accuser réception / marquer lu','D','D','D','D','D','D','D'),
('Créer / modifier institution','Oui','—','—','—','—','—','—'),
('Gérer utilisateurs / sessions','Oui','P','—','—','—','—','—'),
('Lire / exporter audit et sécurité','Oui','P','—','—','—','—','P'),
('Configurer règles et clients M2M','Oui','P','—','—','—','—','—'),
('Lire paramètres','Oui','Oui','—','—','—','—','—'),
('Modifier paramètres / référentiels','Oui','—','—','—','—','—','—'),
('Lire référentiels / institutions','Oui','Oui','Oui','Oui','Oui','Oui','Oui'),
('Lire notifications / état worker','P','P','P','P','P','P','P'),
('Déclencher relances manuelles','Oui','P','—','P','—','—','—'),
('Aperçu et purge physique','Oui','—','—','—','—','—','—')]

styles=getSampleStyleSheet()
styles.add(ParagraphStyle(name='BodyFR',fontName='Helvetica',fontSize=9,leading=13,spaceAfter=6,textColor=colors.HexColor('#24364b')))
styles.add(ParagraphStyle(name='SmallFR',parent=styles['BodyFR'],fontSize=7.4,leading=10,spaceAfter=3))
styles['Title'].textColor=colors.HexColor('#123555')
styles['Heading1'].textColor=colors.HexColor('#123555')
styles['Heading2'].textColor=colors.HexColor('#137c86')
styles['Heading2'].fontSize=12
story=[]; md=[]
def p(t,sty='BodyFR'):
 return Paragraph(escape(t),styles[sty])
def para(t):
 story.append(p(t)); md.append(t+'\n')
def heading(t,level=1):
 story.append(p(t,'Heading1' if level==1 else 'Heading2')); md.append('#'*level+' '+t+'\n')
def table(rows,widths):
 data=[[p(str(cell),'SmallFR') for cell in row] for row in rows]
 obj=Table(data,colWidths=widths,repeatRows=1,hAlign='LEFT')
 obj.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e0eef3')),('VALIGN',(0,0),(-1,-1),'TOP'),('GRID',(0,0),(-1,-1),.35,colors.HexColor('#ccd7df')),('LEFTPADDING',(0,0),(-1,-1),5),('RIGHTPADDING',(0,0),(-1,-1),5),('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5)]))
 story.append(obj); story.append(Spacer(1,10))
 md.extend([' | '.join(map(str,row))+'\n' for row in rows])

story.append(Spacer(1,70)); story.append(p('INFOBRIDGE','Title'))
story.append(p('Cahier de recette fonctionnelle et technique','Title'))
para('Toutes les fonctionnalités exposées et les sept rôles utilisateurs')
para('Version 1.0 • 5 septembre 2026 • Référence de code : 8445ff9 et modifications locales de la reprise')
para('Document de tests à exécuter. Il ne constitue pas un procès-verbal de validation ni une preuve de réussite des scénarios.')
count=sum(len(rows) for _,rows in sections)
para(f'{count} scénarios détaillés • matrice des habilitations • parcours par rôle • inventaire des routes API • grille de résultats CSV')
para('Environnement : ____________________    Version déployée : ____________________')
para('Responsable de recette : ____________________    Période : ____________________')
para('Aucun mot de passe, jeton, secret M2M ou contenu de .env n’est inclus dans ce document.')
story.append(PageBreak())
heading('1. Mode d’emploi et préparation')
para('Exécuter sur un environnement de recette avec base et stockage dédiés. Les scénarios de suspension, verrouillage, purge et mutation SQL utilisent exclusivement des comptes et documents jetables. Conserver un administrateur de secours actif.')
para('Pour chaque scénario : relever la version déployée, vérifier les préconditions, exécuter les étapes dans l’ordre, comparer le résultat attendu, joindre une preuve expurgée de secrets et renseigner le CSV. Les mentions AS/AI/AG/VA/CO/OB/AU sont définies ci-après.')
para('Les scénarios métier se font dans l’interface quand la commande existe. Les contrôles négatifs, filtres avancés, renouvellements de jetons et fonctions techniques se complètent dans /docs ou un client HTTP. Les chemins API indiqués sont relatifs à /api/v1, sauf /health et /docs.')
para('Statuts de recette : NON EXÉCUTÉ, OK, KO, BLOQUÉ, NON APPLICABLE. Une fonction absente est identifiée comme non livrée, pas déclarée OK. Joindre heure, rôle, institution, identifiant du dossier, résultat HTTP et référence d’anomalie ; ne jamais joindre de jeton.')
heading('Jeu de données',2)
para('Créer quatre institutions actives REC-A, REC-B, REC-C et REC-D. A émet vers B ; C vers D sert de témoin hors périmètre. Prévoir les sept rôles dans A et dans B, un second agent dans B et un AS de secours dans une autre institution. Les mots de passe sont distribués séparément.')
para('Préparer des références REC-2026-001 et suivantes, les quatre classifications, cinq priorités, un dossier par état du workflow et des échéances passée/proche/lointaine. Prévoir fichiers texte, PDF valide, fichier trop volumineux, faux MIME et deux versions distinctes. Pour la purge, trois dossiers : ouvert, archivé non expiré et archivé expiré.')
para('Relever les valeurs effectives dans Administration : seuil de verrouillage, durées des jetons, conservation, délai d’archivage et fréquence des scans. La valeur persistée en base prime sur le défaut d’environnement. Les intégrations S3/KMS nécessitent des ressources de recette opérationnelles.')
heading('Sommaire de la campagne',2)
for title,rows in sections: para(f'{rows[0][0]} à {rows[-1][0]} — {title}')
story.append(PageBreak())
heading('2. Rôles et matrice des habilitations')
for short,code,label,desc in roles:
 heading(f'{short} — {label} ({code})',2); para(desc)
para('P = autorisé sous conditions de périmètre, d’état et de gouvernance ; D = uniquement membre de l’institution destinataire et dossier non DRAFT ; — = interdit par les contrôles de rôle des routes. Oui ne dispense pas des validations de données. Cette matrice décrit le backend actuel, à comparer avec les commandes réellement visibles dans l’interface.')
table([('Fonction','AS','AI','AG','VA','CO','OB','AU'),*matrix],[220,37,37,37,37,37,37,37])
para('Une règle de gouvernance ne remplace pas le contrôle de rôle. Pour un dossier, la règle institutionnelle est recherchée avant la règle globale ; absence de règle ne signifie pas refus par défaut. AS contourne ces règles, mais pas toutes les préconditions métier. La liste des institutions est lisible par tous les utilisateurs authentifiés.')
heading('3. Parcours minimal par rôle')
paths=[
('AS','AUTH-01 ; ADM-01 à 08 ; READ-04 à 06 ; SET-01/02 ; REF-01/02 ; M2M-01/04/05/06 ; AUD-01 à 03 ; DOC-07 sur environnement jetable.'),
('AI','AUTH-01 ; ADM-05 à 09 ; cycle de dossiers selon A ou B ; AUD-01 à 03 ; SET-01 en lecture ; M2M-01/07.'),
('AG','AUTH-01 à 07 ; CASE-01 à 07 puis CASE-10 ; DOC-01 à 06 ; REC-01/02 ; NOT-01 ; ADM-10 en négatif.'),
('VA','AUTH-01 ; CASE-05/08/09/11 ; NOT-03 ; lecture et téléchargements ; création et téléversement en négatif.'),
('CO','AUTH-01 ; READ-01 à 03 et READ-07 ; DOC-06 ; REC-01 à 03 ; NOT-01/02 ; CASE-13 et ADM-10 en négatif.'),
('OB','Même parcours que CO, avec un compte distinct et les mêmes règles afin de vérifier l’équivalence effective.'),
('AU','AUTH-01 ; READ-01 à 03 ; DOC-06 ; REC-01/02 ; AUD-01 à 04 ; mutations métier et administration en négatif.')]
table([('Rôle','Scénarios à dérouler'),*paths],[50,429])
para('Parcours de bout en bout : AG-A crée et envoie ; AG-B réceptionne ; VA-B affecte à AG-B ; AG-B démarre et propose ; VA-B rejette avec motif ; AG-B corrige ; VA-B approuve ; AG-B transmet ; VA-A clôture ; AI-A archive. Contrôler documents, reçus, notifications et audit pendant ce même parcours.')
para('Chaîne nominale : DRAFT → SENT → RECEIVED → ASSIGNED → IN_PROGRESS → PENDING_VALIDATION → APPROVED → RESPONSE_SENT → CLOSED → ARCHIVED. Branche de rejet : PENDING_VALIDATION → REJECTED → PENDING_VALIDATION. IN_REVIEW est un état accepté vers ASSIGNED dans le service ; aucune route dédiée d’entrée dans cet état n’est exposée.')
for n,(title,rows) in enumerate(sections,4):
 story.append(PageBreak()); heading(f'{n}. {title}')
 for ident,role,title,pre,steps,expected in rows:
  card=[p(f'{ident} — {title}','Heading2'),p('Acteurs / canal : '+role),p('Préconditions : '+pre),p('Étapes : '+steps),p('Résultat attendu : '+expected),p('Résultat : NON EXÉCUTÉ   |   Preuve / anomalie : ____________________','SmallFR'),Spacer(1,9)]
  story.append(KeepTogether(card))
  md.extend([f'## {ident} — {title}\n',f'Acteurs : {role}\n',f'Préconditions : {pre}\n',f'Étapes : {steps}\n',f'Attendu : {expected}\n','Résultat : NON EXÉCUTÉ\n'])

story.append(PageBreak()); heading('Annexe A. Inventaire des routes et couverture')
para('Inventaire extrait du routeur du code de référence. Les routes de cette annexe sont couvertes par les familles indiquées ; chaque scénario doit aussi être exécuté avec les rôles interdits pertinents. Les payloads exacts et champs requis sont disponibles dans /docs de la version déployée.')
route_rows=[('Méthode et chemin relatif','Famille')]
for node in ast.parse((ROOT/'backend/app/api/routes.py').read_text(encoding='utf-8')).body:
 if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)):
  for dec in node.decorator_list:
   if isinstance(dec,ast.Call) and isinstance(dec.func,ast.Attribute) and isinstance(dec.func.value,ast.Name) and dec.func.value.id=='router':
    path=ast.literal_eval(dec.args[0]); family='CASE / READ'
    for prefix,f in [('/auth','AUTH'),('/institutions','ADM'),('/users','ADM'),('/audit','AUD'),('/security','AUD'),('/dashboard','READ'),('/documents','DOC'),('/notifications','NOT'),('/operations','NOT'),('/integrations','M2M'),('/external','M2M'),('/governance','READ'),('/settings','SET'),('/reference','REF')]:
     if path.startswith(prefix): family=f; break
    if '/attachments' in path: family='M2M' if path.startswith('/external') else 'DOC'
    if '/receipts' in path: family='REC'
    route_rows.append((dec.func.attr.upper()+' '+path,family))
route_rows.append(('GET /health (hors préfixe API)','OPS'))
table(route_rows,[390,89])
heading('Annexe B. Bornes à tester')
table([('Paramètre','Minimum','Maximum'),('access_token_minutes',5,1440),('refresh_token_days',1,90),('login_lock_threshold',3,20),('auto_archive_days',1,3650),('default_retention_days',1,36500),('due_soon_hours',1,720),('lifecycle_interval_seconds',60,86400)],[319,80,80])
para('Booléens : document_purge_enabled et due_alerts_enabled. La taille et les MIME de fichiers dépendent de la configuration effective ; le défaut du code est 25 Mio. Ne pas réduire une politique réelle de conservation pour accélérer un test.')
heading('Annexe C. Limites et critères de clôture')
para('Non livrés dans le code examiné : MFA opérationnel, webhooks et imports/exports métier génériques. Les modèles de messages ne constituent pas à eux seuls une messagerie autonome livrée. Pas de route de restauration documentaire ni de changement de mot de passe utilisateur dans le routeur examiné ; ne pas promettre ces parcours. CONSULTANT/OBSERVER restent à clarifier métier.')
para('Points à observer : droits API versus boutons UI ; pagination après filtrage de gouvernance ; visibilité des brouillons pour le destinataire ; compteurs globaux du tableau de bord ; lecture partagée des notifications institutionnelles ; conservation explicite lors de l’archivage manuel. Consigner les écarts aux exigences métier même si le comportement correspond au code.')
para('Historique de vérification de la reprise : build frontend réussi ; 11 tests unitaires backend réussis ; tests PostgreSQL d’intégration non exécutés faute de base de test configurée. Aucun scénario manuel de ce document n’est présenté comme exécuté. Les tests KMS existants utilisent un faux client et ne prouvent pas une intégration AWS réelle.')
para('Clôture proposée : tous les parcours nominaux des sept rôles exécutés ; aucun accès hors périmètre, contournement de rôle, session révoquée acceptée ou perte de document ; anomalies bloquantes corrigées et retestées ; fonctions non livrées acceptées explicitement hors périmètre. Joindre le CSV final et les preuves.')
para('Bilan : OK ____  KO ____  BLOQUÉ ____  NON APPLICABLE ____  NON EXÉCUTÉ ____')
para('Décision : ACCEPTÉ / ACCEPTÉ AVEC RÉSERVES / REFUSÉ     Responsable : ____________________')
heading('Sources de référence',2)
for source in ['backend/app/api/routes.py','backend/app/api/deps.py','backend/app/models/common.py','backend/app/services/workflow.py','backend/app/services/permissions.py','backend/app/services/documents.py','backend/app/services/lifecycle.py','backend/app/services/platform_settings.py','backend/app/services/reference_data.py','backend/tests/test_api_integration.py','frontend/src/App.tsx','README.md']:
 para(source)

def footer(canvas,doc):
 canvas.saveState(); canvas.setStrokeColor(colors.HexColor('#ccd7df')); canvas.line(36,36,A4[0]-36,36)
 canvas.setFont('Helvetica',8); canvas.setFillColor(colors.HexColor('#526579'))
 canvas.drawString(36,23,'InfoBridge | Cahier de recette | 05/09/2026'); canvas.drawRightString(A4[0]-36,23,f'Page {doc.page}'); canvas.restoreState()
file=OUT/'InfoBridge_Cahier_de_recette_tous_roles.pdf'
SimpleDocTemplate(str(file),pagesize=A4,rightMargin=36,leftMargin=36,topMargin=38,bottomMargin=48,title='InfoBridge — Cahier de recette de toutes les fonctionnalités et rôles',author='InfoBridge',pageCompression=1).build(story,onFirstPage=footer,onLaterPages=footer)
(OUT/'InfoBridge_Cahier_de_recette_tous_roles.md').write_text('\n'.join(md),encoding='utf-8')
with (OUT/'InfoBridge_Grille_execution_tests.csv').open('w',encoding='utf-8-sig',newline='') as f:
 writer=csv.writer(f,delimiter=';'); writer.writerow(['ID','Domaine','Acteurs','Test','Préconditions','Étapes','Résultat attendu','Statut','Résultat observé','Testeur','Date','Environnement/version','Preuve','Anomalie'])
 for domain,rows in sections:
  for ident,role,title,pre,steps,expected in rows: writer.writerow([ident,domain,role,title,pre,steps,expected,'NON EXÉCUTÉ','','','','','',''])
print(f'Generated {count} scenarios and {len(route_rows)-1} routes: {file.name} ({file.stat().st_size} bytes)')
