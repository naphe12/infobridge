# InfoBridge — Manuel d’utilisation

Version 1.0 • 5 septembre 2026

Guide des utilisateurs, administrateurs et auditeurs. Décrit le code disponible à cette date ; les corrections doivent être déployées pour être visibles sur le site. Aucun identifiant secret n’est inclus.

## 1. Découvrir InfoBridge

InfoBridge permet aux institutions d’échanger des demandes d’information, de traiter les réponses, de joindre des documents et de suivre les accusés de réception. Chaque dossier possède une référence, un émetteur, un destinataire et un état de traitement.

Les trois entrées principales sont Vue d’ensemble, Administration et Documents. Les raccourcis regroupent les fonctions : Nouvelle demande, Dossiers, Documents sécurisés, Transmission, Réception, Traitement, Validation, Conservation, Journalisation, Alertes et Interopérabilité.

Choisissez un raccourci pour afficher le formulaire ou la liste correspondante. Les fonctions accessibles dépendent de votre rôle, de votre institution, de l’état du dossier et des règles d’accès. Un bouton visible ne garantit pas que l’opération soit autorisée : le serveur vérifie aussi ces conditions.

Ce guide explique les actions disponibles dans les écrans. Les fonctions uniquement disponibles par API sont identifiées au chapitre 11 ; elles ne sont pas présentées comme des boutons existants.

Sommaire : 1. Découverte ; 2. Connexion ; 3. Rôles ; 4. Recherche ; 5. Demande et réception ; 6. Traitement et validation ; 7. Documents et reçus ; 8. Alertes ; 9. Administration ; 10. Audit et interopérabilité ; 11. Limites ; 12. Assistance.

## 2. Se connecter et gérer sa session

### Ouvrir une session

1. Ouvrez l’adresse du site communiquée par votre administrateur.
2. Saisissez votre adresse e-mail institutionnelle et votre mot de passe personnel.
3. Utilisez l’icône d’affichage du mot de passe si vous souhaitez vérifier votre saisie.
4. Cliquez sur Se connecter, puis vérifiez votre identité, votre rôle et votre institution dans Accès.

Le compte et l’institution doivent être actifs. Le renouvellement de session est géré par l’application tant que la session reste valable. Si elle expire, reconnectez-vous.

### Fermer une session

Utilisez la commande de déconnexion avant de quitter un poste partagé. La déconnexion invalide la session utilisée. Pour fermer toutes les sessions d’un compte, un administrateur doit utiliser Révoquer sessions.

### En cas de refus

Identifiants incorrects : vérifiez l’adresse, la casse du mot de passe et la saisie automatique du navigateur. Ne multipliez pas les tentatives : le compte se verrouille après le seuil configuré.

Compte verrouillé ou désactivé : demandez à un administrateur de vérifier le statut. Institution inactive : demandez à l’administrateur système de vérifier l’institution. Réactiver un compte ne change pas son mot de passe.

Le MFA n’est pas opérationnel dans cette version. Il n’existe pas de procédure autonome de changement ou de récupération du mot de passe dans les routes examinées ; adressez-vous à l’administrateur.

## 3. Comprendre les sept rôles

### Administrateur système — SYSTEM_ADMIN

Gère toutes les institutions, les utilisateurs, les paramètres, les référentiels, les journaux et les clients API. Peut intervenir sur les dossiers des institutions. Pour accuser réception, il doit lui aussi appartenir à l’institution destinataire.

### Administrateur institution — INSTITUTION_ADMIN

Gère les utilisateurs et les clients API de sa propre institution. Peut réaliser les opérations métier correspondant à son institution. Consulte les journaux de son périmètre et les paramètres globaux ; leur modification est réservée à l’administrateur système. Ne peut pas gérer un administrateur système ni créer ou suspendre une institution.

### Agent — AGENT

Crée des demandes et transmet celles dont il est le créateur. Côté destinataire, réceptionne les demandes et traite celles qui lui sont affectées : démarrage, rédaction et envoi après approbation. Peut ajouter des documents, mais ne valide pas les réponses.

### Validateur — VALIDATOR

Affecte les demandes de son institution destinataire et approuve ou rejette les réponses. Côté émetteur, clôture les dossiers après réception de la réponse. Peut déclencher les relances. Ne crée pas de demande et ne téléverse pas de document par défaut.

### Consultant — CONSULTANT et observateur — OBSERVER

Consultent les dossiers et téléchargent les pièces autorisées. Peuvent accuser réception et marquer lu lorsqu’ils appartiennent à l’institution destinataire. Ne réalisent pas les transitions du dossier. Ces deux rôles ont actuellement les mêmes droits de base ; leur distinction métier reste à définir.

### Auditeur — AUDITOR

Consulte les dossiers autorisés, les journaux d’audit et les événements de sécurité de son institution. Exporte l’audit en CSV ou PDF. N’administre pas les comptes et ne modifie pas le workflow. Peut enregistrer ses reçus comme membre du destinataire.

Les autorisations de lecture et de téléchargement peuvent être restreintes par la classification ou une règle de gouvernance. Un dossier d’une institution étrangère n’est pas automatiquement accessible.

## 4. Retrouver et comprendre un dossier

1. Ouvrez Dossiers, Recherche ou l’entrée Documents.
2. Saisissez une référence ou un objet dans la recherche.
3. Utilisez les filtres présents dans la vue, puis retirez-les si aucun résultat n’apparaît.
4. Vérifiez la référence, les institutions émettrice et destinataire, le statut, la classification et les pièces indiquées sur la ligne.

Les classifications sont PUBLIC, INTERNE, CONFIDENTIEL et SECRET. Les priorités vont de LOW à CRITICAL ; leurs libellés peuvent être personnalisés par l’administrateur système. Choisissez la valeur correspondant à la sensibilité et à l’urgence réelles du dossier.

Vue d’ensemble présente des indicateurs et des alertes. Pour traiter une demande précise, partez de sa référence et de son statut dans la liste plutôt que d’un compteur seul.

La chaîne de traitement est : Brouillon → Transmis → Réceptionné → Affecté → En cours → En attente de validation → Approuvé → Réponse transmise → Clôturé → Archivé. Une réponse rejetée doit être corrigée puis soumise à nouveau à validation.

Aucun résultat peut signifier : filtre trop restrictif, dossier hors périmètre ou règle de classification. En cas de message d’erreur de chargement, ne concluez pas que la liste est vide.

## 5. Créer, transmettre et réceptionner une demande

### Créer — agent ou administrateur

1. Ouvrez Nouvelle demande.
2. Saisissez une référence unique, par exemple REC-2026-001 pour une recette, et un objet explicite.
3. Sélectionnez les institutions, la priorité, la classification et l’échéance si nécessaire.
4. Décrivez les informations demandées et le contexte.
5. Cliquez sur Créer la demande. Vérifiez qu’elle apparaît en brouillon.

Un utilisateur non système crée la demande au nom de sa propre institution émettrice. Les institutions choisies doivent être actives.

### Transmettre — côté émetteur

Ajoutez les pièces nécessaires via Documents sécurisés, retrouvez le brouillon et cliquez sur Transmettre. Le statut passe à SENT ; les responsables destinataires sont notifiés. Un agent ne transmet que les demandes qu’il a créées.

### Réceptionner — côté destinataire

Ouvrez la demande transmise et cliquez sur Réceptionner avec un compte autorisé de l’institution destinataire. Elle passe à RECEIVED. Un reçu est enregistré si l’acteur appartient à cette institution.

Réceptionner modifie l’état métier du dossier. Accuser réception enregistre votre reçu personnel ; cette action ne remplace pas la transition de réception du dossier.

### Affecter — administrateur ou validateur destinataire

Dans la liste Affecter du dossier réceptionné, choisissez un utilisateur actif de votre institution destinataire. Le dossier passe à ASSIGNED et l’utilisateur affecté reçoit une notification. Si la liste n’est pas disponible, faites vérifier votre rôle et les comptes actifs pouvant être affectés.

## 6. Traiter, valider et clôturer

### Agent affecté

1. Retrouvez le dossier qui vous est affecté et cliquez sur Démarrer.
2. Examinez la demande et téléchargez les pièces nécessaires.
3. Cliquez sur Répondre ; saisissez la réponse et le commentaire éventuel, puis confirmez le formulaire.
4. Le dossier passe en attente de validation. Attendez la décision avant de transmettre la réponse.

Un autre agent ne peut pas démarrer ou envoyer la réponse du dossier qui vous est affecté.

### Validateur de l’institution destinataire

1. Ouvrez un dossier en attente de validation et examinez la réponse.
2. Cliquez sur Valider pour approuver, ou Rejeter pour demander une correction.
3. En cas de rejet, renseignez un motif ; il est obligatoire.

Après rejet, l’agent utilise Répondre pour corriger et soumettre à nouveau. Après approbation, l’agent affecté ou l’administrateur destinataire clique sur Envoyer réponse.

### Clôturer et archiver — côté émetteur

Après transmission de la réponse, le validateur ou l’administrateur de l’institution émettrice clique sur Clôturer. Un administrateur émetteur peut ensuite cliquer sur Archiver. L’administrateur système peut également intervenir.

L’archivage marque la fin du workflow. Il ne signifie pas une suppression immédiate des fichiers. La conservation et la purge sont gérées selon les paramètres et dates applicables ; contactez l’administrateur pour une date de conservation particulière.

Exemple complet : agent A crée et transmet ; agent B réceptionne ; validateur B affecte ; agent B démarre et répond ; validateur B approuve ; agent B envoie la réponse ; validateur A clôture ; administrateur A archive.

## 7. Utiliser les documents et les reçus

### Ajouter un fichier — agent ou administrateur

1. Ouvrez Documents sécurisés.
2. Sélectionnez le dossier dans Ajouter une pièce à un dossier.
3. Choisissez l’usage de la pièce, par exemple demande ou réponse.
4. Sélectionnez le fichier et cliquez sur Téléverser.
5. Vérifiez le nom du fichier dans la ligne du dossier.

Le serveur contrôle le type déclaré, le contenu et la taille. Le plafond par défaut est de 25 Mio, mais la configuration effective peut différer. Le fichier est chiffré au stockage ; les opérations de dépôt et de téléchargement sont tracées.

### Télécharger

Sur la ligne du dossier, utilisez l’icône de téléchargement. Dans cette interface, cette commande télécharge la première pièce de la liste. Les noms et numéros de version des pièces apparaissent sur la ligne ; la gestion détaillée de toutes les versions passe par l’API dans la version examinée.

Si aucune pièce n’est présente, l’application vous invite à en ajouter. Si le téléchargement est refusé, faites vérifier les droits et la classification. Une pièce archivée n’est plus téléchargeable par son accès normal.

### Accuser réception et marquer lu

Dans un dossier qui vous est destiné et qui n’est plus en brouillon, cliquez sur Accuser réception. Cliquez ensuite sur Marquer lu après consultation. Votre nom et la date apparaissent dans le résumé des reçus.

Ces actions sont disponibles pour tous les rôles de l’institution destinataire, y compris consultant, observateur et auditeur. Les appels répétés ne doivent pas créer plusieurs reçus pour le même acteur.

## 8. Suivre les notifications et échéances

1. Ouvrez Alertes.
2. Consultez les notifications de votre compte et de votre institution.
3. Utilisez le filtre de niveau si nécessaire.
4. Marquez une notification comme lue, ou utilisez la commande de lecture de toutes les notifications.

Une notification peut annoncer une transmission, une affectation, une réponse à valider, une réponse envoyée ou une échéance proche/dépassée. Pour agir, retrouvez le dossier par sa référence.

Les notifications institutionnelles ont un état de lecture partagé dans le modèle actuel ; elles ne constituent pas un accusé personnel par destinataire. Utilisez les reçus du dossier pour le suivi nominatif.

Les administrateurs et validateurs peuvent lancer Scanner échéances. Les relances sont aussi produites automatiquement lorsque le planificateur est activé. Il effectue un scan au démarrage puis selon l’intervalle configuré ; la répétition d’un scan ne doit pas multiplier les mêmes alertes journalières.

Si les relances semblent absentes, demandez à l’administrateur de vérifier l’état du planificateur, son dernier scan, l’activation des relances et les dates d’échéance. Ne modifiez pas une échéance uniquement pour supprimer une alerte.

## 9. Administrer la plateforme

### Gérer les utilisateurs

1. Dans Administration, ouvrez Utilisateurs ou Inviter utilisateur pour la création.
2. Pour créer un compte, renseignez nom, e-mail, mot de passe initial d’au moins 12 caractères, institution et rôle ; confirmez.
3. Pour modifier un compte, cliquez sur Modifier et enregistrez les changements proposés.
4. Utilisez Désactiver pour empêcher son accès ou Réactiver pour rétablir un compte inactif/verrouillé.
5. Utilisez Révoquer sessions pour fermer toutes ses sessions sans désactiver le compte.

Une désactivation révoque les sessions. Une réactivation ne restaure pas les anciennes sessions et ne réinitialise pas le mot de passe. Un changement de rôle est contrôlé à partir du profil courant en base. L’administrateur institution reste limité aux utilisateurs de son institution et ne peut pas gérer un administrateur système.

### Gérer les institutions — administrateur système

Ouvrez Institutions ou Nouvelle institution. Renseignez un nom, un code unique et un type. Utilisez Modifier pour corriger les informations, puis les actions de statut pour suspendre ou réactiver une institution. La suspension invalide les sessions de ses membres.

L’application protège le maintien d’un administrateur système actif. N’utilisez pas votre dernier compte d’administration pour essayer une désactivation.

### Paramètres et référentiels

Dans Gouvernance, consultez les paramètres de sécurité, de conservation et d’automatisation. L’administrateur système saisit la valeur puis clique sur Enregistrer ; l’administrateur institution les consulte en lecture seule. Les modifications sont persistées et auditées.

Dans Référentiels, l’administrateur système peut modifier libellé, description, ordre et disponibilité des valeurs. Les codes structurants restent stables ; les valeurs obligatoires sont protégées. Une valeur désactivée reste visible sur les anciens enregistrements mais n’est plus proposée/acceptée pour une nouvelle utilisation.

Les règles détaillées de permission et de classification existent par API ; l’écran Gouvernance examiné affiche les paramètres, pas un éditeur complet de toutes ces règles.

## 10. Consulter l’audit et gérer l’interopérabilité

### Journalisation — administrateurs et auditeurs

1. Ouvrez Journalisation.
2. Dans Journal d’audit, choisissez une action ou Toutes les actions.
3. Consultez la date, le type d’entité et le contexte des événements.
4. Cliquez sur CSV ou PDF pour exporter l’audit avec le filtre d’action sélectionné.
5. Dans Événements de sécurité, filtrez la sévérité : faible, moyenne, élevée ou critique.

L’administrateur système dispose d’une vue globale. L’administrateur institution et l’auditeur voient les journaux de leur institution. L’export lui-même est audité. Les boutons CSV/PDF concernent le journal d’audit, pas un export général de toutes les données.

### Interopérabilité — administrateurs

1. Ouvrez Interopérabilité et créez un client API avec un nom explicite.
2. Choisissez l’institution et les scopes nécessaires : cases:read pour les dossiers ; documents:read pour les pièces.
3. Enregistrez le secret affiché dans le coffre prévu pour l’intégration : il n’est montré qu’à la création ou à la rotation.
4. Transmettez les paramètres au responsable du système partenaire par le canal approuvé.
5. Utilisez les actions de modification, suspension ou rotation du secret selon le besoin.

L’administrateur institution gère uniquement les clients de son institution ; seul l’administrateur système peut créer un client global. Une réduction de scopes, une suspension ou une rotation invalide les anciens jetons concernés.

L’échange de la clé et du secret contre un jeton se fait par API, puis le partenaire appelle les routes externes autorisées. Ce jeton machine ne remplace pas une connexion utilisateur dans l’interface.

## 11. Fonctions techniques et limites de cette version

Versioning et archivage des pièces : disponibles par API. Le formulaire de dépôt actuel ne propose pas un remplacement de version et la liste ne fournit pas un gestionnaire complet des versions. Demandez l’intervention du responsable technique pour ces opérations.

Purge physique : réservée à l’administrateur système par API, avec aperçu et confirmation explicite. Elle exige un dossier archivé dont la conservation est expirée. La purge peut aussi être activée dans les cycles automatiques ; ce réglage doit respecter la politique de conservation retenue.

Stockage S3/MinIO et chiffrement externe AWS KMS : configurés par l’exploitation. L’utilisateur dépose et télécharge depuis l’application ; il n’a pas à manipuler les clés. Les anciens documents locaux nécessitent le maintien de leur volume de stockage.

Historique détaillé du workflow et filtres avancés : routes API disponibles. Certains raccourcis de l’interface peuvent afficher un module prévu ou À brancher ; cela ne constitue pas un écran fonctionnel complet.

Non opérationnels ou non exposés comme parcours complet dans le code examiné : MFA, webhooks, imports/exports métier génériques, messagerie autonome, restauration de pièce et récupération autonome de mot de passe. Le raccourci Sauvegarde ne prouve pas l’existence d’une procédure de restauration utilisable depuis l’interface.

Pour vérifier une fonction et tous ses cas de refus, utilisez le Manuel de test et sa grille CSV. Ces documents décrivent une campagne à exécuter ; ils ne certifient pas la réussite des tests en production.

## 12. Résoudre les difficultés courantes

### Failed to fetch / API injoignable

Le navigateur n’a pas obtenu une réponse exploitable. Vérifiez votre connexion, actualisez puis utilisez Réessayer si disponible. Si le problème persiste sur toutes les pages, signalez-le à l’exploitation : disponibilité API, adresse configurée, autorisation du site et erreurs serveur doivent être vérifiées. Un simple changement de mot de passe ne corrige pas cette erreur.

### Accès refusé

Vérifiez le rôle, l’institution, l’affectation et la classification. Par exemple, seul l’agent affecté démarre un dossier ; seul le côté émetteur clôture ; seul le destinataire accuse réception. Demandez une vérification des droits plutôt que de répéter l’action.

### Transition impossible

Actualisez le dossier et vérifiez son statut. Les étapes ne peuvent pas être sautées : une réponse doit être approuvée avant envoi et un dossier clôturé avant archivage. Une action réalisée par un collègue peut avoir changé l’état entre-temps.

### Erreur de fichier ou liste vide

Pour un fichier rejeté, contrôlez taille et format réel. Pour une liste vide, retirez les filtres et vérifiez votre périmètre. Une erreur 500 nécessite l’examen du serveur par l’exploitation ; transmettez l’heure, l’action et la référence du dossier.

### Signaler une anomalie

Indiquez l’adresse de la page, la date et l’heure, votre rôle et institution, les étapes effectuées, le message exact et une référence de dossier autorisée. Joignez une capture expurgée si utile. Ne transmettez jamais le mot de passe, un jeton, un secret client, une clé de chiffrement ou le contenu du fichier .env.

Avant de relancer une création ou une transmission après erreur, actualisez et vérifiez si l’opération a déjà été enregistrée afin d’éviter un doublon.
