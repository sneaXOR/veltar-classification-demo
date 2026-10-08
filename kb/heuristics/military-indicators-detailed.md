# Critères détaillés d'analyse militaire

> Ce fichier détaille les critères d'analyse pour déterminer si un composant, équipement ou système est « spécialement conçu ou modifié pour un usage militaire » au sens de la liste ML.
> Sources officielles : Arrêté du 27 juin 2012 modifié (texte de référence ML) ; Guide DGA/DICE/SDCE/BRSI du classement des matériels de guerre et matériels assimilés (Édition 2.0 d'octobre 2025) ; Lignes directrices UE de février 2022 sur le « bien spécialement conçu pour l'usage militaire ».

---

## Principe fondamental

La notion de « spécialement conçu ou modifié pour l'usage militaire » est liée à la nature des travaux préparatoires à la production (ou à la modification) du matériel.

Un produit est considéré comme spécialement conçu pour l'usage militaire lorsqu'il a été développé et fabriqué ou modifié pour cette finalité, en recherchant des caractéristiques et des performances spécifiques à l'emploi opérationnel.

**Ces fonctionnalités et performances opérationnelles caractérisent le matériel AVANT sa forme, son apparence ou sa couleur.**

---

## Critère 1 — Nature du matériel

Questions à se poser :

1. **S'agit-il d'une arme, d'un système d'armes ou d'une munition dont l'emploi est réservé aux forces armées ?**
   - Armes à feu automatiques, lance-missiles, torpilles, bombes, grenades
   - Systèmes de guidage, détonateurs, charges militaires

2. **S'il ne s'agit pas intrinsèquement d'une arme, s'agit-il d'un matériel destiné à mettre en oeuvre les armes ou systèmes d'armes ?**
   - Systèmes de conduite de tir
   - Plateformes de lancement
   - Systèmes de visée et de désignation d'objectifs
   - Mécanismes d'armement et de largage

**Indicateurs positifs** : mention explicite d'arme, munition, système de tir, engagement de cible, neutralisation.

**Indicateurs négatifs** : équipement purement civil sans lien avec l'armement (ex: train d'atterrissage standard, système de divertissement de bord).

---

## Critère 2 — Adaptation aux conditions de l'emploi opérationnel

Le matériel est-il conçu ou modifié pour résister aux conditions particulières de l'emploi opérationnel ? Analyser systématiquement chaque sous-critère :

### 2.1 Résistance aux accélérations, environnements vibratoires et chocs
- Profils vibratoires MIL-STD-810 (vs DO-160 pour civil)
- Spécifications de choc (ex: choc pyrotechnique, choc balistique)
- Accélérations élevées (>15g pour applications munitions, missiles)
- Références à des normes militaires de qualification environnementale

### 2.2 Tenue aux gammes de températures extrêmes
- Le guide DGA évoque qualitativement « des gammes de températures très basses ou très élevées », SANS seuil chiffré officiel. Aucune plage chiffrée n'est, à elle seule, un critère ML.
- Beaucoup de composants industriels civils (automobile haut de gamme, aérospatial certifié civil, énergie, instrumentation, mining, oil&gas) opèrent largement au-delà de -40/+85.
- Le critère devient concluant uniquement quand la plage est associée à un durcissement explicitement justifié par un besoin opérationnel militaire identifié (opération arctique prolongée, désert sous insolation, NBC, EMP combiné, qualification spéciale aux conditions de combat).
- Référence à MIL-STD-810 Method 501/502 = signal indicatif à corroborer, jamais concluant seul (DO-160 civil aéronautique couvre les mêmes méthodes pour applications civiles).

### 2.3 Camouflage visuel, sonore, magnétique ou infrarouge
- Réduction de signature radar (RCS), furtivité
- Réduction de signature infrarouge (IR)
- Réduction de signature acoustique (sous-marins, véhicules)
- Réduction de signature magnétique
- Peintures/revêtements absorbants radar (RAM)
- Traitements anti-reflet militaires

### 2.4 Durcissement aux radiations ou à l'IEM
- Durcissement NEMP (Nuclear Electromagnetic Pulse)
- Résistance EMP / HEMP
- Blindage TEMPEST
- Composants « rad-hard » (durcis aux radiations)
- Spécifications MIL-STD-461 (EMI/EMC militaire) au-delà des exigences civiles

### 2.5 Affichage de valeurs militaires
- Affichage de données que seuls des matériels militaires peuvent rencontrer
- Modes de fonctionnement spécifiques aux opérations militaires
- Interfaces homme-machine spécifiques à l'emploi opérationnel

### 2.6 Mode dégradé opérationnel
- Maintien d'une capacité opérationnelle après dégradation du matériel
- Redondance spécifiquement conçue pour la survie au combat
- Fonctionnement en environnement NBC (nucléaire, biologique, chimique)
- Capacité de résilience après impact/dommage de combat

---

## Critère 3 — Performance opérationnelle intrinsèque

Le matériel fournit-il, dans son domaine de fonctionnement, une performance supérieure à des matériels comparables du marché civil, et exclusive à l'emploi opérationnel ?

### 3.1 Vitesse de fonctionnement
- Temps de réponse du système incompatible avec les applications civiles
- Cadence de tir, vitesse de balayage radar, taux de rafraîchissement
- Vitesse de recalcul de trajectoire, temps d'acquisition de cible

### 3.2 Vitesse et précision de la mesure
- Précision de navigation (ex: dérive gyro < seuils militaires)
- Résolution de capteurs au-delà des besoins civils
- Précision de pointage/tracking
- Précision de localisation/géolocalisation

### 3.3 Distance de mise en oeuvre / portée opérationnelle
- Portée de détection radar/sonar excédant les besoins civils
- Portée de communication en conditions adverses
- Distance d'engagement, portée de tir
- Rayon d'action des véhicules/drones

### 3.4 Efficacité des destructions recherchées
- Puissance de charge explosive
- Pouvoir de pénétration (blindage, fortifications)
- Rayon d'effet létal
- Capacité incendiaire, capacité de neutralisation

### 3.5 Protection et contre-mesures
- Protection balistique (blindage)
- Contre-mesures électroniques (ECM, ECCM)
- Systèmes leurres (chaff, flares)
- Brouillage / anti-brouillage
- Systèmes d'alerte d'approche de missiles

---

## Pièges contextuels — Familles transversales de signaux non concluants

Les FAMILLES de signaux contextuels suivantes apparaissent fréquemment dans tous types de documents (composants, équipements, sous-systèmes, plateformes, software) et toutes industries (aéronautique, naval, terrestre, électronique, optique, mécanique, software, chimie, biotech, spatial, etc.). Aucune ne peut, à elle seule, justifier `is_military: True`.

### A. Spécifications/normes d'approvisionnement et de qualification
Référentiels publiés par des organismes d'achat ou de standardisation (DoD via le catalogue ASSIST, OTAN STANAG, MOD UK, DGA, agences spatiales, organismes industriels). Exemples typologiques : MIL-PRF, MIL-DTL, MIL-S, MIL-T, MIL-STD, STANAG, DEF-STAN, ECSS, etc.

Ces référentiels :
- Sont des catalogues publics de qualification d'interchangeabilité, traçabilité, qualité.
- Sont utilisés transversalement par des acteurs civils (médical, aérospatial civil, énergie, instrumentation scientifique, automobile, ferroviaire, oil&gas, telecoms, mining, recherche).
- Ne traduisent PAS une exclusivité militaire de l'item qualifié.

### B. Codes d'inventaire/catalogue logistique
Codes d'index logistique fédéraux ou nationaux (FSC US, NSN OTAN, codes CAGE, codes douaniers, etc.). Ils classent par CATÉGORIE FONCTIONNELLE sans distinction civil/militaire. AUCUN code de ce type n'est un classement ML.

### C. Mentions explicites de mise à disposition publique
"Distribution Statement A", "Approved for public release", "Cleared for public release", "Publication unlimited", "Distribution unlimited" et leurs équivalents nationaux. Plaident pour l'application de la Note 2(b) ML22 (domaine public), pas pour une conclusion militaire.

### D. Mentions d'approbation par une agence gouvernementale ou de défense
Toute homologation par une agence d'achat gouvernementale (défense ou non : DoD, MOD, DGA, NASA, ESA, ministères divers). Indique une homologation d'achat, pas une exclusivité d'usage.

### E. Méthodes de test issues de standards militaires
Méthodes définies dans les MIL-STD (810, 461, 1311, etc.) sont aussi adoptées en aéronautique civile certifiée (DO-160), automobile, ferroviaire, industriel sévère. Concluantes uniquement combinées à un durcissement explicitement justifié par un stress opérationnel militaire (NBC, EMP/HEMP, choc pyrotechnique, survivabilité au combat).

### F. Étiquettes commerciales "military grade" / "defense grade"
Étiquettes d'achat. Ne démontrent pas, par elles seules, une conception exclusivement militaire.

### G. Citation d'un nom de programme militaire
La simple citation d'un programme dans un document ne rattache pas automatiquement le document à ce programme. Le rattachement doit ressortir du contenu (intégration, P/N spécifique au programme, certification programme, etc.).

---

## Anti-hallucination — Critère 3 Performance intrinsèque

Si le document ne fournit PAS de comparaison explicite avec des équivalents civils ET aucun baseline civil vérifiable n'est citable (standard publié, datasheet fabricant, application civile documentée) :
- Scorer `intrinsic_performance` à **inconclusive** — JAMAIS "positive" sur la base d'un baseline civil inventé.
- Mieux vaut "inconclusive" + intervention humaine que de fabriquer une comparaison non sourcée.

---

## Signaux contextuels (SECONDAIRES — ne peuvent jamais être la seule base d'analyse)

### Noms de programmes militaires connus
- Programmes français : Rafale, A400M, Leclerc, VBCI, Scorpion, Barracuda, FREMM, Caesar, Aster, MICA, Meteor, NH90, Tigre
- Programmes internationaux : F-35, Eurofighter, Patriot, THAAD, Javelin
- Le nom du programme dans le document est un indicateur fort mais pas suffisant seul

### Conventions de nommage et références
- Codes OTAN/NATO (NSN, CAGE codes)
- Références MIL-SPEC, MIL-STD, STANAG
- Préfixes de nomenclature militaire
- Suffixes « -M » ou « military » dans les P/N
- Codes projet défense (DGA, MOD, DoD)

### Standards et normes
- MIL-STD-810 (environnemental militaire) vs DO-160 (civil aéronautique)
- MIL-STD-461 (EMI/EMC militaire) vs EN 55032 (civil)
- MIL-STD-1553 (bus de données militaire)
- STANAG (standards OTAN)
- DEF STAN (UK defence)

### Autres indices contextuels
- Fonction de l'auteur (ingénieur défense vs ingénieur civil)
- Entité émettrice (direction défense vs direction civile)
- Classification de sécurité du document (Confidentiel Défense, Secret, etc.)
- Référence à des contrats DGA, MOD, DoD

---

## Directive « penser comme un ingénieur »

Pour les documents générés durant la phase de développement, l'analyse doit considérer :

1. **Spécification de besoin** : L'utilisateur final est-il un militaire ? Le cahier des charges exprime-t-il des besoins opérationnels militaires ?

2. **Fil conducteur des travaux préparatoires** : Les choix de conception visent-ils une fonctionnalité ou performance spécifique à l'emploi opérationnel ?

3. **Analyse des choix de conception** : Les matériaux, architectures, ou technologies sélectionnés sont-ils justifiés par des contraintes militaires (furtivité, durcissement, survivabilité) ou par des contraintes civiles (coût, poids, certification) ?

---

## Cas des composants

Pour un composant :
- Prendre en compte le classement du matériel auquel il est intégré
- Analyser sa définition technique précise
- Un composant conçu spécialement pour un usage militaire OU uniquement pour un ensemble supérieur classé est lui-même classé

**Exemples du guide** :
- Goujon spécialement conçu pour s'intégrer uniquement dans un propulseur d'avion de combat → ML10
- Potentiomètre spécialement conçu pour un drone militaire → ML10
- Roulement utilisable sur versions militaire ET civile d'un aéronef → non classé

---

## Exclusions importantes

- Aéronefs non de combat, non configurés militaire, certifiés civil → exclus ML10
- Moteurs militaires certifiés civil pour aéronefs civils → exclus ML10.d
- Véhicules civils blindés pour transport de fonds → exclus ML6
- Véhicules fabriqués avant 1946 → exclus ML6
- Armes à feu inertes, non automatiques, neutralisées → exclus ML1
