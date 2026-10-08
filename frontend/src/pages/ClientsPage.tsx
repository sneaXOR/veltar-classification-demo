import { useEffect, useState, type KeyboardEvent } from 'react'
import { Building2, Pencil, Plus, Save, Trash2, X } from 'lucide-react'

import {
  createClient,
  deleteClient,
  fetchClients,
  updateClient,
  type ClientProfile,
  type ClientProfileCreate,
} from '../lib/api'
import { Badge } from '../components/ui/badge'
import { Button } from '../components/ui/button'
import { EmptyState } from '../components/ui/empty-state'
import { Input } from '../components/ui/input'
import { COUNTRY_OPTIONS, formatCountryLabel, getCountryLabel, parseCountryInput } from '../lib/countries'
import { useLanguage } from '../lib/language'
import { cn } from '../lib/utils'

const EMPTY_FORM: ClientProfileCreate = {
  name: '',
  country: '',
  activity_description: '',
  product_families: [],
  product_characteristics: {},
  program_names: [],
  naming_conventions: {},
  classification_history: [],
}

function TagInput({
  value,
  onChange,
  placeholder,
}: {
  value: string[]
  onChange: (value: string[]) => void
  placeholder?: string
}) {
  const [input, setInput] = useState('')

  function handleKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if ((event.key === 'Enter' || event.key === ',') && input.trim()) {
      event.preventDefault()
      if (!value.includes(input.trim())) onChange([...value, input.trim()])
      setInput('')
    }
    if (event.key === 'Backspace' && !input && value.length) onChange(value.slice(0, -1))
  }

  return (
    <div className="flex flex-wrap items-center gap-2 rounded-[20px] border border-border/80 bg-surface px-3 py-3">
      {value.map((tag) => (
        <span
          key={tag}
          className="inline-flex items-center gap-1 rounded-full border border-border/70 bg-secondary/70 px-2 py-1 font-mono text-[10px] uppercase tracking-[0.14em]"
        >
          {tag}
          <button type="button" onClick={() => onChange(value.filter((item) => item !== tag))}>
            <X className="h-3 w-3" />
          </button>
        </span>
      ))}
      <input
        className="min-w-[120px] flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground"
        value={input}
        onChange={(event) => setInput(event.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={value.length ? '' : placeholder}
      />
    </div>
  )
}

function getCopy(uiLanguage: 'en' | 'fr') {
  if (uiLanguage === 'fr') {
    return {
      requiredFields: 'Nom et pays obligatoires.',
      saveImpossible: 'Sauvegarde impossible.',
      clients: 'Clients',
      noClient: 'Aucun client',
      noClientDescription: 'Creer un profil pour ajouter du contexte.',
      newClient: 'Nouveau client',
      edit: 'Edition',
      selection: 'Selection',
      cancel: 'Annuler',
      save: 'Enregistrer',
      name: 'Nom',
      country: 'Pays',
      searchCountry: 'Rechercher un pays',
      activity: 'Activite',
      families: 'Familles',
      programs: 'Programmes',
      add: 'Ajouter',
      delete: 'Supprimer',
      noSelection: 'Aucune selection',
      noSelectionDescription: 'Choisir un client ou en creer un nouveau.',
    }
  }

  return {
    requiredFields: 'Name and country are required.',
    saveImpossible: 'Unable to save client.',
    clients: 'Clients',
    noClient: 'No clients',
    noClientDescription: 'Create a profile to add business context.',
    newClient: 'New client',
    edit: 'Edit',
    selection: 'Selection',
    cancel: 'Cancel',
    save: 'Save',
    name: 'Name',
    country: 'Country',
    searchCountry: 'Search a country',
    activity: 'Activity',
    families: 'Families',
    programs: 'Programs',
    add: 'Add',
    delete: 'Delete',
    noSelection: 'Nothing selected',
    noSelectionDescription: 'Choose a client or create a new one.',
  }
}

export function ClientsPage() {
  const { uiLanguage } = useLanguage()
  const copy = getCopy(uiLanguage)
  const [clients, setClients] = useState<ClientProfile[]>([])
  const [editing, setEditing] = useState<string | null>(null)
  const [form, setForm] = useState<ClientProfileCreate>(EMPTY_FORM)
  const [countryInput, setCountryInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function refresh() {
    try {
      setClients(await fetchClients())
    } catch {
      /* ignore */
    }
  }

  useEffect(() => {
    void refresh()
  }, [])

  function startCreate() {
    setEditing('new')
    setForm(EMPTY_FORM)
    setCountryInput('')
    setError(null)
  }

  function startEdit(client: ClientProfile) {
    setEditing(client.id)
    setForm({
      name: client.name,
      country: client.country,
      activity_description: client.activity_description ?? '',
      product_families: client.product_families,
      product_characteristics: client.product_characteristics,
      program_names: client.program_names,
      naming_conventions: client.naming_conventions,
      classification_history: client.classification_history,
    })
    setCountryInput(getCountryLabel(client.country))
    setError(null)
  }

  function cancelEdit() {
    setEditing(null)
    setForm(EMPTY_FORM)
    setCountryInput('')
    setError(null)
  }

  async function handleSave() {
    const selectedCountry = parseCountryInput(countryInput) ?? (form.country.trim() ? parseCountryInput(form.country) : null)
    if (!form.name.trim() || !selectedCountry) {
      setError(copy.requiredFields)
      return
    }
    setBusy(true)
    setError(null)
    try {
      const payload = { ...form, country: selectedCountry.code }
      if (editing === 'new') await createClient(payload)
      else if (editing) await updateClient(editing, payload)
      await refresh()
      cancelEdit()
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : copy.saveImpossible)
    } finally {
      setBusy(false)
    }
  }

  async function handleDelete(clientId: string) {
    setBusy(true)
    try {
      await deleteClient(clientId)
      if (editing === clientId) cancelEdit()
      await refresh()
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="grid gap-6 xl:grid-cols-[320px_minmax(0,1fr)]">
      <aside className="space-y-4">
        <section className="app-panel overflow-hidden">
          <div className="panel-header">
            <h2 className="section-title">{copy.clients}</h2>
            <Button size="icon" onClick={startCreate} disabled={busy}>
              <Plus className="h-4 w-4" />
            </Button>
          </div>

          <div className="panel-body space-y-2">
            {clients.length ? (
              clients.map((client) => (
                <button
                  key={client.id}
                  type="button"
                  onClick={() => startEdit(client)}
                  className={cn(
                    'w-full rounded-[18px] border px-4 py-3 text-left transition-colors',
                    editing === client.id
                      ? 'border-primary bg-primary/6'
                      : 'border-border/70 bg-surface hover:bg-secondary/45',
                  )}
                >
                  <div className="flex items-center justify-between gap-3">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium">{client.name}</p>
                    </div>
                    <Badge variant="outline">{client.country}</Badge>
                  </div>
                </button>
              ))
            ) : (
              <EmptyState
                icon={Building2}
                title={copy.noClient}
                description={copy.noClientDescription}
              />
            )}
          </div>
        </section>
      </aside>

      <section className="app-panel overflow-hidden">
        <div className="panel-header">
          <h2 className="section-title">
            {editing === 'new' ? copy.newClient : editing ? copy.edit : copy.selection}
          </h2>
          {editing ? (
            <div className="flex gap-2">
              <Button variant="outline" onClick={cancelEdit} disabled={busy}>
                {copy.cancel}
              </Button>
              <Button onClick={() => void handleSave()} disabled={busy}>
                <Save className="h-4 w-4" />
                {copy.save}
              </Button>
            </div>
          ) : null}
        </div>

        <div className="panel-body">
          {editing ? (
            <div className="space-y-5">
              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-2">
                  <p className="metric-label">{copy.name}</p>
                  <Input
                    value={form.name}
                    onChange={(event) => setForm({ ...form, name: event.target.value })}
                    className="h-11 rounded-2xl"
                  />
                </div>
                <div className="space-y-2">
                  <p className="metric-label">{copy.country}</p>
                  <div className="space-y-2">
                    <Input
                      list="client-country-options"
                      value={countryInput}
                      onChange={(event) => {
                        const nextValue = event.target.value
                        setCountryInput(nextValue)
                        const selectedCountry = parseCountryInput(nextValue)
                        if (selectedCountry) {
                          setForm({ ...form, country: selectedCountry.code })
                        }
                      }}
                      placeholder={copy.searchCountry}
                      className="h-11 rounded-2xl"
                    />
                    <datalist id="client-country-options">
                      {COUNTRY_OPTIONS.map((country) => (
                        <option key={country.code} value={formatCountryLabel(country)} />
                      ))}
                    </datalist>
                  </div>
                </div>
              </div>

              <div className="space-y-2">
                <p className="metric-label">{copy.activity}</p>
                <textarea
                  className="min-h-[110px] w-full rounded-[20px] border border-border/80 bg-surface px-4 py-3 text-sm leading-6 outline-none"
                  value={form.activity_description ?? ''}
                  onChange={(event) => setForm({ ...form, activity_description: event.target.value })}
                />
              </div>

              <div className="grid gap-4 lg:grid-cols-2">
                <div className="space-y-2">
                  <p className="metric-label">{copy.families}</p>
                  <TagInput
                    value={form.product_families ?? []}
                    onChange={(value) => setForm({ ...form, product_families: value })}
                    placeholder={copy.add}
                  />
                </div>

                <div className="space-y-2">
                  <p className="metric-label">{copy.programs}</p>
                  <TagInput
                    value={form.program_names ?? []}
                    onChange={(value) => setForm({ ...form, program_names: value })}
                    placeholder={copy.add}
                  />
                </div>
              </div>

              {error ? <p className="text-sm text-destructive">{error}</p> : null}

              {editing !== 'new' ? (
                <Button
                  variant="outline"
                  className="text-destructive hover:text-destructive"
                  onClick={() => void handleDelete(editing)}
                  disabled={busy}
                >
                  <Trash2 className="h-4 w-4" />
                  {copy.delete}
                </Button>
              ) : null}
            </div>
          ) : (
            <EmptyState
              icon={Pencil}
              title={copy.noSelection}
              description={copy.noSelectionDescription}
              action={{ label: copy.newClient, onClick: startCreate }}
            />
          )}
        </div>
      </section>
    </div>
  )
}
