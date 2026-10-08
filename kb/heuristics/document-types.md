# Taxonomie des types de documents techniques — Scoring export control

> Source : Taxonomie opérationnelle des documents techniques aérospatiale/défense
> Ce fichier fournit la liste exhaustive des types de documents techniques susceptibles d'être soumis à l'export control, avec leur probabilité de classification et leur scoring.

---

## Principe

Un document est à traiter comme donnée technique potentiellement export contrôlée s'il permet raisonnablement à quelqu'un de concevoir, développer, fabriquer, assembler, intégrer, tester, maintenir, réparer ou modifier un équipement ou un sous-ensemble.

Le nom du document aide, mais le contenu prime.

---

## Labels de classification documentaire

TECH_DESIGN_SPEC — Spécifications et définition produit
TECH_DESIGN_ANALYSIS — Analyses et calculs de conception
TECH_DRAWING_CAD — Dessins, CAD, schémas
TECH_CONFIG_BOM — Configuration et nomenclatures
TECH_MFG_ENGINEERING — Industrialisation et manufacturing engineering
TECH_MFG_PROCESS — Procédés spéciaux et matériaux
TECH_QUALITY_INSPECTION — Qualité technique et inspection
TECH_TEST_QUALIFICATION — Essais, qualification, certification
TECH_INSTALL_INTEGRATION — Installation, intégration, parachèvement
TECH_MAINT_REPAIR — Maintenance, réparation, overhaul
TECH_SW_FW_FPGA — Logiciel, firmware, FPGA, données paramètres
TECH_SUPPLIER_PACKAGE — Package technique fournisseur
TECH_CHANGE_DEVIATION — Changements, écarts, dispositions de réparation
TECH_MISSION_DEFENSE — Données techniques opérationnelles/mission
NONTECH_ADMIN — Administratif non technique
NONTECH_COMMERCIAL — Commercial non technique
REVIEW_NEEDED — Revue humaine nécessaire

---

## A. Définition du produit / conception — TECH_DESIGN_SPEC

Probabilité : très élevée

Spécification système, sous-système, équipement ; System Requirement Specification (SRS) ; Equipment Specification / Technical Specification ; Functional Specification ; Performance Specification ; Interface Requirement Specification (IRS) / ICD ; Interface Control Document / Interface Definition Document ; Architecture dossier / System architecture description ; Allocation documents / requirement allocation ; Design principles / design rules ; Design justification file ; Technical description / product definition file ; Detailed design dossier ; PDR/CDR data packs ; Trade studies / design trade-off reports ; Dimensioning and tolerancing rules tied to the product ; Materials and process specifications tied to a controlled article ; Special characteristics definition ; Environmental requirement documents ; EMI/EMC design dossiers ; Thermal design dossiers ; Structural substantiation dossiers ; Stress notes / calculation notes / justification notes ; Mass properties files ; Aerodynamic definition files ; Propulsion integration files ; Wiring design dossiers ; EW / mission / tactical integration specifications ; Weapons/stores integration documents ; Flight control law technical design descriptions ; Avionics configuration definitions.

---

## B. Dessins, maquettes numériques, définition géométrique — TECH_DRAWING_CAD

Probabilité : très élevée

Engineering drawings ; 2D drawings ; 3D CAD native files ; CATIA / NX / Creo models ; Model-based definition (MBD) ; Digital Product Definition (DPD) ; Installation drawings ; Assembly drawings ; Detail drawings / piece part drawings ; Definition dossiers ; Schematics ; Wiring diagrams ; Electrical diagrams ; Hydraulic / pneumatic schematics ; Piping schematics ; Optical schematics ; PCB layouts ; Harness drawings ; Loom / bundle drawings ; General arrangement drawings ; Envelope drawings ; Loft / surface definition ; Tolerance stack-up files ; Geometric dimensioning files ; Material stack-up definitions ; CAD overlays ; Change-marked drawings ; Drawing notes / legends if needed to build or inspect ; Digital mock-up snapshots if they reveal controlled geometry/configuration.

---

## C. Nomenclatures et configuration produit — TECH_CONFIG_BOM

Probabilité : élevée

Bill of Materials (BOM) ; EBOM / MBOM / SBOM si reliée à un article contrôlé ; Parts lists ; Indented parts lists ; As-designed / as-built / as-maintained configuration records ; Product structure files ; Configuration item lists ; Configuration baseline ; Effectivity tables ; Tailored configuration dossiers ; Variant applicability matrices ; Retrofit applicability lists ; Standard parts substitution lists (si elles révèlent la conception ou la performance) ; Approved parts lists (APL) ; Critical items lists ; Controlled item lists ; Serialization/configuration traceability records.

---

## D. Industrialisation / manufacturing engineering — TECH_MFG_ENGINEERING

Probabilité : très élevée

SOE / Standard Operating Sheet / Shop Order Engineering ; AIP (si instruction/process d'industrialisation) ; Gammes de fabrication ; Manufacturing work instructions ; Process sheets / route cards ; Router / traveler ; Shop travelers ; Operation sheets ; Work orders techniques ; Manufacturing engineering dossier ; Production file / dossier de fabrication ; Build book / production pack ; Assembly sequence ; Installation sequence ; Tooling sequence ; Operation breakdown sheets ; Manufacturing plans ; Process flow diagrams ; PFMEA (quand il décrit le process et les caractéristiques techniques) ; Control plan (quand il décrit les paramètres produit/process) ; Parameter sheets / machine set-up sheets ; CNC programs ; NC toolpaths ; Post-processor settings ; Tool offset libraries ; Jig/fixture set-up instructions ; Lay-up books ; Ply books ; Composite lamination instructions ; Cure cycles / autoclave recipes ; Heat treatment instructions ; Welding procedures / WPS / PQR ; Brazing procedures ; Soldering profiles ; Surface treatment procedures ; Plating / anodizing instructions ; NDT instructions ; Special process specifications ; Manufacturing process specifications ; Acceptance criteria tied to production ; Rework instructions ; Repair during production instructions ; Nonconformance disposition instructions (if they reveal repair method) ; First Article Inspection build references ; Special tooling design files ; Tool drawings ; Fixture drawings ; GSE/GTE design docs (when tied to manufacturing or maintenance) ; Calibration procedures for production-critical benches ; Clean-room / contamination control technical instructions ; Additive manufacturing build files and parameter sets ; Materials handling specs for sensitive articles ; Packaging/preservation technical instructions (if they preserve operational characteristics).

---

## E. Matériaux, substances, procédés spéciaux — TECH_MFG_PROCESS

Probabilité : très élevée

Material specifications ; Material data sheets (when proprietary/performance linked) ; Process specifications ; Consumable specifications ; Sealant/adhesive application instructions ; Composite material system definitions ; Resin system specifications ; Metallic treatment specs ; Coating schemes ; Chemical conversion process sheets ; Propellant / energetic material process docs ; Explosive ordnance handling technical instructions ; Pyrotechnic assembly instructions ; Armor / shielding material stack definitions ; Signature reduction material/process docs.

---

## F. Logiciels embarqués et artefacts de développement — TECH_SW_FW_FPGA

Probabilité : très élevée

Source code de logiciel embarqué / mission / avionique / EW ; Firmware source ; FPGA/ASIC design files ; HDL / VHDL / Verilog files ; Software design description ; Software architecture docs ; Build instructions ; Compiler/linker settings ; CI/CD release configuration for embedded systems ; Configuration files that enable controlled performance ; Parameter databases ; Mission data package definitions ; OFP load definitions ; Software requirement specifications ; Software interface specs ; Verification procedures ; Software test vectors ; Cyber-hardening configuration for defense equipment ; Cryptographic implementation details ; Real-time OS configuration docs ; Safety-critical partitioning design docs.

---

## G. Essais, validation, qualification, certification — TECH_TEST_QUALIFICATION

Probabilité : très élevée

Test plans ; Test procedures ; Test specifications ; Test readiness review packs ; Qualification test procedures (QTP) ; Qualification test reports (QTR) ; Acceptance test procedures (ATP) ; Acceptance test reports (ATR) ; Functional test procedures ; Bench test procedures ; Integration test procedures ; Environmental test procedures ; Vibration/shock/EMI/EMC/lightning test docs ; Ground test procedures ; Flight test cards ; Flight test plans ; Flight test reports ; Instrumentation plans ; Test set-up drawings ; Test rig design docs ; Calibration procedures for test equipment ; Pass/fail criteria ; Limit curves / envelopes ; Performance maps ; Tuning or trimming procedures ; Fault insertion procedures ; Qualification deviation reports ; Verification cross-reference matrices (when linked to controlled requirements) ; Certification compliance dossiers ; Airworthiness technical justifications ; Safety of flight technical notes.

---

## H. Maintenance, repair, overhaul, support en service — TECH_MAINT_REPAIR

Probabilité : élevée à très élevée

CMM / Component Maintenance Manual ; AMM / Aircraft Maintenance Manual ; SRM / Structural Repair Manual ; MM / Maintenance Manual ; Overhaul manual ; Repair manual ; Troubleshooting manual ; Fault isolation manual ; IPC/IPL (si riche techniquement) ; Removal/installation procedures ; Inspection manuals ; Service instructions ; Field service instructions ; Depot-level repair procedures ; Bench repair procedures ; Maintenance task cards ; Scheduled maintenance task sheets ; Rework and repair schemes ; Repair approvals with technical substantiation ; Modification embodiment instructions ; Retrofit / retrofit kit instructions ; Configuration restoration procedures ; Continued airworthiness instructions ; Service bulletin technical content ; Alert service bulletin technical content ; Technical publication supplements ; Ground run / engine run procedures ; BITE interpretation guides ; Diagnostic tree docs ; Troubleshooting logic docs ; Spare replacement equivalence rules (when technically sensitive).

---

## I. Installation, intégration, parachèvement — TECH_INSTALL_INTEGRATION

Probabilité : très élevée

Installation instructions ; Integration procedures ; Final assembly line instructions ; Completion center work instructions ; Cabin installation engineering files ; Mission system installation packs ; Antenna/radome installation drawings ; Wiring installation procedures ; Routing/clearance installation rules ; Sealing/bonding instructions ; Equipment mounting instructions ; Functional integration check procedures ; Weight and balance technical impact files ; STC-like technical embodiment packs ; Final acceptance build standards ; Embodiment instructions for customer-specific configurations.

---

## J. Qualité technique / conformité produit — TECH_QUALITY_INSPECTION

Probabilité : élevée à très élevée

Inspection instructions ; Inspection plans ; Measurement procedures ; Acceptance criteria documents ; Product quality requirements ; Special characteristics monitoring plans ; FAI / First Article Inspection technical packages ; Control plans ; Measurement point definitions ; Metrology setup instructions ; Gauge design files ; Inspection fixture drawings ; NCR/MRB dispositions with repair or technical deviation details ; Concession/waiver dossiers (when they describe product deviation and technical acceptability) ; Source inspection guides ; Product audit technical checklists ; SPC definitions tied to controlled dimensions/performance.

---

## K. Safety / reliability / dependability — TECH_DESIGN_ANALYSIS

Probabilité : très élevée

FHA / Functional Hazard Assessment ; FMEA/FMECA ; Fault tree analysis ; Reliability predictions ; Maintainability analysis ; Safety assessment ; Common cause analysis ; Zonal safety analyses ; Damage tolerance analyses ; Ballistic / survivability analyses ; Vulnerability assessment technical reports ; Signature management technical reports ; EMP/HIRF hardening analyses ; Safety requirements allocation docs.

---

## L. Simulation, modélisation, calculs — TECH_DESIGN_ANALYSIS

Probabilité : très élevée

Simulation models ; Performance models ; CFD models ; FEM models ; Loads models ; Control law models ; Guidance/navigation/control models ; Digital twin files (if technically representative) ; Modeling assumptions and parameter files ; Solver setup files tied to product design ; Simulation result reports revealing performance or design margins ; Monte Carlo performance analyses ; Trade-off model repositories.

---

## M. Données opérationnelles / mission / tactiques — TECH_MISSION_DEFENSE

Probabilité : critique

Mission performance reports ; Tactical employment envelopes ; Stores release analysis ; Radar/IR/RCS characterization reports ; EW libraries or threat-response technical definitions ; Sensor fusion tuning data ; Guidance tuning files ; Weapon system boresight/alignment procedures ; Mission data load descriptions ; Platform limitation and employment technical guides ; Signature management procedures.

---

## N. Package technique fournisseur — TECH_SUPPLIER_PACKAGE

Probabilité : très élevée

Supplier technical data package (TDP) ; Statement of Work technique ; Supplier specifications ; Build-to-print package ; Source control drawing ; Item definition dossiers sent to suppliers ; Supplier process approval files ; Delegated inspection technical criteria ; Vendor repair technical capability packs ; Make/buy technical transfer packs ; Technical assistance package ; Industrial transfer dossier ; Licensed production packages.

---

## O. Changements / évolutions / écarts — TECH_CHANGE_DEVIATION

Probabilité : élevée à très élevée

Engineering Change Request (ECR) ; Engineering Change Proposal (ECP) ; Engineering Change Notice (ECN) ; Design change package ; Modification dossiers ; Deviation permits ; Waivers with technical content ; Retrofit instructions ; Obsolescence technical substitution analysis ; Root cause technical investigation reports ; Corrective action technical plans ; Problem reports with design/manufacturing details.

---

## P. Bancs, moyens d'essais, outillages, GSE/GTE — TECH_TEST_QUALIFICATION

Probabilité : élevée

Test bench design files ; Automatic test equipment procedures ; Bench software/configuration ; Interface adapters drawings ; Tooling design dossiers ; Special tool manuals ; Ground support equipment technical manuals ; Calibration and verification instructions ; Acceptance criteria for benches and fixtures ; Diagnostic bench fault trees.

---

## Q. Documentation technique livrable client — TECH_MAINT_REPAIR ou TECH_DESIGN_SPEC

Probabilité : élevée à très élevée

Technical data package (TDP) ; Data modules / S1000D technical modules ; Illustrated technical publications ; Operator manuals (when they go beyond simple user-level safe operation) ; Technical handbooks ; Depot manuals ; Technical orders ; Maintenance planning data ; Parts catalogues with engineering applicability intelligence ; Configuration management manuals tied to defense systems ; Training manuals containing maintenance/repair/testing content ; Courseware with controlled schematics or procedures.

---

## R. Données techniques dans des formats informels — REVIEW_NEEDED

Probabilité : variable (dépend du contenu)

Emails contenant drawings, tolerances, parameters, process steps ; Présentations techniques ; Design review decks ; Meeting minutes avec actions techniques détaillées ; Whiteboard photos ; Annotated screenshots of CAD or schematics ; Teams/Slack/Confluence pages techniques ; PLM extracts ; MES exports with process parameters ; ERP attachments containing technical manufacturing instructions ; Shared spreadsheets with limits, parameters, BOM, routings ; Database exports of configuration or maintenance logic ; Images/photographs that reveal internal design or manufacturing set-up.

---

## Documents NON techniques par défaut — NONTECH_ADMIN / NONTECH_COMMERCIAL

Probabilité : faible (sauf si contenu technique en annexe)

Contrats commerciaux ; Bons de commande ; Factures ; Planning projet ; Organigrammes ; KPI génériques ; Qualité système type ISO sans contenu produit ; RH / finance / juridique ; Comptes-rendus purement managériaux ; Catalogue marketing ; Brochure commerciale ; Photo externe non révélatrice ; Documents de shipping sans détail technique ; Checklists purement administratives.

ATTENTION : ces documents peuvent redevenir "techniques" s'ils embarquent en pièce jointe ou en corps : drawing, spec, process step, repair instruction, test result, architecture, controlled performance data.
