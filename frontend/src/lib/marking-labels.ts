import type { SupportedLanguage } from './api'

const MARKING_CODE_PATTERN =
  /\b(?:EC_Not_Technical|EC_Review_Required|[A-Z]{2}_EC_[A-Za-z0-9_.]+|US_[A-Za-z0-9_.]+)\b/g

function humanizeSuffix(value: string): string {
  return value
    .split(/[_\s]+/)
    .filter(Boolean)
    .map((part) => (/^[A-Z0-9.]+$/.test(part) ? part : `${part.slice(0, 1).toUpperCase()}${part.slice(1).toLowerCase()}`))
    .join(' ')
}

function getCountryMarkingParts(code: string): { countryCode: string; suffix: string } | null {
  const match = code.match(/^([A-Z]{2})_EC_(.+)$/)
  if (!match) return null
  return { countryCode: match[1], suffix: match[2] }
}

export function getMarkingLabel(
  code: string | null | undefined,
  language: SupportedLanguage = 'en',
): string {
  if (!code) return '-'

  const predefinedLabels =
    language === 'fr'
      ? {
          EC_Not_Technical: 'Document non technique',
          EC_Review_Required: 'Classification export a confirmer',
          EU_EC_Technical_Not_Controlled: 'Document technique non controle (reglement UE double usage)',
          US_EAR99: 'Article commercial non controle (EAR99)',
          US_REVIEW_REQUIRED: 'Classification export US a confirmer',
        }
      : {
          EC_Not_Technical: 'Non-technical document',
          EC_Review_Required: 'Export classification to be confirmed',
          EU_EC_Technical_Not_Controlled: 'Technical document not controlled under EU dual-use rules',
          US_EAR99: 'Commercial item not controlled (EAR99)',
          US_REVIEW_REQUIRED: 'US export classification to be confirmed',
        }

  if (predefinedLabels[code as keyof typeof predefinedLabels]) {
    return predefinedLabels[code as keyof typeof predefinedLabels]
  }

  const countryMarking = getCountryMarkingParts(code)
  if (countryMarking) {
    if (countryMarking.suffix.startsWith('AMA') || countryMarking.suffix.startsWith('ML')) {
      return language === 'fr'
        ? `Controle export ${countryMarking.countryCode} - rubrique ${countryMarking.suffix}`
        : `${countryMarking.countryCode} export control - entry ${countryMarking.suffix}`
    }
    if (countryMarking.suffix === 'Technical_Not_Controlled') {
      return language === 'fr'
        ? `Document technique non controle (${countryMarking.countryCode})`
        : `Technical document not controlled (${countryMarking.countryCode})`
    }
    return language === 'fr'
      ? `Controle export ${countryMarking.countryCode} - rubrique ${humanizeSuffix(countryMarking.suffix)}`
      : `${countryMarking.countryCode} export control - entry ${humanizeSuffix(countryMarking.suffix)}`
  }

  if (code.startsWith('US_ITAR_')) {
    return language === 'fr'
      ? `ITAR Etats-Unis - rubrique ${humanizeSuffix(code.replace('US_ITAR_', ''))}`
      : `US ITAR - entry ${humanizeSuffix(code.replace('US_ITAR_', ''))}`
  }
  if (code.startsWith('US_EAR_')) {
    return language === 'fr'
      ? `EAR Etats-Unis - rubrique ${humanizeSuffix(code.replace('US_EAR_', ''))}`
      : `US EAR - entry ${humanizeSuffix(code.replace('US_EAR_', ''))}`
  }
  if (code.startsWith('US_')) {
    return language === 'fr'
      ? `Controle export Etats-Unis - ${humanizeSuffix(code.replace('US_', ''))}`
      : `US export control - ${humanizeSuffix(code.replace('US_', ''))}`
  }

  return humanizeSuffix(code)
}

export function replaceMarkingCodesInText(
  text: string | null | undefined,
  language: SupportedLanguage = 'en',
): string {
  if (!text) return ''
  return text.replace(MARKING_CODE_PATTERN, (match) => getMarkingLabel(match, language))
}

export function getLaneLabel(lane: string | null | undefined, language: SupportedLanguage = 'en'): string {
  if (!lane) return '-'

  const labels =
    language === 'fr'
      ? {
          fr_eu: 'France / UE',
          us: 'US ITAR / EAR',
        }
      : {
          fr_eu: 'France / EU',
          us: 'US ITAR / EAR',
        }

  return labels[lane as keyof typeof labels] ?? lane
}

const CITATION_TITLES_EN: Record<string, string> = {
  'definitions/technical-data.md': 'Technical data definitions',
  'heuristics/technical-indicators.md': 'Technical indicators',
  'heuristics/false-positives.md': 'False positive detection',
  'heuristics/document-types.md': 'Document type taxonomy',
  'heuristics/classification-process.md': 'Classification process',
  'definitions/military-use.md': 'Military-use definitions',
  'definitions/software.md': 'Software definitions',
  'definitions/general-notes.md': 'General notes',
  'frml/overview.md': 'French military list - Overview',
  'frml/definitions-ml.md': 'French military list - Definitions',
  'eu-dual-use/overview.md': 'EU dual-use regulation - Overview',
  'eu-dual-use/definitions-dual-use.md': 'EU dual-use regulation - Definitions',
  'eu-dual-use/annexes.md': 'EU dual-use regulation - Annexes',
  'heuristics/lifecycle-phases.md': 'Industrial lifecycle phases',
  'heuristics/military-indicators-detailed.md': 'Detailed military indicators',
  'frml/ML22.md': 'French military list - ML22 (Technology)',
}

const CITATION_TITLES_FR: Record<string, string> = {
  'definitions/technical-data.md': 'Definitions des donnees techniques',
  'heuristics/technical-indicators.md': 'Indicateurs techniques',
  'heuristics/false-positives.md': 'Detection des faux positifs',
  'heuristics/document-types.md': 'Taxonomie des types de documents',
  'heuristics/classification-process.md': 'Processus de classification',
  'definitions/military-use.md': 'Definitions de l usage militaire',
  'definitions/software.md': 'Definitions logiciel',
  'definitions/general-notes.md': 'Notes generales',
  'frml/overview.md': 'Liste militaire francaise - Vue d ensemble',
  'frml/definitions-ml.md': 'Liste militaire francaise - Definitions',
  'eu-dual-use/overview.md': 'Reglement UE double usage - Vue d ensemble',
  'eu-dual-use/definitions-dual-use.md': 'Reglement UE double usage - Definitions',
  'eu-dual-use/annexes.md': 'Reglement UE double usage - Annexes',
  'heuristics/lifecycle-phases.md': 'Phases du cycle de vie industriel',
  'heuristics/military-indicators-detailed.md': 'Indicateurs militaires detailles',
  'frml/ML22.md': 'Liste militaire FR - ML22 (Technologie)',
}

export function getCitationTitle(source: string, language: SupportedLanguage = 'en'): string {
  const titles = language === 'fr' ? CITATION_TITLES_FR : CITATION_TITLES_EN
  if (titles[source]) return titles[source]

  const frmlMatch = source.match(/^frml\/ML(\d+)\.md$/)
  if (frmlMatch) {
    return language === 'fr'
      ? `Liste militaire FR - ML${frmlMatch[1]}`
      : `French military list - ML${frmlMatch[1]}`
  }

  const amaMatch = source.match(/^frml\/AMA(\d+)\.md$/)
  if (amaMatch) {
    return language === 'fr'
      ? `Liste militaire FR - AMA${amaMatch[1]}`
      : `French military list - AMA${amaMatch[1]}`
  }

  const euCatMatch = source.match(/^eu-dual-use\/cat(\d+)/)
  if (euCatMatch) {
    return language === 'fr'
      ? `Double usage UE - Categorie ${euCatMatch[1]}`
      : `EU dual-use - Category ${euCatMatch[1]}`
  }

  return source.replace(/\.md$/, '').replace(/[/-]/g, ' ')
}

const STEP_LABELS_EN: Record<string, string> = {
  step2: 'Technical review',
  step4: 'Item identification',
  step5: 'Military classification',
  step7: 'Dual-use classification',
  step8: 'Technology control',
  step_us: 'US classification',
  step_a: 'Content scan',
  step_b: 'Identification of the analyzed item',
  step_c: 'Military / ITAR analysis',
  step_c_itar: 'ITAR assessment',
  step_d: 'ML22 technical data',
  step_e: 'Dual-use search',
  step_e_screening: 'EAR screening',
  step_e_detailed: 'EAR detailed analysis',
  step_f: 'Nature E technical data',
}

const STEP_LABELS_FR: Record<string, string> = {
  step2: 'Evaluation technique',
  step4: "Identification de l'article",
  step5: 'Classification militaire',
  step7: 'Classification double usage',
  step8: 'Controle technologique',
  step_us: 'Classification US',
  step_a: 'Scan du contenu',
  step_b: "Identification de l'element analyse",
  step_c: 'Analyse militaire / ITAR',
  step_c_itar: 'Evaluation ITAR',
  step_d: 'Donnee technique ML22',
  step_e: 'Recherche double usage',
  step_e_screening: 'Screening EAR',
  step_e_detailed: 'Analyse EAR detaillee',
  step_f: 'Donnee technique nature E',
}

export function getStepLabel(stepKey: string, language: SupportedLanguage = 'en'): string {
  const labels = language === 'fr' ? STEP_LABELS_FR : STEP_LABELS_EN
  return labels[stepKey] ?? stepKey
}
