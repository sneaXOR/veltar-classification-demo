# Faux positifs — Ce qui N'EST PAS une donnée technique export contrôlée

> Ce fichier aide l'agent à éviter les faux positifs en identifiant les types de documents et de contenu qui ne sont généralement PAS des données techniques au sens de l'export control.

---

## Documents NON techniques par défaut

Les types suivants ne sont généralement PAS des données techniques export contrôlées :

Contrats commerciaux ; Bons de commande (PO / Purchase Order) ; Factures ; Documents de shipping/expédition sans détail technique ; Planning projet ; Organigrammes ; KPI génériques ; Qualité système purement administrative (ISO 9001 sans contenu produit) ; Documents RH / finance / juridique ; Comptes-rendus purement managériaux ; Catalogues marketing ; Brochures commerciales ; Photos externes non révélatrices de la conception interne ; Checklists purement administratives ; Fiches fournisseur purement commerciales ; NDA / contrats de confidentialité (le contrat lui-même, pas ses annexes techniques) ; Risk register non technique ; Communications internes sans contenu technique.

---

## Documents de référence-only (faux positifs fréquents)

Les documents de référence-only sont la source la plus courante de faux positifs. Ils **mentionnent**, **listent** ou **pointent vers** des éléments techniques sans transmettre le savoir-faire nécessaire pour développer, produire ou utiliser l'équipement.

### Patterns typiques

- Listes de numéros d'outillage avec quantités mais SANS dimensions, tolérances ou matériaux
- Registres de documents ou index listant des P/N et titres de documents
- Listes d'approvisionnement avec références de pièces et quantités commandées
- Logs de références 3D listant des noms de fichiers CATIA/NX SANS données géométriques
- Lettres de transmission référençant des dessins SANS les inclure
- Listes de configuration (P/N, effectivité, révision) SANS détail de conception
- Bons de livraison avec références techniques mais sans contenu technique

### Test du "retrait des références"

**Retirer tous les numéros de pièce, références de documents, numéros d'outillage et quantités. Reste-t-il du contenu technique exploitable ?**

- Si OUI → le document est probablement technique (les références sont un complément)
- Si NON → le document est référence-only et N'EST PAS une donnée technique

### Malus de scoring pour les documents référence-only

- Document ne contenant QUE des P/N, numéros d'outillage, quantités et références : **-15 à -25 points**
- Un document référence-only ne devrait jamais dépasser un score de 25/100

### Exemples concrets

- "Tooling n°52301D54521086200, qty 1, ref 3D CATIA_v5_rev2" → RÉFÉRENCE-ONLY (pas de dimensions, pas de matériaux, pas de procédé)
- "P/N 1234-5678, Rev C, effectivity MSN 001-100" → RÉFÉRENCE-ONLY (pas de spécifications)
- "Voir dessin DWG-A320-042 pour détails" → RÉFÉRENCE-ONLY (le dessin n'est pas dans ce document)

---

## ATTENTION — Exceptions importantes

Ces documents peuvent REDEVENIR techniques s'ils embarquent en pièce jointe ou en corps :
- Un drawing
- Une specification
- Un process step
- Une repair instruction
- Un test result
- Une architecture
- Des controlled performance data
- Des paramètres techniques (dimensions, tolérances, matériaux)

Règle : scanner le contenu et les pièces jointes, pas seulement le type documentaire.

---

## Ce que les réglementations excluent explicitement

### Exclusions FR ML22

Le point ML22 ne vise pas :
a. la "technologie" minimale nécessaire à l'installation, à l'exploitation, à l'entretien (vérification) ou à la réparation des articles qui ne sont pas contrôlés ou dont l'exportation a été autorisée ;
b. la "technologie" relevant "du domaine public", la "recherche scientifique fondamentale" ou l'information minimale nécessaire au dépôt de demandes de brevets ;
c. la "technologie" afférente à l'induction magnétique pour la propulsion continue d'engins de transport civil.

### Exclusions EU GTN (General Technology Note)

Controls do not apply to that "technology" which is the minimum necessary for the installation, operation, maintenance (checking) or repair of those goods which are not controlled or whose export has been authorised.

Controls on "technology" transfers do not apply to information "in the public domain", to "basic scientific research" or to the minimum necessary information for patent applications.

### Exclusion EU GSN (General Software Note)

Categories 1 to 9 do not control "software" which is:
a. Generally available to the public by being sold from stock at retail selling points, without restriction, and designed for installation by the user without further substantial support by the supplier;
b. "In the public domain"; or
c. The minimum necessary "object code" for installation, operation, maintenance or repair of authorized items.

### "Domaine public" / "In the public domain"

"Technologie" ou "logiciel" ayant été rendu accessible sans qu'il ait été apporté de restrictions à sa diffusion ultérieure.

Note : Les restrictions relevant du droit d'auteur (copyright) n'empêchent pas une "technologie" ou un "logiciel" d'être considérés comme relevant du « domaine public ».

Exemples de domaine public :
- Publications académiques librement accessibles
- Manuels universitaires
- Standards publiés et librement disponibles
- Principes scientifiques, mathématiques ou d'ingénierie couramment enseignés

### Familles de documents qui relèvent typiquement du domaine public

Indépendamment de l'industrie ou de la typologie technique, les FAMILLES suivantes sont, par leur nature, publiques et donc généralement exclues du contrôle ML22 par la Note 2(b). Cette liste est non-limitative — le principe est : tout document publié par un organisme officiel pour diffusion sans restriction.

**1. Spécifications/normes publiées par un organisme d'achat ou de standardisation officiel**
- Exemples non-limitatifs d'organismes : DoD (catalogue ASSIST), OTAN (STANAG publics), MOD UK (DEF-STAN publics), DGA (textes publics), agences spatiales (ECSS), organismes nationaux et internationaux de normalisation (AFNOR, BSI, DIN, ISO, IEC, EN, IEEE, ASTM, ANSI, etc.).
- Critère opérationnel : le document est-il téléchargeable ou consultable sans restriction sur un portail officiel ? Si oui → domaine public présumé.

**2. Documents portant une mention de mise à disposition publique**
- "Distribution Statement A — Approved for public release"
- "Approved for public release", "Cleared for public release", "Publication unlimited", "Distribution unlimited"
- Mentions équivalentes nationales (ex : "diffusion sans restriction", "non protégé")
- L'apparition d'une telle mention dans un document est un argument FORT pour l'exclusion Note 2(b).

**3. Datasheets et documentation technique de composants ou produits commerciaux**
- Fiches techniques publiées par les fabricants ou distributeurs (catalogues commerciaux, sites publics).
- Documentation produite pour la vente sans restriction de diffusion.

**4. Publications académiques, manuels universitaires, brevets**
- Articles dans des revues à diffusion ouverte ou achetable.
- Manuels d'enseignement.
- Information minimale au dépôt de brevet (Note 2 ML22 c).

**5. Documents en libre accès sur un site officiel ou commercial**
- Tout document disponible publiquement sans procédure d'autorisation ni clause de confidentialité.

### Test du "domaine public" pour ML22

Avant de classer un document en ML22, te poser :
1. **Origine** : le document provient-il d'un organisme officiel publiant pour diffusion non restreinte (organisme de normalisation, agence d'achat publique, fabricant via catalogue commercial public, université, organisme de brevets) ?
2. **Marquage** : le document porte-t-il explicitement une mention de mise à disposition publique ?
3. **Accessibilité** : le document est-il téléchargeable ou consultable librement sans procédure d'autorisation ni accord de confidentialité ?
4. **Contenu** : le document expose-t-il une connaissance/savoir-faire qui n'a pas été restreinte par son émetteur ?

Si OUI à au moins l'une des questions 1-3 → l'exclusion ML22 Note 2(b) "domaine public" doit être appliquée, et `is_technical_data` reste False (ou bascule vers une étiquette dédiée si l'architecture le prévoit).

NB : le copyright/droit d'auteur n'empêche PAS le domaine public au sens du contrôle export. Un document peut être protégé par copyright (achetable) ET relever du domaine public au sens Note 2(b).

### "Recherche scientifique fondamentale" / "Basic scientific research"

Travaux théoriques ou expérimentaux, entrepris principalement en vue de l'acquisition de connaissances nouvelles touchant les principes fondamentaux de phénomènes ou de faits observables, et non essentiellement orientés vers un but ou un objectif pratique.

---

## Signaux de NON-technicité

Si le document présente UNIQUEMENT ces caractéristiques, il est probablement non technique :

- Pas de dimensions, tolérances, ou paramètres techniques
- Pas de séquence d'opérations ou de procédures
- Pas de référence à des pièces, composants, ou systèmes spécifiques
- Pas de schémas, dessins, ou vues techniques
- Pas de critères d'acceptation ou de rejet
- Contenu purement organisationnel, financier, ou managérial
- Langage purement commercial ou marketing
- Informations génériques disponibles publiquement

---

## Cas ambigus courants

### Présentations techniques

Les présentations (PowerPoint, etc.) sont ambiguës :
- Si elles contiennent des schémas d'architecture, des paramètres de performance, des données de conception → TECHNIQUE
- Si elles sont purement des slides de status meeting managérial → NON TECHNIQUE

### Meeting minutes

- Minutes avec actions techniques détaillées, paramètres, décisions de design → TECHNIQUE
- Minutes purement managériales/organisationnelles → NON TECHNIQUE

### Emails

- Email contenant des drawings, tolerances, parameters, process steps en pièce jointe ou dans le corps → TECHNIQUE
- Email purement administratif → NON TECHNIQUE

### Formation / Training

- Training manuals contenant des procédures de maintenance/repair/testing → TECHNIQUE (ML14 potentiellement)
- Formation générale sans contenu technique contrôlé → NON TECHNIQUE

### Photos / Images

- Photos révélant la conception interne, le set-up de fabrication, l'assemblage → TECHNIQUE
- Photos externes non révélatrices (photo marketing du produit fini) → NON TECHNIQUE

---

## Malus de scoring pour les faux positifs

- Contrat, facture, PO, planning, organigramme, RH, budget, KPI génériques, com interne : -30 points
- Marketing / brochure / vente sans détail technique : -25 points
- Qualité système purement administrative : -20 points
