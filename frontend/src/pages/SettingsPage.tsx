import { useEffect, useMemo, useState } from 'react'

import { Badge } from '../components/ui/badge'
import { Button } from '../components/ui/button'
import { Spinner } from '../components/ui/spinner'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/select'
import {
  fetchLlmSettings,
  updateLlmSettings,
  type LLMRuntimeProfile,
  type LLMRuntimeSettings,
  type LanguageSettings,
  type SupportedLanguage,
} from '../lib/api'
import { getLanguageLabel, useLanguage } from '../lib/language'

const JURISDICTION_STORAGE_KEY = 'veltar.runtime.jurisdiction'

const JURISDICTIONS = [
  {
    id: 'none',
    label: { en: 'None / Undefined', fr: 'Aucune / Non definie' },
    summary: { en: 'No regulatory frame selected', fr: 'Cadre non selectionne' },
    scope: { en: 'To be confirmed', fr: 'A confirmer' },
    reference: { en: '-', fr: '-' },
    sensitivity: { en: 'Variable', fr: 'Variable' },
  },
  {
    id: 'eu',
    label: { en: 'European Union', fr: 'Union europeenne' },
    summary: { en: 'EU dual-use goods - documentary review required', fr: 'UE - biens a double usage - verification documentaire requise' },
    scope: { en: 'European Union', fr: 'Union europeenne' },
    reference: { en: 'EU dual-use', fr: 'Double usage UE' },
    sensitivity: { en: 'Standard', fr: 'Standard' },
  },
  {
    id: 'fr',
    label: { en: 'France', fr: 'France' },
    summary: { en: 'France defence and dual-use - reinforced review', fr: 'France - defense et double usage - verification renforcee' },
    scope: { en: 'France', fr: 'France' },
    reference: { en: 'FR military list + EU', fr: 'Liste militaire FR + UE' },
    sensitivity: { en: 'High', fr: 'Elevee' },
  },
  {
    id: 'de',
    label: { en: 'Germany', fr: 'Allemagne' },
    summary: { en: 'Germany defence and dual-use - reinforced review', fr: 'Allemagne - defense et double usage - verification renforcee' },
    scope: { en: 'Germany', fr: 'Allemagne' },
    reference: { en: 'DE / EU', fr: 'DE / UE' },
    sensitivity: { en: 'High', fr: 'Elevee' },
  },
  {
    id: 'us',
    label: { en: 'United States', fr: 'Etats-Unis' },
    summary: { en: 'US EAR / ITAR - strict review', fr: 'US - EAR / ITAR - verification stricte' },
    scope: { en: 'United States', fr: 'Etats-Unis' },
    reference: { en: 'EAR / ITAR', fr: 'EAR / ITAR' },
    sensitivity: { en: 'High', fr: 'Elevee' },
  },
  {
    id: 'uk',
    label: { en: 'United Kingdom', fr: 'Royaume-Uni' },
    summary: { en: 'UK defence and dual-use - reinforced review', fr: 'UK - defense et dual-use - verification renforcee' },
    scope: { en: 'United Kingdom', fr: 'Royaume-Uni' },
    reference: { en: 'UK Strategic Export Controls', fr: 'UK Strategic Export Controls' },
    sensitivity: { en: 'High', fr: 'Elevee' },
  },
  {
    id: 'ch',
    label: { en: 'Switzerland', fr: 'Suisse' },
    summary: { en: 'Switzerland sensitive goods - documentary review required', fr: 'Suisse - biens sensibles - verification documentaire requise' },
    scope: { en: 'Switzerland', fr: 'Suisse' },
    reference: { en: 'Goods control', fr: 'Controle des biens' },
    sensitivity: { en: 'Moderate', fr: 'Moderee' },
  },
] as const

function getCopy(uiLanguage: SupportedLanguage) {
  if (uiLanguage === 'fr') {
    return {
      save: 'Enregistrer',
      retry: 'Recharger la page',
      languageSectionTitle: 'Langue et sorties',
      languageSectionCopy: "Cette section pilote la langue de l'interface, des analyses generees et du rationnel final.",
      interfaceLanguage: "Langue de l'outil",
      analysisLanguage: "Langue de l'analyse",
      rationaleLanguage: 'Langue du rationnel',
      saveLanguages: 'Appliquer les langues',
      savingLanguages: 'Application...',
      languageSaved: 'Reglages actifs',
      analysisModelTitle: "Modele d'analyse",
      analysisModelCopy: 'Selection du modele OpenRouter utilise par le projet pour lancer les classifications.',
      loadingProfiles: 'Chargement des profils LLM',
      selectModel: 'Selectionner un modele',
      applyingModel: 'Application...',
      applyModel: 'Appliquer le modele',
      activeModel: 'Modele actif',
      pendingChange: 'Modification en attente',
      apiConfigured: 'API configuree',
      apiMissing: 'API non configuree',
      model: 'Modele',
      endpoint: 'Endpoint',
      timeout: 'Timeout',
      noModelProfile: 'Aucun profil modele disponible.',
      exportJurisdictionTitle: "Juridiction d'export",
      exportJurisdictionCopy: "Ce choix cadre l'espace de travail et reste stocke localement dans l'interface.",
      selectJurisdiction: 'Selectionner une juridiction',
      activeJurisdiction: 'Juridiction active',
      scope: 'Portee',
      reference: 'Referentiel',
      sensitivity: 'Sensibilite',
      loadingImpossible: 'Chargement impossible.',
    }
  }

  return {
    save: 'Save',
    retry: 'Reload page',
    languageSectionTitle: 'Language and outputs',
    languageSectionCopy: 'This section controls the UI language, generated analysis language, and final rationale language.',
    interfaceLanguage: 'Tool language',
    analysisLanguage: 'Analysis language',
    rationaleLanguage: 'Rationale language',
    saveLanguages: 'Apply languages',
    savingLanguages: 'Applying...',
    languageSaved: 'Active settings',
    analysisModelTitle: 'Analysis model',
    analysisModelCopy: 'Select the OpenRouter model used by the project to run classifications.',
    loadingProfiles: 'Loading LLM profiles',
    selectModel: 'Select a model',
    applyingModel: 'Applying...',
    applyModel: 'Apply model',
    activeModel: 'Active model',
    pendingChange: 'Pending change',
    apiConfigured: 'API configured',
    apiMissing: 'API not configured',
    model: 'Model',
    endpoint: 'Endpoint',
    timeout: 'Timeout',
    noModelProfile: 'No model profile available.',
    exportJurisdictionTitle: 'Export jurisdiction',
    exportJurisdictionCopy: 'This choice frames the workspace and remains stored locally in the interface.',
    selectJurisdiction: 'Select a jurisdiction',
    activeJurisdiction: 'Active jurisdiction',
    scope: 'Scope',
    reference: 'Reference',
    sensitivity: 'Sensitivity',
    loadingImpossible: 'Unable to load settings.',
  }
}

function getProjectModelProfiles(settings: LLMRuntimeSettings | null): LLMRuntimeProfile[] {
  if (!settings) {
    return []
  }

  const openRouterProfiles = settings.available_profiles.filter((profile) => profile.id.startsWith('openrouter_'))
  const hasActiveProfile = openRouterProfiles.some((profile) => profile.id === settings.active_profile_id)
  if (hasActiveProfile || settings.active_profile_id.startsWith('openrouter_')) {
    return openRouterProfiles
  }
  return [settings.active_profile, ...openRouterProfiles]
}

function getLlmErrorMessage(error: unknown, uiLanguage: SupportedLanguage): string {
  if (typeof error === 'object' && error && 'response' in error) {
    const response = error.response
    if (typeof response === 'object' && response && 'data' in response) {
      const data = response.data
      if (typeof data === 'object' && data && 'detail' in data && typeof data.detail === 'string') {
        return data.detail
      }
    }
  }

  if (error instanceof Error && error.message) {
    return error.message
  }

  return getCopy(uiLanguage).loadingImpossible
}

export function SettingsPage() {
  const { settings: languageSettings, uiLanguage, saveLanguageSettings } = useLanguage()
  const copy = getCopy(uiLanguage)

  const [selectedJurisdictionId, setSelectedJurisdictionId] = useState('none')
  const [llmSettings, setLlmSettings] = useState<LLMRuntimeSettings | null>(null)
  const [selectedProfileId, setSelectedProfileId] = useState('')
  const [llmLoading, setLlmLoading] = useState(true)
  const [llmSaving, setLlmSaving] = useState(false)
  const [llmError, setLlmError] = useState<string | null>(null)

  const [languageDraft, setLanguageDraft] = useState<LanguageSettings>(languageSettings)
  const [languageSaving, setLanguageSaving] = useState(false)
  const [languageError, setLanguageError] = useState<string | null>(null)

  useEffect(() => {
    setLanguageDraft(languageSettings)
  }, [languageSettings])

  useEffect(() => {
    const storedValue = window.localStorage.getItem(JURISDICTION_STORAGE_KEY)
    if (storedValue && JURISDICTIONS.some((option) => option.id === storedValue)) {
      setSelectedJurisdictionId(storedValue)
    }
  }, [])

  useEffect(() => {
    window.localStorage.setItem(JURISDICTION_STORAGE_KEY, selectedJurisdictionId)
  }, [selectedJurisdictionId])

  useEffect(() => {
    let cancelled = false

    async function loadLlmSettings() {
      setLlmLoading(true)
      setLlmError(null)

      try {
        const nextSettings = await fetchLlmSettings()
        if (cancelled) {
          return
        }
        setLlmSettings(nextSettings)
        setSelectedProfileId(nextSettings.active_profile_id)
      } catch (error) {
        if (!cancelled) {
          setLlmError(getLlmErrorMessage(error, uiLanguage))
        }
      } finally {
        if (!cancelled) {
          setLlmLoading(false)
        }
      }
    }

    void loadLlmSettings()

    return () => {
      cancelled = true
    }
  }, [uiLanguage])

  const selectedJurisdiction = useMemo(
    () => JURISDICTIONS.find((option) => option.id === selectedJurisdictionId) ?? JURISDICTIONS[0],
    [selectedJurisdictionId],
  )

  const projectModelProfiles = useMemo(() => getProjectModelProfiles(llmSettings), [llmSettings])

  const selectedProfile = useMemo(
    () =>
      projectModelProfiles.find((profile) => profile.id === selectedProfileId) ??
      llmSettings?.active_profile ??
      null,
    [llmSettings, projectModelProfiles, selectedProfileId],
  )

  const canSaveProfile =
    !!llmSettings && !!selectedProfileId && selectedProfileId !== llmSettings.active_profile_id && !llmSaving

  const canSaveLanguageSettings =
    !languageSaving &&
    (languageDraft.ui_language !== languageSettings.ui_language ||
      languageDraft.analysis_language !== languageSettings.analysis_language ||
      languageDraft.rationale_language !== languageSettings.rationale_language)

  async function handleSaveProfile() {
    if (!selectedProfileId) {
      return
    }

    setLlmSaving(true)
    setLlmError(null)

    try {
      const nextSettings = await updateLlmSettings(selectedProfileId)
      setLlmSettings(nextSettings)
      setSelectedProfileId(nextSettings.active_profile_id)
    } catch (error) {
      setLlmError(getLlmErrorMessage(error, uiLanguage))
    } finally {
      setLlmSaving(false)
    }
  }

  async function handleSaveLanguages() {
    setLanguageSaving(true)
    setLanguageError(null)

    try {
      await saveLanguageSettings(languageDraft)
      const nextSettings = await fetchLlmSettings()
      setLlmSettings(nextSettings)
      setSelectedProfileId(nextSettings.active_profile_id)
    } catch (error) {
      setLanguageError(getLlmErrorMessage(error, uiLanguage))
    } finally {
      setLanguageSaving(false)
    }
  }

  return (
    <div className="max-w-4xl space-y-6">
      <section className="app-panel overflow-hidden">
        <div className="panel-header">
          <div>
            <h2 className="section-title">{copy.languageSectionTitle}</h2>
            <p className="section-copy mt-1">{copy.languageSectionCopy}</p>
          </div>
          <Badge variant="outline">{copy.languageSaved}</Badge>
        </div>

        <div className="panel-body space-y-4">
          <div className="grid gap-4 md:grid-cols-3">
            <div className="space-y-2">
              <p className="metric-label">{copy.interfaceLanguage}</p>
              <Select
                value={languageDraft.ui_language}
                onValueChange={(value) =>
                  setLanguageDraft((current) => ({ ...current, ui_language: value as SupportedLanguage }))
                }
              >
                <SelectTrigger className="h-11 rounded-2xl">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="en">{getLanguageLabel('en', uiLanguage)}</SelectItem>
                  <SelectItem value="fr">{getLanguageLabel('fr', uiLanguage)}</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <p className="metric-label">{copy.analysisLanguage}</p>
              <Select
                value={languageDraft.analysis_language}
                onValueChange={(value) =>
                  setLanguageDraft((current) => ({ ...current, analysis_language: value as SupportedLanguage }))
                }
              >
                <SelectTrigger className="h-11 rounded-2xl">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="en">{getLanguageLabel('en', uiLanguage)}</SelectItem>
                  <SelectItem value="fr">{getLanguageLabel('fr', uiLanguage)}</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <p className="metric-label">{copy.rationaleLanguage}</p>
              <Select
                value={languageDraft.rationale_language}
                onValueChange={(value) =>
                  setLanguageDraft((current) => ({ ...current, rationale_language: value as SupportedLanguage }))
                }
              >
                <SelectTrigger className="h-11 rounded-2xl">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="en">{getLanguageLabel('en', uiLanguage)}</SelectItem>
                  <SelectItem value="fr">{getLanguageLabel('fr', uiLanguage)}</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          {languageError ? <p className="text-sm text-destructive">{languageError}</p> : null}

          <Button size="lg" onClick={() => void handleSaveLanguages()} disabled={!canSaveLanguageSettings}>
            {languageSaving ? <Spinner className="h-4 w-4" /> : null}
            {languageSaving ? copy.savingLanguages : copy.saveLanguages}
          </Button>
        </div>
      </section>

      <section className="app-panel overflow-hidden">
        <div className="panel-header">
          <div>
            <h2 className="section-title">{copy.analysisModelTitle}</h2>
            <p className="section-copy mt-1">{copy.analysisModelCopy}</p>
          </div>
        </div>

        <div className="panel-body space-y-4">
          {llmLoading ? (
            <div className="flex min-h-[110px] items-center gap-3 text-sm text-muted-foreground">
              <Spinner />
              {copy.loadingProfiles}
            </div>
          ) : llmError ? (
            <div className="space-y-3 rounded-[20px] border border-destructive/25 bg-destructive/5 px-4 py-4">
              <p className="text-sm text-destructive">{llmError}</p>
              <Button size="sm" variant="outline" onClick={() => window.location.reload()}>
                {copy.retry}
              </Button>
            </div>
          ) : llmSettings && selectedProfile ? (
            <>
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
                <Select value={selectedProfileId} onValueChange={setSelectedProfileId}>
                  <SelectTrigger className="h-11 max-w-md rounded-2xl">
                    <SelectValue placeholder={copy.selectModel} />
                  </SelectTrigger>
                  <SelectContent>
                    {projectModelProfiles.map((profile) => (
                      <SelectItem key={profile.id} value={profile.id}>
                        {profile.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>

                <Button size="lg" onClick={() => void handleSaveProfile()} disabled={!canSaveProfile}>
                  {llmSaving ? <Spinner className="h-4 w-4" /> : null}
                  {llmSaving ? copy.applyingModel : copy.applyModel}
                </Button>
              </div>

              <div className="app-panel-muted px-4 py-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div className="space-y-1">
                    <p className="text-sm font-medium text-foreground">{selectedProfile.label}</p>
                    <p className="text-sm text-muted-foreground">{selectedProfile.description}</p>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    {llmSettings.active_profile_id === selectedProfile.id ? (
                      <Badge variant="outline">{copy.activeModel}</Badge>
                    ) : (
                      <Badge variant="info">{copy.pendingChange}</Badge>
                    )}
                    <Badge variant={selectedProfile.api_key_configured ? 'outline' : 'destructive'}>
                      {selectedProfile.api_key_configured ? copy.apiConfigured : copy.apiMissing}
                    </Badge>
                  </div>
                </div>

                <div className="mt-4 grid gap-4 sm:grid-cols-3">
                  <div className="space-y-1">
                    <p className="metric-label">{copy.model}</p>
                    <p className="text-sm text-foreground">{selectedProfile.model_name}</p>
                  </div>
                  <div className="space-y-1">
                    <p className="metric-label">{copy.endpoint}</p>
                    <p className="truncate text-sm text-foreground">{selectedProfile.base_url}</p>
                  </div>
                  <div className="space-y-1">
                    <p className="metric-label">{copy.timeout}</p>
                    <p className="text-sm text-foreground">{selectedProfile.timeout_seconds}s</p>
                  </div>
                </div>
              </div>
            </>
          ) : (
            <p className="text-sm text-muted-foreground">{copy.noModelProfile}</p>
          )}
        </div>
      </section>

      <section className="app-panel overflow-hidden">
        <div className="panel-header">
          <h2 className="section-title">{copy.exportJurisdictionTitle}</h2>
        </div>

        <div className="panel-body space-y-4">
          <p className="section-copy">{copy.exportJurisdictionCopy}</p>

          <Select value={selectedJurisdictionId} onValueChange={setSelectedJurisdictionId}>
            <SelectTrigger className="h-11 max-w-md rounded-2xl">
              <SelectValue placeholder={copy.selectJurisdiction} />
            </SelectTrigger>
            <SelectContent>
              {JURISDICTIONS.map((option) => (
                <SelectItem key={option.id} value={option.id}>
                  {option.label[uiLanguage]}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          <div className="app-panel-muted px-4 py-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="space-y-1">
                <p className="text-sm font-medium text-foreground">{selectedJurisdiction.label[uiLanguage]}</p>
                <p className="text-sm text-muted-foreground">{selectedJurisdiction.summary[uiLanguage]}</p>
              </div>
              <Badge variant="outline">{copy.activeJurisdiction}</Badge>
            </div>

            <div className="mt-4 grid gap-4 sm:grid-cols-3">
              <div className="space-y-1">
                <p className="metric-label">{copy.scope}</p>
                <p className="text-sm text-foreground">{selectedJurisdiction.scope[uiLanguage]}</p>
              </div>
              <div className="space-y-1">
                <p className="metric-label">{copy.reference}</p>
                <p className="text-sm text-foreground">{selectedJurisdiction.reference[uiLanguage]}</p>
              </div>
              <div className="space-y-1">
                <p className="metric-label">{copy.sensitivity}</p>
                <p className="text-sm text-foreground">{selectedJurisdiction.sensitivity[uiLanguage]}</p>
              </div>
            </div>
          </div>
        </div>
      </section>
    </div>
  )
}
