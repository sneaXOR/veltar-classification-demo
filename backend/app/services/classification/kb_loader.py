from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
import re

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# Module-level caches â€" KB files don't change at runtime
_FILE_CACHE: dict[str, str] = {}
_RUBRICS_CACHE: list[tuple[str, str, str]] | None = None


def _read_cached(path: Path) -> str:
    key = str(path)
    if key not in _FILE_CACHE:
        _FILE_CACHE[key] = path.read_text(encoding="utf-8", errors="ignore")
    return _FILE_CACHE[key]


@dataclass(slots=True)
class KBBundle:
    step_name: str
    content: str
    citations: list[dict]
    pre_matched_eccns: list[dict] | None = None


# Maps simple terms found in document text â†’ ECCN rubrics they point to.
# Used to pre-identify candidate rubrics BEFORE the LLM sees the prompt.
# Each entry: regex pattern â†’ list of (eccn_code, description, key_term_matched)
# Each entry: (regex_pattern, [(eccn, description), ...])
# RULES for patterns:
#   - Use SHORT single-word stems only â€" never multi-word phrases
#   - The regulation may use different wording than the document, so match on root terms
#   - Use \b word boundaries to avoid false positives on short terms
#   - Prefer stems that work in both English and French
TERM_TO_ECCN: list[tuple[str, list[tuple[str, str]]]] = [
    # â"€â"€ Cat 2 â€" Materials Processing â"€â"€
    (r"superplastic|spf\b",            [("2E003", "Technology: superplastic forming, diffusion bonding"), ("2B004", "Hot isostatic presses")]),
    (r"isostatic",                      [("2B004", "Hot isostatic presses"), ("2B104", "Isostatic presses (MTCR)"), ("2E003", "Technology: hot isostatic densification")]),
    (r"diffusion.?bond|brasage.?diffus",[("2E003", "Technology: diffusion bonding")]),
    (r"fraisage|milling\b|grinding\b|usinage|tournage|turning\b", [("2B001", "Machine tools"), ("2B201", "Machine tools (non-2B001)")]),
    (r"\bcnc\b",                        [("2B001", "Machine tools"), ("2B201", "Machine tools (non-2B001)")]),
    (r"spin.?form|flow.?form",          [("2B009", "Spin-forming/flow-forming machines"), ("2B209", "Flow forming machines (MTCR)")]),
    (r"\bcvd\b|\bpvd\b|sputt",         [("2B005", "Equipment for coatings/surface modifications"), ("2E003", "Technology: coating processes")]),
    (r"\bcmm\b",                        [("2B006", "Dimensional inspection/measuring systems")]),
    (r"\bdie[s]?\b|mould|moule|fonderie|casting\b", [("2B204", "Dies/moulds/controls"), ("2B004", "Hot isostatic presses")]),
    # â"€â"€ Cat 1 â€" Special Materials â"€â"€
    (r"maraging",                       [("1C116", "Maraging steels"), ("1C216", "Maraging steels (MTCR)")]),
    (r"titanium|titane\b",             [("1C002", "Metal alloys for structures"), ("1C202", "Titanium alloys (MTCR)")]),
    (r"inconel|superalliage|superalloy|nimonic|waspaloy|hastelloy", [("1C002", "Metal alloys/superalloys")]),
    (r"composite\b",                    [("1A002", "Composite structures"), ("1C010", "Fibrous/filamentary materials")]),
    (r"beryllium",                    [("1C011", "Metals and compounds")]),
    # â"€â"€ Cat 7 â€" Navigation & Avionics â"€â"€
    (r"inertiel|inertial",             [("7A003", "Inertial navigation systems"), ("7A103", "INS/GNSS integrated")]),
    (r"\bimu\b",                        [("7A001", "Accelerometers"), ("7A003", "Inertial navigation systems")]),
    (r"gyroscop|gyrometr",            [("7A002", "Gyroscopes")]),
    (r"accelerometr",                 [("7A001", "Accelerometers")]),
    (r"\badiru\b|\bahrs\b",            [("7A003", "Inertial navigation systems"), ("7A103", "INS/GNSS integrated")]),
    # â"€â"€ Cat 9 â€" Aerospace & Propulsion â"€â"€
    (r"\bdrone\b|\buav\b",             [("9A012", "Unmanned aerial vehicles"), ("9A112", "UAV systems (MTCR)")]),
    (r"turbin|turbo.?react",          [("9A001", "Aero gas turbine engines")]),
    (r"fusee|rocket\b|propuls",       [("9A005", "Liquid rocket propulsion"), ("9A010", "Ramjet/scramjet/pulse detonation")]),
    # â"€â"€ Cat 6 â€" Sensors & Lasers â"€â"€
    (r"\blaser\b|\blidar\b",           [("6A005", "Lasers"), ("6A205", "Lasers (MTCR)")]),
    (r"\bradar\b",                      [("6A008", "Radar systems"), ("6A108", "Radar systems (MTCR)")]),
    (r"infrarouge|\bflir\b|thermograph", [("6A003", "Cameras and imaging systems")]),
    # â"€â"€ Cat 5 â€" Telecom & Crypto â"€â"€
    (r"crypto|chiffr|cipher|encrypt",  [("5A002", "Information security systems"), ("5D002", "Cryptographic software")]),
    # â"€â"€ Cat 3 â€" Electronics â"€â"€
    (r"\bfpga\b|\bmmic\b",            [("3A001", "Electronic components"), ("3A201", "Electronic components (MTCR)")]),
    (r"semiconduc",                     [("3A001", "Electronic components")]),
]


BASE_STEP_FILES = {
    # â"€â"€ V1 steps (preserved for backward compatibility) â"€â"€
    "step2_technical": [
        "definitions/technical-data.md",
        "heuristics/document-types.md",
        "heuristics/technical-indicators.md",
        "heuristics/false-positives.md",
    ],
    "step4_item_id": [
        "heuristics/technical-indicators.md",
        "heuristics/classification-process.md",
    ],
    "step5_military": [
        "definitions/military-use.md",
        "frml/overview.md",
    ],
    "step7_dualuse": [
        "eu-dual-use/overview.md",
        "eu-dual-use/definitions-dual-use.md",
    ],
    "step8_technology": [
        "definitions/technical-data.md",
        "eu-dual-use/overview.md",
    ],
    "step_us_experimental": [
        "itar/overview.md",
        "itar/definitions-itar.md",
    ],
    # â"€â"€ V2 steps â"€â"€
    "step_a_scan": [
        "heuristics/document-types.md",
        "heuristics/lifecycle-phases.md",
    ],
    "step_b_tangible": [
        "heuristics/technical-indicators.md",
        "heuristics/classification-process.md",
        "heuristics/false-positives.md",
    ],
    "step_c_military": [
        "definitions/military-use.md",
        "heuristics/military-indicators-detailed.md",
        "frml/overview.md",
        "frml/ML22.md",
    ],
    "step_d_techdata_ml": [
        "definitions/technical-data.md",
        "definitions/military-use.md",
        "frml/ML22.md",
    ],
    # step_e_dualuse and step_f_techdata_du removed — replaced by step_e_dualuse_unified
    # which uses load_full_eu_dualuse() and sends the entire regulation via OpenRouter.

    # ── US lane steps ──
    "step_c_itar": [
        "itar/overview.md",
        "itar/definitions-itar.md",
        # Additional USML category files are added dynamically via KEYWORD_TO_USML
    ],
    "step_e_ear_screening": [
        "ear/overview.md",
        "ear/gtn-gsn.md",
        # SSTN files are added dynamically via KEYWORD_TO_EAR or loaded fully via load_ear_screening()
    ],
    "step_e_ear_detailed": [
        "ear/overview.md",
        "ear/definitions-ear.md",
        "ear/gtn-gsn.md",
        # Full category files are loaded dynamically based on screening results
    ],
}

KEYWORD_TO_ML = {
    r"missile|torpille|munition|roquette": ["frml/ML4.md"],
    r"drone|uav|helicopter|helicoptere|helicopt|aircraft|aeronef|avion|moteur": ["frml/ML10.md"],
    r"radar|countermeasure|contre-mesure|fire control": ["frml/ML5.md"],
    r"software|firmware|fpga|code": ["frml/ML21.md"],
    r"technical data|technology|donnees? techniques": ["frml/ML22.md"],
}

# Maps document keywords → USML category files for ITAR assessment
KEYWORD_TO_USML: dict[str, list[str]] = {
    r"firearm|gun|rifle|pistol|shotgun|silencer|suppressor": ["itar/usml-catI.md"],
    r"cannon|howitzer|mortar|armament|weapon.?mount": ["itar/usml-catII.md"],
    r"ammunition|ordnance|cartridge|projectile|warhead|fuse": ["itar/usml-catIII.md"],
    r"missile|rocket|launch\s?vehicle|bomb|mine|torpedo|countermeasure": ["itar/usml-catIV.md"],
    r"explosive|propellant|pyrotechnic|energetic": ["itar/usml-catV.md"],
    r"vessel|ship|submarine|naval|sonar|mine.?sweep": ["itar/usml-catVI.md"],
    r"tank|armored|apc|ground.?vehicle|military.?vehicle|humvee|hmmwv": ["itar/usml-catVII.md"],
    r"aircraft|helicopter|drone|uav|uas|airframe|wing|rotorcraft": ["itar/usml-catVIII.md"],
    r"training.?equipment|simulator|military.?training": ["itar/usml-catIX.md"],
    r"body\s?armor|helmet|protective.?equipment|ballistic|cbrn": ["itar/usml-catX.md"],
    r"military.?electronics|electronic.?warfare|ecm|eccm|elint|sigint|jamm": ["itar/usml-catXI.md"],
    r"fire\s?control|laser|imaging|infrared|flir|thermal|night\s?vision|guidance|seeker": ["itar/usml-catXII.md"],
    r"armor\s?plate|depleted.?uranium|stealth|ram|composite|special.?material": ["itar/usml-catXIII.md"],
    r"toxicological|chemical\s?agent|biological\s?agent|tear\s?gas|riot\s?control": ["itar/usml-catXIV.md"],
    r"spacecraft|satellite|space\s?vehicle|space\s?launch|space\s?qualif": ["itar/usml-catXV.md"],
    r"nuclear|atomic|weapon\s?of\s?mass": ["itar/usml-catXVI.md"],
    r"classified": ["itar/usml-catXVII.md"],
    r"directed\s?energy|particle\s?beam|high.?power\s?microwave|hpm|laser\s?weapon": ["itar/usml-catXVIII.md"],
    r"gas\s?turbine|turbofan|turbojet|turboshaft|turboprop|jet\s?engine|apu": ["itar/usml-catXIX.md"],
    r"submersible|underwater\s?vehicle|auv|rov": ["itar/usml-catXX.md"],
}

# Maps document keywords → EAR CCL category files for dual-use screening
KEYWORD_TO_EAR: dict[str, list[str]] = {
    r"nuclear|reactor|deuterium|tritium|uranium|plutonium|firearm|ammunition": ["ear/ccl-cat0-sstn.md"],
    r"composite|alloy|fiber|fibre|titanium|maraging|inconel|superalloy|chemical|toxin|precursor|biological": ["ear/ccl-cat1-sstn.md"],
    r"cnc|machining|milling|grinding|lathe|turning|forming|press|isostatic|cvd|pvd|robot": ["ear/ccl-cat2-sstn.md"],
    r"fpga|mmic|semiconductor|circuit|electronic|adc|microprocessor|integrated": ["ear/ccl-cat3-sstn.md"],
    r"computer|processor|hybrid|digital|supercomputer": ["ear/ccl-cat4-sstn.md"],
    r"crypto|cipher|encrypt|telecom|network|optical\s?fiber|information\s?security": ["ear/ccl-cat5-sstn.md"],
    r"laser|lidar|camera|sensor|infrared|thermal|radar|sonar|acoustic|magneto": ["ear/ccl-cat6-sstn.md"],
    r"inertial|imu|gyro|acceleromet|navigation|avionics|gps|gnss|ahrs|adiru": ["ear/ccl-cat7-sstn.md"],
    r"marine|vessel|submarine|underwater|propeller|sonobuoy": ["ear/ccl-cat8-sstn.md"],
    r"aircraft|engine|turbine|uav|drone|rocket|propulsion|spacecraft|satellite|thrust": ["ear/ccl-cat9-sstn.md"],
}

KEYWORD_TO_EU = {
    r"inertial|imu|ins|gyro|accelerometer|centrale inertielle": ["eu-dual-use/cat7.md"],
    r"radar|laser|camera|optronic|electro-optical|sonar": ["eu-dual-use/cat6-part1.md", "eu-dual-use/cat6-part2.md"],
    r"turbine|propulsion|uav|drone|aerospace|rocket|launcher": ["eu-dual-use/cat9-part1.md", "eu-dual-use/cat9-part2.md"],
    r"cnc|machining|fraisage|machine-outil|tooling|outillage|forming|formage|moulage|fonderie|casting|forging|die|moule|superplastic|spf|isostatic|hot press|traitement thermique|heat treat": ["eu-dual-use/cat2-part1.md", "eu-dual-use/cat2-part2.md"],
    r"fpga|mmic|semiconductor|circuit": ["eu-dual-use/cat3-part1.md", "eu-dual-use/cat3-part2.md"],
    r"crypto|chiffrement|cipher|encrypt|ssl|tls|vpn|ipsec": ["eu-dual-use/cat5-part1.md", "eu-dual-use/cat5-part2.md"],
    r"composite|alloy|fiber|fibre|materiau|titane|titanium|maraging|inconel|superalliage|superalloy": ["eu-dual-use/cat1-part1.md", "eu-dual-use/cat1-part2.md", "eu-dual-use/cat1-part3.md"],
}

STEP_CHAR_BUDGETS = {
    # V1
    "step2_technical": 12000,
    "step4_item_id": 10000,
    "step5_military": 14000,
    "step7_dualuse": 16000,
    "step8_technology": 14000,
    "step_us_experimental": 6000,
    # V2
    "step_a_scan": 10000,
    "step_b_tangible": 10000,
    "step_c_military": 20000,
    "step_d_techdata_ml": 14000,
    # step_e_dualuse and step_f_techdata_du removed — no char budget for the unified step
    # since it sends the full regulation (~27K tokens) to a 1M-context OpenRouter model.

    # US lane
    "step_c_itar": 24000,       # USML categories can be large (overview + definitions + 2-3 categories)
    "step_e_ear_screening": 0,  # No budget — loads full SSTN screening set via load_ear_screening()
    "step_e_ear_detailed": 0,   # No budget — loads full category files via load_ear_detailed()
}

STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "from",
    "that",
    "this",
    "dans",
    "pour",
    "avec",
    "sans",
    "des",
    "les",
    "une",
    "document",
    "page",
    "sample",
    "representative",
    "technical",
}


class KBLoader:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.root = Path(self.settings.kb_root)

    def load_full_eu_dualuse(self) -> KBBundle:
        """Load ALL EU dual-use regulation files concatenated.

        Used with large-context models (e.g. OpenRouter Qwen3.6-plus, 1M tokens)
        that can ingest the entire Annexe I (~30K tokens) in a single call,
        eliminating the need for keyword pre-filtering or rubric ranking.
        """
        eu_dir = self.root / "eu-dual-use"
        if not eu_dir.exists():
            logger.warning("EU dual-use KB directory not found: %s", eu_dir)
            return KBBundle(step_name="step_e_dualuse_unified", content="", citations=[])

        content_blocks: list[str] = []
        citations: list[dict] = []
        total_chars = 0

        for md_file in sorted(eu_dir.glob("*.md")):
            file_content = _read_cached(md_file)
            relative_path = f"eu-dual-use/{md_file.name}"
            content_blocks.append(f"### {relative_path}\n{file_content}")
            citations.append({"source": relative_path, "title": md_file.name})
            total_chars += len(file_content)

        logger.info(
            "Loaded full EU dual-use KB: %d files, %d chars (~%d tokens)",
            len(content_blocks), total_chars, total_chars // 4,
        )
        return KBBundle(
            step_name="step_e_dualuse_unified",
            content="\n\n".join(content_blocks),
            citations=citations,
        )

    def load_ear_screening(self, text: str = "") -> KBBundle:
        """Load ALL EAR SSTN screening files + overview + GTN/GSN.

        Used to identify 1-3 candidate CCL categories in a single LLM call.
        Total size: ~30K tokens (all 10 SSTN files + overview + GTN/GSN).
        """
        ear_dir = self.root / "ear"
        if not ear_dir.exists():
            logger.warning("EAR KB directory not found: %s", ear_dir)
            return KBBundle(step_name="step_e_ear_screening", content="", citations=[])

        content_blocks: list[str] = []
        citations: list[dict] = []
        total_chars = 0

        # Load base files first (overview + GTN/GSN)
        for base_file in ["ear/overview.md", "ear/gtn-gsn.md"]:
            fp = self.root / base_file
            if fp.exists():
                fc = _read_cached(fp)
                content_blocks.append(f"### {base_file}\n{fc}")
                citations.append({"source": base_file, "title": fp.name})
                total_chars += len(fc)

        # Load all SSTN files
        for sstn_file in sorted(ear_dir.glob("*-sstn.md")):
            fc = _read_cached(sstn_file)
            rel_path = f"ear/{sstn_file.name}"
            content_blocks.append(f"### {rel_path}\n{fc}")
            citations.append({"source": rel_path, "title": sstn_file.name})
            total_chars += len(fc)

        logger.info(
            "Loaded EAR screening KB: %d files, %d chars (~%d tokens)",
            len(content_blocks), total_chars, total_chars // 4,
        )
        return KBBundle(
            step_name="step_e_ear_screening",
            content="\n\n".join(content_blocks),
            citations=citations,
        )

    def load_ear_detailed(self, candidate_categories: list[str]) -> KBBundle:
        """Load FULL category files for candidate CCL categories identified by screening.

        Args:
            candidate_categories: List of category numbers as strings, e.g. ["3", "6", "9"]

        Loads definitions + GTN/GSN + full category files for the specified categories.
        Typically 1-3 categories, each 50-270K chars.
        """
        ear_dir = self.root / "ear"
        if not ear_dir.exists():
            logger.warning("EAR KB directory not found: %s", ear_dir)
            return KBBundle(step_name="step_e_ear_detailed", content="", citations=[])

        content_blocks: list[str] = []
        citations: list[dict] = []
        total_chars = 0

        # Load base reference files
        for base_file in ["ear/overview.md", "ear/definitions-ear.md", "ear/gtn-gsn.md"]:
            fp = self.root / base_file
            if fp.exists():
                fc = _read_cached(fp)
                content_blocks.append(f"### {base_file}\n{fc}")
                citations.append({"source": base_file, "title": fp.name})
                total_chars += len(fc)

        # Load full category files for candidates
        for cat_num in candidate_categories:
            cat_file = ear_dir / f"ccl-cat{cat_num}.md"
            if cat_file.exists():
                fc = _read_cached(cat_file)
                rel_path = f"ear/{cat_file.name}"
                content_blocks.append(f"### {rel_path}\n{fc}")
                citations.append({"source": rel_path, "title": cat_file.name})
                total_chars += len(fc)
            else:
                logger.warning("EAR category file not found: %s", cat_file)

        logger.info(
            "Loaded EAR detailed KB for categories %s: %d files, %d chars (~%d tokens)",
            candidate_categories, len(content_blocks), total_chars, total_chars // 4,
        )
        return KBBundle(
            step_name="step_e_ear_detailed",
            content="\n\n".join(content_blocks),
            citations=citations,
        )

    def load(self, step_name: str, text: str = "") -> KBBundle:
        files = list(BASE_STEP_FILES.get(step_name, []))
        lowered = text.lower()
        if step_name in {"step5_military", "step_c_military"}:
            files.extend(self._match_keywords(lowered, KEYWORD_TO_ML))
        elif step_name in {"step7_dualuse", "step8_technology"}:
            # V1 steps: keyword-based file selection
            files.extend(self._match_keywords(lowered, KEYWORD_TO_EU))
        elif step_name == "step_e_dualuse_unified":
            pass  # Full regulation loaded via load_full_eu_dualuse(), not here
        elif step_name == "step_c_itar":
            files.extend(self._match_keywords(lowered, KEYWORD_TO_USML))
        elif step_name == "step_e_ear_screening":
            files.extend(self._match_keywords(lowered, KEYWORD_TO_EAR))

        unique_files = list(dict.fromkeys(files))
        content_blocks: list[str] = []
        citations: list[dict] = []
        total_budget = STEP_CHAR_BUDGETS.get(step_name)
        per_file_budget = max(1500, total_budget // max(len(unique_files), 1)) if total_budget else None

        for relative_path in unique_files:
            file_path = self.root / relative_path
            if not file_path.exists():
                continue
            file_content = _read_cached(file_path)
            if per_file_budget and len(file_content) > per_file_budget:
                file_content = self._excerpt_markdown(file_content, lowered, per_file_budget)
            content_blocks.append(f"### {relative_path}\n{file_content}")
            citations.append({"source": relative_path, "title": file_path.name})

        return KBBundle(step_name=step_name, content="\n\n".join(content_blocks), citations=citations)

    def _parse_all_rubrics(self) -> list[tuple[str, str, str]]:
        """Parse all EU dual-use category files into individual ECCN rubrics.
        Results are cached at module level since KB files don't change at runtime.
        """
        global _RUBRICS_CACHE
        if _RUBRICS_CACHE is not None:
            return _RUBRICS_CACHE

        eu_dir = self.root / "eu-dual-use"
        if not eu_dir.exists():
            _RUBRICS_CACHE = []
            return _RUBRICS_CACHE

        rubrics: list[tuple[str, str, str]] = []
        for cat_file in sorted(eu_dir.glob("cat*.md")):
            content = _read_cached(cat_file)
            source_file = f"eu-dual-use/{cat_file.name}"
            current_header = ""
            current_lines: list[str] = []
            for line in content.splitlines():
                if re.match(r"^###\s+\d+[A-E]\d{3}", line):
                    # ECCN rubric header â€" save previous, start new
                    if current_header and current_lines:
                        rubrics.append((current_header, "\n".join(current_lines), source_file))
                    current_header = line
                    current_lines = [line]
                elif re.match(r"^##\s", line):
                    # Section header â€" close current rubric but do NOT start a new one
                    if current_header and current_lines:
                        rubrics.append((current_header, "\n".join(current_lines), source_file))
                    current_header = ""
                    current_lines = []
                else:
                    if current_header:  # Only append if inside an ECCN rubric
                        current_lines.append(line)
            if current_header and current_lines:
                rubrics.append((current_header, "\n".join(current_lines), source_file))

        logger.info("Parsed %d ECCN rubrics from %s", len(rubrics), eu_dir)
        _RUBRICS_CACHE = rubrics
        return _RUBRICS_CACHE

    def _rank_eu_rubrics(self, text: str, budget: int) -> tuple[str, list[dict], list[dict]]:
        """Score cached ECCN rubrics against document text and return top matches within budget.

        This replaces keyword-based file selection with content-based ranking,
        so ANY document type can find relevant ECCN rubrics regardless of regex coverage.
        """
        rubrics = self._parse_all_rubrics()

        if not rubrics:
            return "", [], []

        # 3. Extract document keywords
        doc_keywords = self._extract_keywords(text)
        doc_words = set(re.findall(r"[a-z][a-z0-9]{2,}", text))

        # 4. Score each rubric by word overlap with document
        scored: list[tuple[float, int, str, str, str]] = []  # (score, index, header, text, source)
        for idx, (header, rubric_text, source) in enumerate(rubrics):
            rubric_lower = rubric_text.lower()
            # Keyword overlap score
            score = sum(2.0 for kw in doc_keywords if kw in rubric_lower)
            # General word overlap (lighter weight)
            rubric_words = set(re.findall(r"[a-z][a-z0-9]{2,}", rubric_lower))
            overlap = doc_words & rubric_words - STOPWORDS
            score += len(overlap) * 0.3
            # Boost for TERM_TO_ECCN matches (regex pre-matching still helps with ranking)
            for pattern, eccn_list in TERM_TO_ECCN:
                if re.search(pattern, rubric_lower, flags=re.IGNORECASE) and re.search(pattern, text, flags=re.IGNORECASE):
                    score += 5.0
                    break
            scored.append((score, idx, header, rubric_text, source))

        # 5. Select top rubrics within budget
        scored.sort(key=lambda x: (-x[0], x[1]))
        selected: list[str] = []
        selected_sources: set[str] = set()
        pre_matched: list[dict] = []
        remaining = budget

        for score, _idx, header, rubric_text, source in scored:
            if score < 0.5:
                break  # No point including rubrics with near-zero relevance
            if len(rubric_text) > remaining:
                # Try to fit a truncated version
                if remaining > 200:
                    rubric_text = rubric_text[:remaining].rstrip()
                else:
                    continue
            selected.append(rubric_text)
            selected_sources.add(source)
            remaining -= len(rubric_text)

            # Extract ECCN code from header for pre-matching
            eccn_match = re.search(r"(\d[A-E]\d{3})", header)
            if eccn_match and score >= 2.0:
                pre_matched.append({
                    "eccn": eccn_match.group(1),
                    "description": header.lstrip("#").strip()[:80],
                    "matched_term": f"score={score:.1f}",
                })

            if remaining <= 200:
                break

        if not selected:
            return "", [], []

        citations = [{"source": src, "title": Path(src).name} for src in sorted(selected_sources)]
        content = "### Rubriques EU dual-use les plus pertinentes pour ce document\n\n" + "\n\n".join(selected)
        return content, citations, pre_matched

    @staticmethod
    def _find_eccn_matches(text: str) -> list[dict]:
        """Scan document text against TERM_TO_ECCN to pre-identify candidate ECCN rubrics."""
        seen: set[str] = set()
        matches: list[dict] = []
        for pattern, eccn_list in TERM_TO_ECCN:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if not match:
                continue
            matched_term = match.group(0)
            for eccn_code, description in eccn_list:
                if eccn_code in seen:
                    continue
                seen.add(eccn_code)
                matches.append({
                    "eccn": eccn_code,
                    "description": description,
                    "matched_term": matched_term,
                })
        return matches

    @staticmethod
    def _match_keywords(text: str, mapping: dict[str, list[str]]) -> list[str]:
        matches: list[str] = []
        for pattern, file_paths in mapping.items():
            if re.search(pattern, text, flags=re.IGNORECASE):
                matches.extend(file_paths)
        return matches

    def _excerpt_markdown(self, content: str, text: str, max_chars: int) -> str:
        if len(content) <= max_chars:
            return content

        sections = self._split_sections(content)
        if not sections:
            return content[:max_chars].rstrip()

        keywords = self._extract_keywords(text)
        scored_sections: list[tuple[int, int, str]] = []
        for index, section in enumerate(sections):
            section_lower = section.lower()
            score = 1 if index == 0 else 0
            score += sum(1 for keyword in keywords if keyword in section_lower)
            if re.search(r"\b(note|definition|regle|threshold|score|military|dual-use)\b", section_lower):
                score += 1
            scored_sections.append((score, index, section))

        selected: list[tuple[int, str]] = []
        remaining = max_chars

        first_section = sections[0]
        first_excerpt = self._clip_section(first_section, min(len(first_section), max(600, max_chars // 4)))
        selected.append((0, first_excerpt))
        remaining -= len(first_excerpt)

        for _, index, section in sorted(scored_sections[1:], key=lambda item: (-item[0], item[1])):
            if remaining <= 200:
                break
            excerpt = self._clip_section(section, remaining)
            if not excerpt:
                continue
            selected.append((index, excerpt))
            remaining -= len(excerpt)

        if remaining > 400:
            for index, section in enumerate(sections[1:], start=1):
                if any(existing_index == index for existing_index, _ in selected):
                    continue
                excerpt = self._clip_section(section, remaining)
                if not excerpt:
                    continue
                selected.append((index, excerpt))
                remaining -= len(excerpt)
                if remaining <= 200:
                    break

        return "\n\n".join(section for _, section in sorted(selected, key=lambda item: item[0])).rstrip()

    @staticmethod
    def _split_sections(content: str) -> list[str]:
        sections: list[str] = []
        current: list[str] = []
        for line in content.splitlines():
            if re.match(r"^#{1,3}\s", line) and current:
                sections.append("\n".join(current).strip())
                current = [line]
            else:
                current.append(line)
        if current:
            sections.append("\n".join(current).strip())
        return [section for section in sections if section]

    @staticmethod
    def _extract_keywords(text: str) -> list[str]:
        counts = Counter(
            token
            for token in re.findall(r"[a-z0-9][a-z0-9_\-/.]{2,}", text.lower())
            if token not in STOPWORDS
        )
        return [token for token, _ in counts.most_common(15)]

    @staticmethod
    def _clip_section(section: str, max_chars: int) -> str:
        if max_chars <= 0:
            return ""
        if len(section) <= max_chars:
            return section

        clipped = section[:max_chars]
        cut_index = clipped.rfind("\n")
        if cut_index >= max_chars // 2:
            clipped = clipped[:cut_index]
        return clipped.rstrip() + "\n[excerpt truncated for local context budget]"

