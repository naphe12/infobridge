# Espace de travail des dossiers

Les huit parcours sont accessibles depuis **Workflow → Espace de travail** et le bouton **Espace dossier** des listes de demandes.

## Parcours disponibles

1. **Complétude documentaire.** Un dossier possède un type de demande (`GENERAL` pour les dossiers existants). Un administrateur configure les usages obligatoires (`REQUEST`, `RESPONSE`, `EVIDENCE`) par institution, type et éventuellement classification. Les règles de l’expéditeur s’appliquent à la transmission. L’API refuse l’envoi si une pièce obligatoire manque ; une pièce archivée ou purgée ne satisfait pas la checklist. Le type ne se modifie qu’en brouillon.
2. **Relances et escalades.** Le scanner conserve les rappels quotidiens d’échéance. Après 24 heures de retard, il notifie les administrateurs de l’institution destinataire ; après 72 heures, les administrateurs système. Déduplication par dossier, niveau, destinataire et jour. Les alertes et le scanner automatique doivent être activés dans Gouvernance. Les escalades sont exécutées par le scanner de cycle de vie ; le bouton historique « Scanner échéances » ne déclenche que les rappels ordinaires.
3. **Discussion du dossier.** Les notes `INTERNAL` sont visibles uniquement dans l’institution de leur auteur, y compris pour les administrateurs système rattachés à une autre institution. Les messages `SHARED` sont visibles des acteurs autorisés du dossier. Les mentions portent sur des collègues actifs de sa propre institution et génèrent une notification. Les observateurs, consultants et auditeurs sont en lecture seule. Les messages partagés sont interdits en brouillon ; les discussions sont fermées à la clôture.
4. **Recherche documentaire.** Recherche locale dans les pièces autorisées, par lots de cinq, avec pagination explicite. Formats pris en charge : texte UTF-8, DOCX, PDF, JPEG et PNG. Les PDF mixtes sont lus page par page avec recours à l’OCR quand une page contient peu de texte. Les droits `cases.read` et `documents.download` sont vérifiés avant extraction. Les documents archivés logiquement ou purgés sont exclus.
5. **Synthèse sourcée.** Synthèse extractive locale : sélection de passages du document en fonction du sujet, références des pièces et trame de réponse à compléter. Ce n’est pas un modèle génératif externe. Aucun document n’est transmis à un fournisseur d’IA. La proposition doit être relue et soumise au circuit de validation ; sa génération ne modifie ni le statut ni la réponse du dossier. La chronologie est disponible dans le même écran.
6. **Circuits configurables.** Les règles de l’institution destinataire définissent jusqu’à cinq étapes par règle, réservées au rôle Validateur ou Admin institution. Les règles correspondantes se cumulent dans l’ordre de création. Le circuit est figé lors de chaque soumission de réponse : modifier une règle ne change pas une validation en cours. Une personne différente doit approuver chaque étape ; le rejet renvoie la réponse en correction. Les validations concurrentes sont sérialisées par verrouillage du dossier. Sans règle, la validation simple existante est conservée.
7. **Délégations temporaires.** Un administrateur autorisé du destinataire choisit un autre agent actif du destinataire, un début et une fin (90 jours maximum). Le remplaçant peut démarrer, proposer une réponse et transmettre une réponse déjà validée, dans la limite de ses propres droits. L’affectation d’origine reste intacte ; expiration, révocation ou changement de titulaire invalident la délégation. Aucun droit de validation n’est ajouté.
8. **Blocages.** Liste des dossiers accessibles en retard, reçus sans responsable, en attente de validation ou sans évolution depuis trois jours. L’âge est calculé à partir de la dernière action du workflow, ou de la création pour les anciens dossiers. Les dossiers clôturés et archivés sont exclus.

## Configuration de départ

Dans **Règles et circuits**, créer par exemple :

- Institution émettrice, type `INFORMATION_FINANCIERE`, pièces `REQUEST, EVIDENCE`.
- Institution destinataire, même type, étapes `VALIDATOR`, puis `INSTITUTION_ADMIN`.

Créer un dossier de ce type, téléverser les deux catégories de pièces via Documents sécurisés, puis transmettre. Prévoir deux personnes différentes disposant des rôles de validation. Les règles se désactivent depuis leur formulaire d’édition.

## Déploiement

- Déployer le backend avec la migration **0017_case_productivity** (`alembic upgrade head`, déjà exécuté par `start.sh`). Elle ajoute trois tables et trois colonnes aux dossiers, sans supprimer les données existantes.
- Reconstruire l’image backend : le Dockerfile installe Poppler et Tesseract avec les langues français/anglais. Aucun secret supplémentaire n’est requis.
- Déployer ensuite le frontend. Une compilation locale ne met pas à jour Railway.
- Vérifier l’activation du scanner dans Gouvernance pour les escalades.

Pour une exécution backend hors Docker, installer `pdfinfo`, `pdftotext`, `pdftoppm` et `tesseract` avec les langues `fra` et `eng` dans le PATH.

## Limites explicites de cette version

- Extraction à la demande, sans index persistant : cinq pièces par lot de recherche ou de synthèse, 20 Mo par pièce, dix premières pages de chaque PDF et 100 000 caractères par document. La synthèse indique le nombre de pièces traitées sur le total. La recherche affiche une couverture pour chaque pièce, même sans résultat.
- Les extraits de synthèse sont limités à 1 500 caractères par pièce. Ils ne remplacent pas la lecture intégrale ni la vérification des résultats OCR.
- Le texte déchiffré n’est pas enregistré en base. Les outils d’extraction utilisent un répertoire temporaire privé supprimé après traitement ; l’extraction ne crée pas de copie persistante des pièces.
- Les circuits portent sur la validation des réponses. Les délégations sont définies par dossier, sans transfert global de compte ni validation par procuration.
- Les types de demande sont des codes métier ; les pièces obligatoires utilisent les usages du référentiel documentaire existant.

## Vérification

- `python -m unittest discover -s tests -v` dans `backend`, avec `TEST_DATABASE_URL` pointant vers une base PostgreSQL de recette. Chaque classe crée un schéma isolé ; aucune base de production ne doit être utilisée.
- `npm run build` dans `frontend`.
- Test navigateur explicite : installer Playwright, construire le frontend avec son URL API locale par défaut, puis exécuter `python tests/browser_productivity.py` avec `TEST_DATABASE_URL`. `TEST_CHROMIUM_PATH` permet de choisir Chromium installé. Le script utilise les ports locaux 5179 et 8559 et ne contacte pas Railway.
- La migration a été exercée sur PostgreSQL 18 : installation jusqu’à 0017, retour à 0016 et réapplication.
- Les tests couvrent la complétude, la confidentialité et les mentions, les circuits figés, la séparation des validateurs, l’expiration/révocation des délégations, les droits documentaires et les escalades dédupliquées. Le test du PDF mixte simule les commandes d’extraction : un essai OCR sur un document réel reste nécessaire dans l’image backend déployée.

La suite existante a également révélé une erreur de sérialisation des secrets lors de la création/rotation des clients API ; elle est corrigée sans modifier leurs permissions.
