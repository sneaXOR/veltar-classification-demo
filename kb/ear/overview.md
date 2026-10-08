# EAR -- Commerce Control List (CCL)

> Source: 15 CFR Part 774, Supplement No. 1 (Export Administration Regulations)
> Authority: Export Control Reform Act of 2018 (50 U.S.C. 4801-4852)
> Administered by: Bureau of Industry and Security (BIS), U.S. Department of Commerce

## CCL Structure

The Commerce Control List contains **10 categories** (0-9), each with **5 control groups** (A-E):

| Group | Code | Description |
|-------|------|-------------|
| A | Equipment | End items, assemblies, and components |
| B | Test/Production | Test, inspection, and production equipment |
| C | Materials | Materials and substances |
| D | Software | Software for items in A, B, or C |
| E | Technology | Technology for items in A, B, C, or D |

## ECCN Format

Each item is identified by an **Export Control Classification Number (ECCN)**: `[Category][Group][3-digit number]`

Examples: `2B001` = Category 2 (Materials Processing), Group B (Test/Production Equipment), Entry 001

## Categories

| Cat | Name | Description |
|-----|------|-------------|
| 0 | Nuclear & Firearms | Nuclear materials/equipment, firearms, ammunition |
| 1 | Materials & Chemicals | Special materials, chemicals, microorganisms, toxins |
| 2 | Materials Processing | Machine tools, metalworking, manufacturing equipment |
| 3 | Electronics | Electronic components, circuits, semiconductors |
| 4 | Computers | Computer systems, equipment, components |
| 5 | Telecom & InfoSec | Telecommunications, information security, cryptography |
| 6 | Sensors & Lasers | Optical sensors, cameras, lasers, radar |
| 7 | Navigation & Avionics | Inertial navigation, gyroscopes, avionics |
| 8 | Marine | Underwater systems, vessels, marine equipment |
| 9 | Aerospace & Propulsion | Aircraft, engines, UAVs, rockets, spacecraft |

## Order of Review (EAR)

Under EAR, the classification order is:
1. Check if the item is on the USML (ITAR) FIRST -- if yes, ITAR applies
2. If NOT on USML, check the CCL for applicable ECCN
3. If no ECCN applies, the item is classified as **EAR99** (no license required for most destinations)

## 600-Series Items

The 600-series ECCNs (e.g., 0A606, 1A613, 9A610) control items that were transferred from the
USML to the CCL as part of Export Control Reform (ECR). These are "military items controlled
under EAR" and have stricter controls than typical dual-use items.

## Relationship to EU Dual-Use

The CCL and the EU Annexe I both derive from the Wassenaar Arrangement. Many ECCNs have
equivalent entries in the EU list. The 10-category structure and ECCN numbering (NXNNN) are
shared between both systems. However, the CCL has additional entries (600-series, 9x515)
and different threshold values in some cases.

## General Technology Note (GTN)

The export of "technology" that is "required" for the "development," "production," or "use"
of items controlled on the CCL is controlled to the same level as the item itself.
"Required" technology means only that portion which is peculiarly responsible for achieving
or exceeding the controlled performance levels.

## General Software Note (GSN)

The CCL does not control "software" that is any of the following:
- Generally available to the public (retail sale, free download)
- In the public domain
- The minimum necessary "object code" for installation, operation, maintenance, or repair
