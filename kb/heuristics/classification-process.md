# Processus de classification en 10 étapes

> Source : Document de processus de classement de Karim (co-fondateur Veltar, expert réglementaire)
> Ce fichier décrit le workflow complet de classification export control pour un client en France.

---

## Scope : Client en France

Les réglementations applicables sont :
- La réglementation militaire française (liste ML)
- La réglementation européenne double usage (EU 2021/821)

Ces deux réglementations sont exclusives l'une de l'autre.

---

## Step 1 : Identifier la juridiction applicable

Identifier la juridiction applicable à partir du pays de création ou de modification du document.

Exemple : si le document est créé en France alors les réglementations applicables seront potentiellement la réglementation militaire française ou européenne double usage.

Fichiers KB à charger : aucun à cette étape (logique déterministe basée sur les métadonnées du document).

---

## Step 2 : Analyser le contenu — donnée technique ou non

Analyser le contenu pour déterminer si le document contient ou est une donnée technique au sens des réglementations militaire et double usage.

Définition opérationnelle : une donnée technique est une information peu importe sa forme (plan, formule mathématique, image, etc.) partielle ou totale qui permet le développement, la production ou l'usage d'un équipement, composant, matériau, outil, système, etc.

Fichiers KB à charger : kb/definitions/technical-data.md, kb/heuristics/document-types.md, kb/heuristics/technical-indicators.md

---

## Step 3 : Si NON technique — marquer EC_Not_Technical

Si le document n'est pas une donnée technique ou ne contient pas de donnée technique, alors la donnée est classée comme Not Technical.

Marquage : "EC_Not_Technical"

---

## Step 4 : Si technique — identifier l'item associé

Si le document est ou contient une donnée technique, il faut identifier l'équipement, le produit, le composant, la matière ou l'item auquel cette donnée se rattache.

Méthodes d'identification :
1. Contenu intrinsèque du document (mentions explicites, références, P/N)
2. Rattachement via PLM/SAP (la référence documentaire permet d'établir qu'il se rapporte à un tangible déjà classé dans la BOM)
3. Contexte de l'entreprise (historique de classement, type de produits fabriqués)
4. Approche par ATA pour l'aéronautique (identifier la section de l'avion sur laquelle le tangible est monté) [À AFFINER — approche spécialiste Airbus]

Fichiers KB à charger : kb/heuristics/technical-indicators.md

---

## Step 5 : Analyse militaire — l'item est-il militaire ?

Commencer par l'analyse militaire et vérifier si la donnée technique concerne le développement, la production ou l'usage d'un item conçu, développé ou modifié pour un usage militaire.

Logique : le classement militaire repose sur la notion de conception pour l'usage militaire ou de modification pour l'usage militaire. Voir kb/definitions/military-use.md pour les critères détaillés.

Si l'item est militaire, la donnée technique associée sera classée :
- ML22.a : "technologie" "nécessaire" au développement, production, exploitation, installation, entretien, réparation, révision ou rénovation d'articles visés dans la liste ML et/ou spécialement conçu pour un usage militaire.
- ML22.b.1 : technologie nécessaire à la conception/exploitation d'installations de production.
- ML22.b.2 : technologie nécessaire au développement/production d'armes à feu portatives.
- ML22.b.5 : technologie nécessaire à l'incorporation de biocatalyseurs dans des substances militaires.

Marquage si classé militaire : {Code Pays}_EC_{Export Control code}
Exemple : "FR_EC_ML22.a"

Fichiers KB à charger : kb/definitions/military-use.md, kb/frml/overview.md, et le fichier ML spécifique si l'item correspond à une catégorie identifiable (ex: kb/frml/ML10.md pour un aéronef).

---

## Step 6 : Si NON militaire — basculer vers le dual-use

Si la branche militaire ne s'applique pas (l'item n'est pas conçu/modifié pour usage militaire et ne figure pas dans la liste ML), basculer vers l'analyse des biens à double usage.

---

## Step 7 : Classifier l'item dans la liste dual-use

Classifier d'abord l'item concerné dans la liste de contrôle des biens à double usage (Annexe I du règlement EU 2021/821).

Méthode de recherche :
1. Recherche par mots-clés dans la liste des biens à double usage (maximiser avec plusieurs mots-clés)
2. Recherche par catégorie et sous-catégorie pressentie

Les 10 catégories :
- 0: Matières, installations et équipements nucléaires
- 1: Matières spéciales et équipements apparentés
- 2: Traitement des matériaux
- 3: Électronique
- 4: Calculateurs
- 5: Télécommunications et sécurité de l'information
- 6: Capteurs et lasers
- 7: Navigation et aéro-électronique
- 8: Marine
- 9: Aérospatiale et propulsion

Nature du bien (sous-catégorie) :
- A : Systèmes, équipements et composants
- B : Matériel d'essai, d'inspection et de production
- C : Matériaux
- D : Logiciels
- E : Technologie

Exemples de recherche par mots-clés :
- Machine-outil CNC : "Machines-outils" → 2B001, 2B002, 2B003, 2B201 ; "Fraisage" → 2B001 ; "Axes" → 2B001, 2B002, 2B201
- Drone : "Drone" → aucun résultat ; "Véhicules aériens" → 9A012, 9A112 ; "UAV" → 9A012, 9A112
- Acier maraging : "Aciers" → 1C116, 1C216 ; "Maraging" → 1C116, 1C216

Fichiers KB à charger : kb/eu-dual-use/overview.md pour la structure, puis le fichier de catégorie correspondant (ex: kb/eu-dual-use/cat2.md pour les machines-outils).

---

## Step 8 : Vérifier si la donnée technique est contrôlée (partie E)

Une fois l'ECCN du composant, équipement ou matériau identifié, vérifier si la donnée technique répond aux caractéristiques listées dans la partie E (Technology) de la catégorie, c'est-à-dire si elle constitue une technologie contrôlée de développement, production ou usage relative à l'item contrôlé.

Si la donnée est contrôlée : marquer avec "EU_EC_{ECCN}"
Exemple : EU_EC_7E101

Fichiers KB à charger : la section E du fichier de catégorie correspondant.

---

## Step 9 : Si la donnée n'est pas contrôlée

Si la donnée technique ne répond pas aux critères de la partie E, la marquer :
"EU_EC_Technical_Not_Controlled"

---

## Step 10 : Décision finale et remontée pour revue humaine

Produire une décision finale de classement avec :
- Justification de la détermination technique/non technique
- Justification de la détermination militaire/non militaire
- Si non militaire : justification de la détermination dual-use ou non
- Pour chaque justification : un niveau de confiance
- Analyse synthétique expliquant le niveau de confiance
- Quand le niveau de confiance est faible ou sur un cas complexe : les éléments permettant à l'humain de vérifier/valider

Le marquage consiste à indiquer le classement dans les métadonnées du document ainsi que physiquement sur le document (cartouche d'un plan 2D, note de bas de page, etc.).

---

## Cas spéciaux

### Deux situations principales pour le classement

1. Le document donne suffisamment d'informations pour en connaître le classement : il donne suffisamment d'informations pour classer le tangible associé (savoir si, en fonction de ses caractéristiques, il est classé militaire ou listé sur la liste des biens à double usage) et ainsi permettre de savoir si c'est une donnée militaire ou double usage.

2. Le document ne le permet pas : il faut aller chercher des informations auprès de l'ingénieur concepteur, du fournisseur (cas build-to-print), dans le PLM, SAP, le contrat, etc.

### Classification par rattachement à un tangible classé

Un document technique peut être classé non seulement sur la base de son contenu intrinsèque, mais aussi sur la base de son rattachement système. Si sa référence documentaire permet d'établir, dans le PLM/SAP, qu'il se rapporte à un tangible déjà classé (ex: ML10A dans la BOM), alors ce document doit être traité comme une donnée technique contrôlée relative à cet item.

### Classification par historique et comparatif

Dans l'analyse du contexte, on analyse aussi l'historique de classement de l'entreprise pour comprendre le type de produit qu'elle fabrique. On regarde les documents précédemment classés et leurs caractéristiques pour faire un comparatif.

Exemple : une entreprise qui crée des centrales inertielles ou des actionneurs de vol qu'elle classe 7A101, a sûrement déjà classé des données techniques 7E101. Si j'ai une donnée dont je connais le classement, elle peut servir de base pour classer d'autres documents grâce à l'IA et au ML.

### Exemples concrets

1. Un plan d'un moteur sur lequel on voit la mention A400M → classer ML22.a (ou si on identifie la référence moteur et on sait que c'est un moteur d'avion militaire A400M).

2. Pour la classification en masse : regarder la nature du document. Par exemple, toutes les SOI, AIPI (documents techniques du manufacturing engineering) sont considérées comme des données techniques.

3. Approche par ATA (spécialiste aéronautique, contexte Airbus) : identifier le tangible associé et voir sur quelle section de l'avion il est monté. Si le tangible se monte sur le train d'atterrissage, on sait qu'il n'est généralement pas contrôlé et donc que la donnée technique associée ne le sera pas. [À AFFINER — nécessite des règles ATA spécifiques par programme]

---

## Gestion des classements en masse

### Rational global

Dans le cadre de la classification de plusieurs documents avec le même classement, expliquer pourquoi l'ensemble des documents a été classé ainsi (approche similaire à celle utilisée pour les violations groupées).

L'idée est d'éviter à l'humain d'aller valider le classement de plusieurs milliers de documents un par un, en proposant un rational global en plus du rational individuel.

### Groupement par complexité et confiance

Lister les cas par complexité et niveau de confiance. Si pas sûr, ne pas raconter n'importe quoi mais proposer des classements avec justification pour aider à la décision.

---

## UI du raisonnement (pour chaque classement proposé)

L'interface doit afficher :
1. Ce qui a permis à l'agent de déterminer que c'est une donnée technique ou non
2. Ce qui a permis à l'agent de déterminer que le composant/équipement/matériau/système/logiciel objet de la donnée est militaire ou non
3. Si non militaire : ce qui a permis à l'agent de déterminer que l'objet est listé sur la liste de contrôle des biens à double usage ou non
4. Pour chaque justification : un niveau de confiance, puis une analyse synthétique qui explique le niveau de confiance
5. Quand le niveau de confiance est faible ou sur un cas complexe : les éléments qui permettent à l'humain de vérifier/valider

---

## Scope futur : Client aux US (ITAR/EAR)

[Ce scope n'est pas dans le MVP mais les définitions et le processus sont documentés ici pour référence future. Source : Karim.]

### Principe clé : Order of Review (ITAR prioritaire sur EAR)

L'ITAR Order of Review priorise l'ITAR sur l'EAR. Si un item est listé sur l'USML, il relève de l'ITAR. Sinon, il peut relever de l'EAR. Cette logique est analogue à la priorité ML/Dual-Use en France.

### ITAR Technical data definition (22 CFR 120.33)

(a) Technical data means:

(1) Information (other than software defined as the system functional design, logic flow, algorithms, application programs, operating systems, and support software for design, implementation, test, operation, diagnosis, and repair) which is required for the design, development, production, manufacture, assembly, operation, repair, testing, maintenance, or modification of defense articles. This includes information in the form of blueprints, drawings, photographs, plans, instructions, or documentation;

(2) Classified information relating to defense articles and defense services on the U.S. Munitions List and 600-series items controlled by the Commerce Control List;

(3) Information covered by an invention secrecy order; or

(4) Software directly related to defense articles.

(b) Technical data does not include information concerning general scientific, mathematical, or engineering principles commonly taught in schools, colleges, and universities, or information in the public domain as defined in § 120.34 or telemetry data as defined in note 3 to Category XV(f) of § 121.1 of this subchapter. It also does not include basic marketing information on function or purpose or general system descriptions of defense articles.

### EAR Technology/Technical data definition

Information necessary for the "development," "production," "use," operation, installation, maintenance, repair, overhaul, or refurbishing (or other terms specified in ECCNs on the CCL that control "technology") of an item.

"Technology" may be in any tangible or intangible form, such as written or oral communications, blueprints, drawings, photographs, plans, diagrams, models, formulae, tables, engineering designs and specifications, computer-aided design files, manuals or documentation, electronic media or information revealed through visual inspection.

### EAR "Use" definition

Operation, installation (including on-site installation), maintenance (checking), repair, overhaul and refurbishing. (critères cumulatifs)

### EAR "Required" definition (avec exemple CCL)

As applied to "technology" or "software," refers to only that portion of "technology" or "software" which is peculiarly responsible for achieving or exceeding the controlled performance levels, characteristics or functions. Such "required" "technology" or "software" may be shared by different products.

Exemple : Supposons que le produit "X" est contrôlé sur la CCL s'il fonctionne à 400 MHz ou plus, et n'est pas contrôlé en dessous de 400 MHz. Si les technologies de production "A", "B" et "C" permettent une production à maximum 399 MHz, alors "A", "B" et "C" ne sont pas "required" pour produire le produit contrôlé "X". Si les technologies "A", "B", "C", "D" et "E" sont utilisées ensemble et permettent de produire un produit "X" fonctionnant à 400 MHz ou plus, alors dans cet exemple, les technologies "D" et "E" sont peculiarly responsible pour fabriquer le produit contrôlé et sont donc de la "required" technology au titre de la General Technology Note.

### "Specially designed" definition (EAR § 772.1)

A commodity or software is specially designed if it:

(1) As a result of development, has properties peculiarly responsible for achieving or exceeding the controlled performance levels, characteristics, or functions described in the relevant U.S. Munitions List (USML) paragraph in § 121.1 of this subchapter; or

(2) Is specifically identified in the relevant USML paragraph.

Note : Cette définition est essentielle pour distinguer les articles ITAR des articles EAR. Si un item est "specially designed" pour une application militaire au sens de l'USML, il relève de l'ITAR.

### US Overhaul Process — 5 Steps

#### Step 1 — Identify the Item or Service

Description and Functionality : Start by thoroughly describing the item or service, including its functionality, components, and intended use. This information is crucial for accurate classification.

#### Step 2 — Determine the Jurisdiction

Is the Item Specially Designed? : Evaluate whether the item is "specially designed" for a military application or if it has been modified for military use. This determination is critical for establishing ITAR jurisdiction.

Check the USML : Review the United States Munitions List (USML) to see if the item is specifically enumerated. The USML categorizes defense articles into 21 categories, ranging from firearms to spacecraft systems.

#### Step 3 — Classify the Item Under the USML

USML Categories : If the item is determined to be under ITAR jurisdiction, classify it according to the appropriate category on the USML. Each category has detailed descriptions and subcategories that aid in accurate classification.

Technical Data Classification : If the item is technical data or a defense service, classify it under the relevant USML category. Technical data includes blueprints, drawings, and other information related to defense articles.

#### Step 4 — Review the Commerce Control List (CCL)

Dual-Use Items : If the item is not listed on the USML, check the Commerce Control List (CCL) under the Export Administration Regulations (EAR) to determine if it is a dual-use item. Dual-use items have both civilian and military applications and are controlled by the Bureau of Industry and Security (BIS).

#### Step 5 — Document the Analysis

Comprehensive Documentation : Maintain detailed records of the analysis process, including the rationale for jurisdiction and classification decisions. This documentation is essential for compliance audits and regulatory reviews.

### Parallèle FR vs US

| Étape | France | US |
|-------|--------|-----|
| Juridiction | Pays de création → FR ML + EU DU | Order of Review → ITAR puis EAR |
| Donnée technique | Définition ML22/GTN | ITAR 22 CFR 120.33 / EAR "technology" |
| Militaire | "Spécialement conçu pour usage militaire" | "Specially designed" (USML) |
| Liste militaire | Liste ML (22 catégories) | USML (21 catégories) |
| Dual-use | Annexe I EU 2021/821 (10 catégories) | CCL (10 catégories) |
| Exclusions | Domaine public, recherche fondamentale | Public domain (§ 120.34), general principles |
