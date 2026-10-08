# Phases du cycle de vie industriel — Référence export control

> Ce fichier décrit les 24 phases du cycle de vie d'un produit industriel, les types de données techniques générées à chaque phase, leur niveau de sensibilité export control, et les points de vigilance pour l'analyse.

---

## DÉVELOPPEMENT

### Phase 1 — Recherche amont (Research)
- **Description** : Études exploratoires, maturation technologique (TRL 1-3), travaux sur phénomènes physiques
- **Types de données** : Publications internes, white papers, rapports d'études exploratoires, brevets, notes de recherche appliquée, résultats de tests de maturation
- **Exemples de documents** : Technology Readiness Assessment Report, Internal Research Papers, Patent Applications, Lab Notebooks, TRL Assessment Reports
- **Sensibilité** : Variable (fondamental = exclu, appliqué = contrôlé)
- **Risque deemed export** : Moyen
- **Point de vigilance** : Distinguer recherche fondamentale (exclue par GTN et ML22 Note 2) vs. appliquée (contrôlée). La frontière bascule dès qu'un résultat est orienté vers un article classifiable.

### Phase 2 — Études de faisabilité (Feasibility Studies)
- **Description** : Études de concepts, trade studies, analyses de compromis, architecture système préliminaire
- **Types de données** : Rapports de faisabilité, trade study reports, analyses de compromis, architecture système préliminaire, évaluations de risques techniques
- **Exemples de documents** : Feasibility Study Report, CONOPS, Trade Study Matrix, Risk Assessment Report
- **Sensibilité** : Moyen
- **Risque deemed export** : Moyen
- **Point de vigilance** : Un trade study révélant les performances-cibles peut permettre la classification même si le design n'est pas finalisé. Détecter les seuils techniques mentionnés.

### Phase 3 — Définition des exigences (Requirements Definition)
- **Description** : Exigences client, système, sous-système, interface, environnementales, sûreté, logiciel, hardware
- **Types de données** : CRD, SRD, IRD/ICD, exigences environnementales (DO-160, MIL-STD-810), exigences sûreté (ARP4754A/4761), SRS (DO-178C), HRS (DO-254)
- **Exemples de documents** : Customer Requirements Document, System Requirements Document, ICD, SRS, HRS, Safety Requirements Document
- **Sensibilité** : Élevé
- **Risque deemed export** : Élevé
- **Point de vigilance** : Les exigences de performance (précision, fréquence, portée, résolution) permettent directement la classification. Un SRD spécifiant une dérive gyro < 0.01°/h classe l'article en Cat. 7.

### Phase 4 — Conception préliminaire (Preliminary Design)
- **Description** : Architecture système, décomposition fonctionnelle, schémas blocs, sélection technologies clés, PDR
- **Types de données** : Architecture système (SBS/PBS/WBS), schémas fonctionnels, trade studies détaillés, sélection composants, analyses préliminaires (mass/power/link budget), livrables PDR
- **Exemples de documents** : System Architecture Document, Functional Block Diagram, PDR package, Component Selection Report
- **Sensibilité** : Élevé
- **Risque deemed export** : Élevé
- **Point de vigilance** : Le choix d'un composant contrôlé (FPGA >X gates, gyro <Y drift) déclenche la classification de l'ensemble. Croiser composants sélectionnés vs. listes de contrôle.

### Phase 5 — Conception détaillée (Detailed Design)
- **Description** : Modèles CAO 3D, plans 2D, BOM, schémas électriques, design logiciel, design FPGA/ASIC, CDR
- **Types de données** : Modèles CAO, plans GD&T, nomenclatures (BOM), schémas électriques, spécs matériaux, architecture logicielle/code source, design VHDL/Verilog
- **Exemples de documents** : 3D CAD Models, 2D Drawings, Bill of Materials, Electrical Schematics, PCB Layout, Source Code, FPGA Design files, CDR Package
- **Sensibilité** : Très élevé
- **Risque deemed export** : Très élevé
- **Point de vigilance** : Coeur de la donnée contrôlée. Un modèle CAO d'article ITAR est ITAR. Le code source d'un système de guidage est classifiable. Les BOM révèlent composants contrôlés.

### Phase 6 — Analyse et simulation
- **Description** : FEA, CFD, EMC/EMI, fiabilité (FMEA), sûreté (FHA/PSSA/SSA), simulations de performance
- **Types de données** : Rapports FEA, CFD, EMC/EMI, FMEA/FMECA, analyses de sûreté, modèles Simulink/Matlab, rapports de tolérance
- **Exemples de documents** : Stress Analysis Report, Thermal Analysis Report, EMC Analysis Report, FMEA Worksheets, Simulation Results
- **Sensibilité** : Très élevé
- **Risque deemed export** : Très élevé
- **Point de vigilance** : Les résultats de simulation révèlent les performances RÉELLES — souvent plus sensibles que les plans. Un rapport CFD montrant la signature IR d'un aéronef militaire est hautement contrôlé.

### Phase 7 — Prototypage (Prototyping)
- **Description** : Fabrication de prototypes, maquettes fonctionnelles, prototypes logiciels, bancs de développement
- **Types de données** : Dossiers de fabrication prototype, rapports EM/DM, configurations prototypes, instructions de montage, versions logicielles de développement
- **Exemples de documents** : Engineering Model Build Package, Development Model Documentation, Prototype Configuration Record
- **Sensibilité** : Élevé
- **Risque deemed export** : Élevé
- **Point de vigilance** : Le prototype est déjà un article contrôlé. La documentation de fabrication relève à la fois du développement et de la production. Double classification potentielle.

### Phase 8 — Vérification et validation (Design V&V)
- **Description** : Essais qualification, essais environnementaux, fonctionnels, EMC, sûreté, V&V logiciel/hardware
- **Types de données** : Plans de V&V, procédures de qualification, rapports d'essais (DO-160, MIL-STD-810, MIL-STD-461), V&V DO-178C/DO-254
- **Exemples de documents** : QTP, QTR, Environmental Test Reports, EMC Test Reports, Software Verification Results
- **Sensibilité** : Très élevé
- **Risque deemed export** : Élevé
- **Point de vigilance** : Les résultats d'essais de qualification documentent les performances mesurées vs. seuils de contrôle. Directement classifiants.

### Phase 9 — Certification
- **Description** : Dossiers de certification, plans (PSAC, PHAC), conformité, déclarations de design
- **Types de données** : Dossiers TC/STC, plans PSAC/PHAC, matrices de conformité, TCDS, DDP
- **Exemples de documents** : PSAC, PHAC, Compliance Matrix, Type Certificate Data Sheet, DDP, Certification Summary Reports
- **Sensibilité** : Élevé
- **Risque deemed export** : Moyen
- **Point de vigilance** : Les données de certification documentent les capacités validées. Les TCDS ou DDP contiennent des informations de performance classifiantes même si le document est « administratif ».

---

## PRODUCTION

### Phase 10 — Industrialisation (Process Development)
- **Description** : Développement procédés de fabrication, gammes, qualification procédés, programmes CN
- **Types de données** : Procédés spéciaux (soudure, brasage, TT, TS, dépôts), gammes MPI, PQR, programmes CNC, paramètres procédés critiques
- **Exemples de documents** : MPI, PQR, CNC Programs, Special Process Specifications, Work Instructions, Process Flow Diagrams
- **Sensibilité** : Élevé
- **Risque deemed export** : Élevé
- **Point de vigilance** : Les procédés de fabrication sont contrôlables INDÉPENDAMMENT de l'article. Un procédé de revêtement barrière thermique peut avoir son propre ECCN.

### Phase 11 — Outillages (Tooling)
- **Description** : Conception et fabrication outillages de fabrication et de test
- **Types de données** : Plans d'outillages, spécifications ATE, rapports de qualification outillages
- **Exemples de documents** : Tooling Design Drawings, Jig & Fixture Specifications, ATE Specs, Tooling Qualification Reports
- **Sensibilité** : Moyen à élevé
- **Risque deemed export** : Moyen
- **Point de vigilance** : Un outillage « specially designed » pour fabriquer un article contrôlé peut lui-même être contrôlé.

### Phase 12 — Premier article (FAI)
- **Description** : Fabrication premier article série, inspection FAI (AS9102), validation chaîne de production
- **Types de données** : Rapport FAI (AS9102), mesures dimensionnelles, résultats CND, validation chaîne production
- **Exemples de documents** : First Article Inspection Report, Dimensional Inspection Report, NDT Results, PRR
- **Sensibilité** : Élevé
- **Risque deemed export** : Moyen
- **Point de vigilance** : Le FAI est le pont entre développement et production. Contient des données de performance mesurées dans un contexte de production. Double nature.

### Phase 13 — Production série (Series Production)
- **Description** : Fabrication récurrente, gestion supply chain, approvisionnement composants contrôlés
- **Types de données** : Ordres de fabrication, rapports de production, traçabilité matières, CCPU, NCR, données supply chain
- **Exemples de documents** : Production Orders, Material Certifications, Batch Records, NCR, Supply Chain Records
- **Sensibilité** : Moyen
- **Risque deemed export** : Moyen
- **Point de vigilance** : Les données de traçabilité (BOM de production) peuvent exposer des composants contrôlés.

### Phase 14 — Assemblage et intégration
- **Description** : Assemblage sous-ensembles, intégration système, câblage, chargement logiciel
- **Types de données** : Instructions d'assemblage, procédures d'intégration, plans de câblage, procédures de chargement logiciel, configurations
- **Exemples de documents** : Assembly Work Instructions, System Integration Procedures, Wiring Diagrams, Software Loading Procedures, As-Built Configuration Records
- **Sensibilité** : Élevé
- **Risque deemed export** : Moyen
- **Point de vigilance** : CRITIQUE — la classification peut CHANGER à l'intégration. Un sous-ensemble non contrôlé intégré dans un système contrôlé peut devenir contrôlé. Évaluer au niveau système.

### Phase 15 — Essais et recette (Production Testing)
- **Description** : Essais d'acceptation usine (FAT), tests fonctionnels, CND/NDT, certificats
- **Types de données** : ATP, rapports FAT, rapports qualité, résultats CND, certificats de conformité, certificats libératoires (EASA Form 1, FAA 8130-3)
- **Exemples de documents** : Acceptance Test Procedures, Factory Acceptance Test Report, NDT Reports, Certificate of Conformity, EASA Form 1
- **Sensibilité** : Moyen
- **Risque deemed export** : Faible
- **Point de vigilance** : Distinguer essais PRODUCTION (acceptance) vs DÉVELOPPEMENT (qualification). Les résultats FAT confirment les performances.

### Phase 16 — Expédition et livraison (Packaging & Shipping)
- **Description** : Conditionnement, documentation d'accompagnement, formalités export, licences
- **Types de données** : Spécifications conditionnement, packing lists, licences d'exportation, déclarations douanières, EUC
- **Exemples de documents** : Packaging Specifications, Export License Documents, End-User Certificate, Customs Declarations
- **Sensibilité** : Faible (données administratives)
- **Risque deemed export** : Faible
- **Point de vigilance** : Phase la plus « visible » mais pas la plus risquée pour les fuites de données techniques. Le vrai risque est en amont.

---

## UTILISATION

### Phase 17 — Installation
- **Description** : Procédures d'installation, montage sur plateforme, raccordements, configuration initiale
- **Types de données** : Manuels d'installation, procédures de montage, plans d'implantation, procédures de raccordement/configuration
- **Exemples de documents** : Installation Manual, Installation Design Package, Site Preparation Guide, Interconnection Diagrams
- **Sensibilité** : Moyen
- **Risque deemed export** : Élevé
- **Point de vigilance** : L'installation implique souvent du personnel sur site chez le client (étranger) = deemed export de technologie d'utilisation. Nécessite TAA (ITAR) ou licences.

### Phase 18 — Mise en service (Commissioning)
- **Description** : Essais SAT, calibration, validation opérationnelle, formation opérateurs
- **Types de données** : Procédures SAT, rapports de mise en service, procédures de calibration, programmes/supports de formation
- **Exemples de documents** : SAT Procedures & Reports, Calibration Procedures, Training Materials, Operational Validation Reports
- **Sensibilité** : Moyen
- **Risque deemed export** : Très élevé
- **Point de vigilance** : La FORMATION est le cas emblématique du deemed export : un ingénieur qui forme un opérateur étranger transfère de la technologie contrôlée.

### Phase 19 — Exploitation / Opération
- **Description** : Utilisation opérationnelle, manuels opérateur, procédures d'exploitation
- **Types de données** : Manuels opérateur, SOP, données de performance opérationnelle, logs, rapports d'incidents
- **Exemples de documents** : Operating Manual, Standard Operating Procedures, Performance Logs, Mission Reports
- **Sensibilité** : Faible à moyen
- **Risque deemed export** : Moyen
- **Point de vigilance** : Les manuels opérateur sont moins sensibles SAUF s'ils révèlent des capacités opérationnelles (portée, précision, modes de fonctionnement).

### Phase 20 — Maintenance programmée (Scheduled Maintenance)
- **Description** : CMM, AMM, bulletins de service, inspections périodiques
- **Types de données** : CMM, AMM, SB, cartes de travail, programmes de maintenance, IPC
- **Exemples de documents** : Component Maintenance Manual, Aircraft Maintenance Manual, Service Bulletins, Maintenance Task Cards, IPC
- **Sensibilité** : Moyen
- **Risque deemed export** : Élevé
- **Point de vigilance** : Phase souvent SOUS-ESTIMÉE en volume de données contrôlées. Les CMM et SB circulent massivement entre OEM, MRO et opérateurs sans contrôle adéquat. Risque systémique.

### Phase 21 — Réparation (Repair)
- **Description** : Procédures de réparation, diagnostic de pannes, échange standard LRU/SRU
- **Types de données** : Procédures de réparation, guides de troubleshooting, rapports diagnostic, procédures d'échange standard, dérogations
- **Exemples de documents** : Repair Procedures, Troubleshooting Manual, Structural Repair Manual, Non-Conformance Reports, RMA
- **Sensibilité** : Moyen
- **Risque deemed export** : Élevé
- **Point de vigilance** : Le support technique à distance (remote troubleshooting) vers un MRO étranger est un transfert intangible de technologie.

### Phase 22 — Révision générale (Overhaul)
- **Description** : Démontage complet, inspection, remise à neuf, re-certification
- **Types de données** : Procédures de révision, rapports d'inspection après démontage, spécifications de remise à neuf, données de re-certification
- **Exemples de documents** : Overhaul Manual, Teardown Inspection Report, Overhaul Work Scope, Post-Overhaul Test Report
- **Sensibilité** : Moyen
- **Risque deemed export** : Élevé
- **Point de vigilance** : L'overhaul par un MRO étranger nécessite le transfert de documentation technique substantielle. Risque élevé si le MRO emploie des ressortissants de pays sensibles.

### Phase 23 — Modification et mise à jour (Modification & Upgrade)
- **Description** : Engineering Changes, mises à jour logicielles, retrofits, kits de modification, gestion obsolescence
- **Types de données** : ECO, EO, dossiers de modification, mises à jour logicielles, kits de modification, études d'obsolescence
- **Exemples de documents** : Engineering Change Notice, Engineering Order, Modification Kit Instructions, Software Update Package, Obsolescence Management Plan
- **Sensibilité** : Élevé
- **Risque deemed export** : Très élevé
- **Point de vigilance** : CAS HYBRIDE CRITIQUE — une modification génère de la technologie de DÉVELOPPEMENT (nouveau design) dans un contexte d'UTILISATION. Classifier selon la NATURE du document (conception = dev), pas la phase du cycle de vie.

### Phase 24 — Fin de vie et démantèlement (Disposal)
- **Description** : Retrait de service, destruction contrôlée, démilitarisation, archivage
- **Types de données** : Procédures de retrait, certificats de destruction, rapports de démilitarisation, registres d'archivage
- **Exemples de documents** : Decommissioning Plan, Certificate of Destruction, Demilitarization Certificate, Data Disposition Records
- **Sensibilité** : Faible à moyen
- **Risque deemed export** : Faible
- **Point de vigilance** : Obligations PERSISTANTES même après fin de vie : les données techniques archivées restent contrôlées. Vérifier les obligations de destruction/retour dans les accords de licence.
