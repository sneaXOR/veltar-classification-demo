# Indicateurs techniques et scoring pour la détection de données techniques

> Ce fichier fournit les mots-clés, signaux forts et règles de scoring utilisés par l'agent pour évaluer si un document est une donnée technique au sens de l'export control.

---

## Scoring sur 100 points

### A. Score par type documentaire (+35 / +25 / +15)

+35 points : Drawing / CAD / schematic / spec / procedure / manual / test doc
+25 points : BOM / config / routing / work instruction / repair disposition
+15 points : Presentation / email / spreadsheet / meeting notes techniques

### B. Score par owner métier (+25 / +20 / +5)

+25 points : Engineering / Design Office
+25 points : Manufacturing Engineering / Industrialization
+20 points : Quality produit / inspection / MRB
+20 points : Test / certification / support engineering / MRO
+0 à +5 points : Programme / achats / finance / RH

### C. Score par contenu technique (+20 chacun, cumulable)

+20 : dimensions / tolérances / matières / géométrie
+20 : paramètres process / set-up / séquence d'opérations
+20 : procédures test / critères d'acceptation / calibration
+20 : instructions maintenance / réparation / troubleshooting
+20 : architecture / interfaces / performances / limitations

### D. Score par contexte article sensible (+20)

+20 : avionique, propulsion, structures critiques, composites, radar, EW, mission, armement, guidance, crypto, drone/UAS, satellite

### E. Malus faux positifs (-30 / -25 / -20)

-30 : contrat, facture, PO, planning, organigramme, RH, budget, KPI génériques, com interne
-25 : marketing / brochure / vente sans détail technique
-20 : qualité système purement administrative

### Seuils de décision

80-100 : quasi certain document technique export control → classification automatique proposée
60-79 : probable, revue prioritaire → classification proposée avec flag revue
40-59 : possible, revue secondaire → flag pour analyse humaine
0-39 : faible probabilité → marquer EC_Not_Technical (avec possibilité de revue)

---

## Mots-clés par domaine

### Documents de conception

specification, requirement, ICD, interface control, architecture, design description, design definition, substantiation, justification, calculation note, stress report, load case, thermal analysis, safety assessment, trade study, performance specification, functional specification

### Dessins / définition

drawing, plan, schematic, wiring diagram, assembly drawing, installation drawing, CAD, 3D model, CATIA, NX, tolerancing, GD&T, envelope, detail part, blueprint, diagram, layout, loft, surface definition

### Industrialisation / fabrication

SOE, routing, traveler, work instruction, operation sheet, manufacturing plan, process sheet, assembly sequence, lay-up, cure cycle, autoclave, tooling, fixture, jig, set-up, CNC, NC program, gamme, fabrication, industrialisation

### Qualité / contrôle

inspection instruction, control plan, acceptance criteria, FAI, first article, gauge, metrology, measurement point, conformity, special characteristic, inspection plan, measurement procedure

### Essais / qualification

test procedure, test report, ATP, QTP, qualification, verification, validation, compliance, flight test, bench test, calibration, instrumentation, test plan, test specification, QTR, ATR

### Maintenance / réparation

AMM, CMM, SRM, overhaul, repair scheme, troubleshooting, fault isolation, remove/install, service bulletin, repair instruction, maintenance task, depot repair, rework, maintenance manual

### Logiciel / électronique / mission

source code, firmware, FPGA, VHDL, Verilog, parameter file, OFP, mission data, tuning, loadable software, embedded software, HDL, ASIC, build config, cryptographic

### Changement / écart

ECN, ECR, deviation, waiver, concession, MRB, nonconformance, rework, corrective action, root cause, engineering change, modification, retrofit

---

## Signaux dans le contenu — Deux niveaux

### Tier 1 — Signaux de substance technique (+20 chacun)

Ces éléments indiquent la présence de savoir-faire exploitable pour développer, produire ou utiliser un équipement :

- Dimensions, couples, pressions, températures (valeurs numériques avec unités)
- Séquences d'opérations détaillées (Step 1, Step 2, etc.) avec paramètres
- Paramètres machine (vitesse, avance, température, pression)
- Matériaux et procédés spéciaux AVEC détails (composition d'alliages, cycles de traitement, températures de fusion)
- Tolérances (±, tolerance, IT, H7, etc.)
- Schémas ou vues internes avec cotes (coupe, section, detail view, GD&T)
- Critères d'acceptation/rejet (accept, reject, go/no-go, pass/fail)
- Méthodes de réparation avec étapes procédurales concrètes
- Procédures de test avec paramètres d'essai et critères mesurables
- Résultats de qualification/performances/limitations avec données numériques

### Tier 2 — Signaux de référence (+5 chacun, insuffisants seuls)

Ces éléments indiquent un contexte technique mais ne constituent PAS du savoir-faire exploitable à eux seuls :

- Numéros de pièce (P/N, Part Number) sans spécifications associées
- Indices/révisions (Rev, Revision, Index)
- Effectivity / applicability
- Références à des modèles 3D sans données géométriques
- Numéros d'outillage, quantités
- Consignes d'intégration/installation au niveau référence seulement (sans étapes détaillées)
- Configuration logicielle ou matérielle (version, baseline) sans code/paramètres

### Règle de combinaison

**Un document ne scorant que sur des signaux Tier 2 ne peut pas dépasser 25 points de contenu.** Les signaux Tier 2 ne deviennent significatifs que combinés avec au moins un signal Tier 1.

Autrement dit : lister des P/N, des numéros d'outillage et des quantités sans fournir de dimensions, tolérances, paramètres ou procédures NE CONSTITUE PAS une donnée technique.

---

## Mots-clés domaine défense / aéro (signal fort)

airframe, avionics, propulsion, guidance, EW, electronic warfare, radar, IR, infrared, mission, stores, nacelle, FADEC, flight control, composite layup, NDT, structural repair, qualification, airworthiness, armement, munition, missile, torpedo, warhead, ballistic, stealth, signature, countermeasure, NRBC, NBC, encryption, crypto, satellite, launcher, UAV, drone, submarine, sonar

---

## Mots-clés fonctionnels (verbes indiquant une activité technique contrôlée)

design, develop, development, produce, production, manufacture, fabricate, assemble, assembly, integrate, integration, test, testing, inspect, inspection, maintain, maintenance, repair, overhaul, modify, modification, calibrate, calibration, qualify, qualification, verify, verification, validate, validation, install, installation, operate, operation

Versions françaises : concevoir, développer, produire, fabriquer, assembler, intégrer, tester, inspecter, maintenir, réparer, réviser, modifier, calibrer, qualifier, vérifier, valider, installer, exploiter

---

## Règles métier simples (if/then)

### Règle 1 — Owner + type

Si owner appartient à {engineering, manufacturing engineering, quality produit, test, MRO}
ET type documentaire appartient à {spec, drawing, procedure, report, manual, BOM}
ALORS → high likelihood

### Règle 2 — Contenu technique

Si le document contient : paramètres, dimensions, tolérances, séquence de fabrication, test setup, critères d'acceptation, méthode de réparation
ALORS → high likelihood

### Règle 3 — Activité technique

Si le document décrit : design, development, production, assembly, integration, operation technique, maintenance, repair, overhaul, modification, test
ALORS → high likelihood

### Règle 4 — Administratif pur

Si le document est purement : contractuel, commercial, financier, RH, planning
ALORS → low likelihood, SAUF présence d'annexes techniques

### Règle 5 — Domaine sensible

Si le document concerne : avionics, propulsion, flight controls, composites, weapons/stores, radar, EW, crypto, mission systems
ALORS → augmenter fortement le score (+20)

---

## Documents Airbus/aéro à marquer haut par défaut

SOE ; gamme de fabrication ; router/traveler ; AIP (si instruction de process/industrialisation) ; work instruction ; assembly instruction ; installation dossier ; completion/parachèvement pack ; inspection instruction ; control plan ; FAI dossier ; NCR/MRB avec disposition technique ; concession/waiver avec justification technique ; engineering drawing ; CAD model ; ICD ; requirement spec ; qualification test procedure/report ; flight test report ; AMM/CMM/SRM ; repair scheme ; service bulletin technique ; source code embarqué ; FPGA files ; supplier TDP ; build-to-print package.
