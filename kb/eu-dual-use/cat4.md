# Category 4 — Computers

> Source: Regulation (EU) 2021/821, Annex I

Note 1: Computers, related equipment and "software" performing telecommunications or "local area network" functions must also be evaluated against Category 5, Part 1.
Note 2: Control units which directly interconnect the buses or channels of central processing units, 'main storage' or disk controllers are not regarded as telecommunications equipment in Category 5, Part 1.

Technical Note: 'Main storage' is the primary storage for data or instructions for rapid access by a central processing unit.

## 4A — Systems, Equipment and Components

### 4A001

Electronic computers and related equipment, having any of the following, and "electronic assemblies" and specially designed components therefor:

a. Specially designed to have any of the following:
   1. Rated for operation at ambient temperature below 228 K (-45°C) or above 358 K (85°C);
      Note: Does not control computers specially designed for civil automobile, railway train or "civil aircraft" applications.
   2. Radiation hardened to exceed: (a) Total Dose 5 x 10^3 Gy (silicon); (b) Dose Rate Upset 5 x 10^6 Gy (silicon)/s; or (c) Single Event Upset 1 x 10^-8 Error/bit/day.
      Note: Does not control computers specially designed for "civil aircraft" applications.
b. Not used.

### 4A003

"Digital computers", "electronic assemblies", and related equipment therefor, as follows and specially designed components therefor:

Note 1: Includes vector processors, array processors, digital signal processors, logic processors, equipment designed for "image enhancement".

Note 2: Control status determined by other equipment if: (a) essential for operation; (b) not a "principal element"; (c) "technology" determined by 4E.

b. "Digital computers" having an "Adjusted Peak Performance" ("APP") exceeding 29 Weighted TeraFLOPS (WT)
c. "Electronic assemblies" specially designed or modified for enhancing performance by aggregation of processors so that the "APP" exceeds 29 WT
g. Equipment for aggregating performance providing unidirectional data rates exceeding 2.0 Gbyte/s per link
   Note: Does not control internal interconnection equipment, passive interconnection, "network access controllers" or "communications channel controllers".

### 4A004

Computers: (a) 'Systolic array computers'; (b) 'Neural computers'; (c) 'Optical computers'.

### 4A005

Systems, equipment, and components therefor, specially designed or modified for the generation, command and control, or delivery of "intrusion software".

### 4A101

Analogue computers, "digital computers" or digital differential analysers, ruggedized and designed or modified for use in space launch vehicles (9A004) or sounding rockets (9A104).

### 4A102

Hybrid computers specially designed for modelling, simulation or design integration of space launch vehicles or sounding rockets.

## 4B — None

## 4C — None

## 4D — Software

### 4D001
a. "Software" specially designed or modified for "development" or "production" of equipment or "software" in 4A001 to 4A004, or 4D.
b. "Software" specially designed or modified for "development" or "production" of: 1. "Digital computers" with "APP" exceeding 15 WT; 2. "Electronic assemblies" exceeding that limit.

### 4D004
"Software" specially designed or modified for the generation, command and control, or delivery of "intrusion software".

## 4E — Technology

### 4E001
a. "Technology" for "development", "production" or "use" of equipment or "software" in 4A or 4D.
b. "Technology" for "development" or "production" of: 1. "Digital computers" with "APP" exceeding 15 WT; 2. Related "electronic assemblies".
c. "Technology" for the "development" of "intrusion software".
   Note 1: 4E001.a. and 4E001.c. do not control "vulnerability disclosure" or "cyber incident response".

---

## Technical Note on "Adjusted Peak Performance" ("APP")

"APP" is an adjusted peak rate at which "digital computers" perform 64-bit or larger floating point additions and multiplications, expressed in Weighted TeraFLOPS (WT).

Calculation: APP = sum of (Wi x Ri) for all processors, where:
- For 'vector processors': Wi = 0.9
- For non-'vector processors': Wi = 0.3
- Ri = peak floating point calculating rate for processor i
