export type CountryOption = {
  code: string
  name: string
}

export const COUNTRY_OPTIONS: CountryOption[] = [
  { code: 'AE', name: 'Emirats arabes unis' },
  { code: 'AR', name: 'Argentine' },
  { code: 'AT', name: 'Autriche' },
  { code: 'AU', name: 'Australie' },
  { code: 'BE', name: 'Belgique' },
  { code: 'BR', name: 'Bresil' },
  { code: 'CA', name: 'Canada' },
  { code: 'CH', name: 'Suisse' },
  { code: 'CL', name: 'Chili' },
  { code: 'CN', name: 'Chine' },
  { code: 'CZ', name: 'Republique tcheque' },
  { code: 'DE', name: 'Allemagne' },
  { code: 'DK', name: 'Danemark' },
  { code: 'ES', name: 'Espagne' },
  { code: 'FI', name: 'Finlande' },
  { code: 'FR', name: 'France' },
  { code: 'GB', name: 'Royaume-Uni' },
  { code: 'GR', name: 'Grece' },
  { code: 'HU', name: 'Hongrie' },
  { code: 'IE', name: 'Irlande' },
  { code: 'IL', name: 'Israel' },
  { code: 'IN', name: 'Inde' },
  { code: 'IT', name: 'Italie' },
  { code: 'JP', name: 'Japon' },
  { code: 'KR', name: 'Coree du Sud' },
  { code: 'LU', name: 'Luxembourg' },
  { code: 'MA', name: 'Maroc' },
  { code: 'MX', name: 'Mexique' },
  { code: 'NL', name: 'Pays-Bas' },
  { code: 'NO', name: 'Norvege' },
  { code: 'NZ', name: 'Nouvelle-Zelande' },
  { code: 'PL', name: 'Pologne' },
  { code: 'PT', name: 'Portugal' },
  { code: 'RO', name: 'Roumanie' },
  { code: 'SA', name: 'Arabie saoudite' },
  { code: 'SE', name: 'Suede' },
  { code: 'SG', name: 'Singapour' },
  { code: 'TR', name: 'Turquie' },
  { code: 'UA', name: 'Ukraine' },
  { code: 'US', name: 'Etats-Unis' },
]

function normalizeCountryToken(value: string) {
  return value
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/\s+/g, ' ')
    .trim()
    .toLowerCase()
}

export function formatCountryLabel(country: CountryOption) {
  return `${country.name} (${country.code})`
}

export function getCountryLabel(code: string | null | undefined) {
  if (!code) return ''
  const country = COUNTRY_OPTIONS.find((item) => item.code === code.toUpperCase())
  return country ? formatCountryLabel(country) : code.toUpperCase()
}

export function parseCountryInput(value: string): CountryOption | null {
  const normalized = normalizeCountryToken(value)
  if (!normalized) return null

  return (
    COUNTRY_OPTIONS.find((country) => {
      const code = normalizeCountryToken(country.code)
      const name = normalizeCountryToken(country.name)
      const label = normalizeCountryToken(formatCountryLabel(country))
      return normalized === code || normalized === name || normalized === label
    }) ?? null
  )
}
