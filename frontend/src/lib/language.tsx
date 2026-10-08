import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'

import {
  fetchLanguageSettings,
  updateLanguageSettings,
  type LanguageSettings,
  type SupportedLanguage,
} from './api'

const DEFAULT_LANGUAGE_SETTINGS: LanguageSettings = {
  ui_language: 'en',
  analysis_language: 'en',
  rationale_language: 'en',
}

type LanguageContextValue = {
  settings: LanguageSettings
  uiLanguage: SupportedLanguage
  loading: boolean
  saveLanguageSettings: (nextSettings: LanguageSettings) => Promise<LanguageSettings>
}

const LanguageContext = createContext<LanguageContextValue | null>(null)

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [settings, setSettings] = useState<LanguageSettings>(DEFAULT_LANGUAGE_SETTINGS)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false

    async function loadLanguageSettings() {
      try {
        const nextSettings = await fetchLanguageSettings()
        if (!cancelled) {
          setSettings(nextSettings)
        }
      } catch {
        if (!cancelled) {
          setSettings(DEFAULT_LANGUAGE_SETTINGS)
        }
      } finally {
        if (!cancelled) {
          setLoading(false)
        }
      }
    }

    void loadLanguageSettings()

    return () => {
      cancelled = true
    }
  }, [])

  async function saveLanguageSettings(nextSettings: LanguageSettings) {
    const savedSettings = await updateLanguageSettings(nextSettings)
    setSettings(savedSettings)
    return savedSettings
  }

  const value = useMemo<LanguageContextValue>(
    () => ({
      settings,
      uiLanguage: settings.ui_language,
      loading,
      saveLanguageSettings,
    }),
    [loading, settings, saveLanguageSettings],
  )

  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>
}

export function useLanguage() {
  const context = useContext(LanguageContext)
  if (!context) {
    throw new Error('useLanguage must be used within a LanguageProvider')
  }
  return context
}

export function getLanguageLabel(language: SupportedLanguage, uiLanguage: SupportedLanguage) {
  if (language === 'en') {
    return uiLanguage === 'fr' ? 'Anglais' : 'English'
  }
  return uiLanguage === 'fr' ? 'Francais' : 'French'
}
