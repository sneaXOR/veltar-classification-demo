import { useEffect, useMemo, useRef, useState } from 'react'
import {
  AlertCircle,
  ChevronDown,
  ChevronRight,
  FolderOpen,
  Loader2,
  Upload,
  UploadCloud,
} from 'lucide-react'
import { useNavigate } from 'react-router-dom'

import {
  fetchClients,
  fetchDocuments,
  submitBatch,
  submitDocument,
  type ClientProfile,
  type DocumentRecord,
  type UploadFileLike,
} from '../lib/api'
import { formatDateTime, formatDurationMs } from '../lib/format'
import { useLanguage } from '../lib/language'
import { getMarkingLabel } from '../lib/marking-labels'
import { getDocumentStatusTone, getProgressMessage, getProgressStageLabel } from '../lib/presentation'
import { Badge } from '../components/ui/badge'
import { Button } from '../components/ui/button'
import { EmptyState } from '../components/ui/empty-state'
import { Progress } from '../components/ui/progress'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/select'
import { cn } from '../lib/utils'

type DropEntry = DropFileEntry | DropDirectoryEntry

type DropEntryBase = {
  name: string
}

type DropFileEntry = DropEntryBase & {
  isFile: true
  isDirectory: false
  file: (callback: (file: File) => void, errorCallback?: (error: DOMException) => void) => void
}

type DropDirectoryEntry = DropEntryBase & {
  isFile: false
  isDirectory: true
  createReader: () => DropDirectoryReader
}

type DropDirectoryReader = {
  readEntries: (callback: (entries: DropEntry[]) => void, errorCallback?: (error: DOMException) => void) => void
}

type DataTransferItemWithEntry = DataTransferItem & {
  webkitGetAsEntry?: () => DropEntry | null
}

type FolderTreeNode = {
  key: string
  name: string
  path: string
  folders: FolderTreeNode[]
  documents: DocumentRecord[]
  documentCount: number
  activeCount: number
  latestUpdatedAt: string | null
  sortTimestamp: number
}

type HistoryItem =
  | {
      type: 'document'
      key: string
      document: DocumentRecord
      sortTimestamp: number
    }
  | {
      type: 'folder'
      key: string
      node: FolderTreeNode
      sortTimestamp: number
    }

type MutableFolderNode = {
  key: string
  name: string
  path: string
  folders: Map<string, MutableFolderNode>
  documents: DocumentRecord[]
}

const ANALYSIS_STEPS = ['queued', 'ingesting', 'processing', 'finalizing'] as const

function getCopy(uiLanguage: 'en' | 'fr') {
  if (uiLanguage === 'fr') {
    return {
      operationImpossible: 'Operation impossible.',
      importFolders: (count: number) => `Import ${count} dossiers`,
      analysisInProgress: 'Analyse en cours',
      error: 'Erreur',
      queued: 'En attente',
      intake: 'Intake',
      addDocuments: 'Ajouter des documents',
      clientProfile: 'Profil client',
      noProfile: 'Aucun profil',
      files: 'Fichiers',
      folder: 'Dossier',
      selectFiles: 'Selectionner des fichiers',
      selectFolder: 'Selectionner un dossier',
      releaseToImport: 'Relacher pour importer',
      dragAndDrop: 'Glisser deposer active',
      history: 'Historique',
      noDocument: 'Aucun document',
      noDocumentDescription: 'Ajoutez un fichier ou un dossier pour commencer.',
      inProgress: 'En cours',
      noActiveAnalysis: 'Aucune analyse active.',
      activeCount: (count: number) => `${count} en cours`,
      activeAnalyses: (count: number) => `${count} analyse(s) active(s)`,
      fileCount: (count: number) => `${count} fichier(s)`,
    }
  }

  return {
    operationImpossible: 'Operation unavailable.',
    importFolders: (count: number) => `Import ${count} folders`,
    analysisInProgress: 'Analysis in progress',
    error: 'Error',
    queued: 'Queued',
    intake: 'Intake',
    addDocuments: 'Add documents',
    clientProfile: 'Client profile',
    noProfile: 'No profile',
    files: 'Files',
    folder: 'Folder',
    selectFiles: 'Select files',
    selectFolder: 'Select folder',
    releaseToImport: 'Release to import',
    dragAndDrop: 'Drag and drop ready',
    history: 'History',
    noDocument: 'No document',
    noDocumentDescription: 'Add a file or folder to get started.',
    inProgress: 'In progress',
    noActiveAnalysis: 'No active analysis.',
    activeCount: (count: number) => `${count} active`,
    activeAnalyses: (count: number) => `${count} active analysis(es)`,
    fileCount: (count: number) => `${count} file(s)`,
  }
}

function getErrorMessage(error: unknown, uiLanguage: 'en' | 'fr') {
  if (typeof error === 'object' && error && 'response' in error) {
    const response = (error as { response?: { data?: { detail?: string } } }).response
    if (response?.data?.detail) return response.data.detail
  }
  return error instanceof Error ? error.message : getCopy(uiLanguage).operationImpossible
}

function getProgressPercent(document: DocumentRecord) {
  if (document.progress?.percent !== null && document.progress?.percent !== undefined) {
    return document.progress.percent
  }
  if (document.latest_job_status === 'queued') return 4
  if (document.latest_job_status === 'running') return 18
  return null
}

function getProgressStepIndex(stage: string | null) {
  if (!stage) return 0
  const index = ANALYSIS_STEPS.findIndex((step) => step === stage)
  return index >= 0 ? index : 0
}

function normalizeRelativePath(value?: string | null) {
  return (value ?? '').replace(/\\/g, '/').split('/').filter(Boolean).join('/')
}

function withRelativePath(file: File, relativePath: string): UploadFileLike {
  const uploadFile = file as UploadFileLike
  uploadFile.relativePath = normalizeRelativePath(relativePath)
  return uploadFile
}

function getRelativePath(file: UploadFileLike) {
  return normalizeRelativePath(file.relativePath || file.webkitRelativePath || '')
}

function dedupeFiles(files: UploadFileLike[]) {
  const seen = new Set<string>()
  return files.filter((file) => {
    const relativePath = getRelativePath(file)
    const key = `${relativePath || file.name}:${file.size}:${file.lastModified}`
    if (seen.has(key)) return false
    seen.add(key)
    return true
  })
}

async function readFileEntry(entry: DropFileEntry) {
  return new Promise<File>((resolve, reject) => {
    entry.file(resolve, reject)
  })
}

async function readDirectoryBatch(reader: DropDirectoryReader) {
  return new Promise<DropEntry[]>((resolve, reject) => {
    reader.readEntries((entries) => resolve(entries as DropEntry[]), reject)
  })
}

async function collectFilesFromEntry(entry: DropEntry, parentPath = ''): Promise<UploadFileLike[]> {
  if (entry.isFile) {
    const file = await readFileEntry(entry)
    return parentPath ? [withRelativePath(file, `${parentPath}/${entry.name}`)] : [file as UploadFileLike]
  }

  const reader = entry.createReader()
  const nestedFiles: UploadFileLike[] = []
  const currentPath = parentPath ? `${parentPath}/${entry.name}` : entry.name
  while (true) {
    const entries = await readDirectoryBatch(reader)
    if (!entries.length) break
    const entryFiles = await Promise.all(entries.map((childEntry) => collectFilesFromEntry(childEntry, currentPath)))
    nestedFiles.push(...entryFiles.flat())
  }
  return nestedFiles
}

async function extractDroppedFiles(dataTransfer: DataTransfer) {
  const items = Array.from(dataTransfer.items ?? []) as DataTransferItemWithEntry[]
  if (!items.length) return { files: Array.from(dataTransfer.files ?? []) as UploadFileLike[], containsDirectory: false }
  const extracted = await Promise.all(
    items.map(async (item) => {
      const entry = item.webkitGetAsEntry?.() as DropEntry | null | undefined
      if (entry) return { files: await collectFilesFromEntry(entry), containsDirectory: entry.isDirectory }
      const file = item.getAsFile()
      return { files: file ? [file as UploadFileLike] : [], containsDirectory: false }
    }),
  )
  return {
    files: dedupeFiles(extracted.flatMap((item) => item.files)),
    containsDirectory: extracted.some((item) => item.containsDirectory),
  }
}

function deriveBatchName(files: UploadFileLike[], uiLanguage: 'en' | 'fr') {
  const relativePaths = files.map((file) => getRelativePath(file)).filter(Boolean)
  if (!relativePaths.length) return undefined

  const roots = new Set(relativePaths.map((path) => path.split('/')[0]).filter(Boolean))
  if (roots.size === 1) return Array.from(roots)[0]
  return getCopy(uiLanguage).importFolders(roots.size)
}

function isDocumentActive(document: DocumentRecord) {
  return (
    !document.final_marking &&
    !document.processing_error &&
    !document.latest_job_error &&
    ['queued', 'running'].includes(document.latest_job_status ?? '')
  )
}

function sortDocumentsByUpdatedAt(left: DocumentRecord, right: DocumentRecord) {
  return new Date(right.updated_at).getTime() - new Date(left.updated_at).getTime()
}

function createMutableFolderNode(key: string, name: string, path: string): MutableFolderNode {
  return {
    key,
    name,
    path,
    folders: new Map<string, MutableFolderNode>(),
    documents: [],
  }
}

function finalizeFolderNode(node: MutableFolderNode): FolderTreeNode {
  const folders = Array.from(node.folders.values())
    .map((child) => finalizeFolderNode(child))
    .sort((left, right) => right.sortTimestamp - left.sortTimestamp)
  const documents = [...node.documents].sort(sortDocumentsByUpdatedAt)

  const latestDocument = documents[0]
  const latestFolder = folders[0]
  const latestUpdatedAt = latestDocument
    ? latestDocument.updated_at
    : latestFolder
      ? latestFolder.latestUpdatedAt
      : null

  return {
    key: node.key,
    name: node.name,
    path: node.path,
    folders,
    documents,
    documentCount:
      documents.length + folders.reduce((total, folder) => total + folder.documentCount, 0),
    activeCount:
      documents.filter((document) => isDocumentActive(document)).length +
      folders.reduce((total, folder) => total + folder.activeCount, 0),
    latestUpdatedAt,
    sortTimestamp: latestUpdatedAt ? new Date(latestUpdatedAt).getTime() : 0,
  }
}

function buildHistoryItems(documents: DocumentRecord[]): HistoryItem[] {
  const standalone: HistoryItem[] = []
  const batchRoots = new Map<string, MutableFolderNode>()

  for (const document of documents) {
    const relativePath = normalizeRelativePath(document.relative_path)
    if (!relativePath) {
      standalone.push({
        type: 'document',
        key: document.id,
        document,
        sortTimestamp: new Date(document.updated_at).getTime(),
      })
      continue
    }

    const segments = relativePath.split('/').filter(Boolean)
    if (!segments.length) {
      standalone.push({
        type: 'document',
        key: document.id,
        document,
        sortTimestamp: new Date(document.updated_at).getTime(),
      })
      continue
    }

    const batchKey = document.batch_id ?? `single:${document.id}`
    let rootNode = batchRoots.get(batchKey)
    if (!rootNode) {
      rootNode = createMutableFolderNode(batchKey, '', '')
      batchRoots.set(batchKey, rootNode)
    }
    let currentNode: MutableFolderNode = rootNode

    if (segments.length === 1) {
      currentNode.documents.push(document)
      continue
    }

    const folderSegments = segments.slice(0, -1)
    let currentPath = ''
    for (const segment of folderSegments) {
      currentPath = currentPath ? `${currentPath}/${segment}` : segment
      let nextNode = currentNode.folders.get(segment)
      if (!nextNode) {
        nextNode = createMutableFolderNode(`${batchKey}:${currentPath}`, segment, currentPath)
        currentNode.folders.set(segment, nextNode)
      }
      currentNode = nextNode
    }
    currentNode.documents.push(document)
  }

  const folderItems: HistoryItem[] = []
  for (const root of batchRoots.values()) {
    const rootFolders = Array.from(root.folders.values())
      .map((folder) => finalizeFolderNode(folder))
      .sort((left, right) => right.sortTimestamp - left.sortTimestamp)

    folderItems.push(
      ...rootFolders.map((node) => ({
        type: 'folder' as const,
        key: node.key,
        node,
        sortTimestamp: node.sortTimestamp,
      })),
    )

    folderItems.push(
      ...root.documents
        .sort(sortDocumentsByUpdatedAt)
        .map((document) => ({
          type: 'document' as const,
          key: document.id,
          document,
          sortTimestamp: new Date(document.updated_at).getTime(),
        })),
    )
  }

  return [...folderItems, ...standalone].sort((left, right) => right.sortTimestamp - left.sortTimestamp)
}

function ActiveRow({
  document,
  uiLanguage,
}: {
  document: DocumentRecord
  uiLanguage: 'en' | 'fr'
}) {
  const copy = getCopy(uiLanguage)
  const percent = getProgressPercent(document)
  const stepIndex = getProgressStepIndex(document.progress?.stage ?? document.latest_job_status)

  return (
    <div className="space-y-3 rounded-[20px] border border-border/70 bg-surface px-4 py-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate text-sm font-medium">{document.original_filename}</p>
          <p className="mt-1 text-sm text-muted-foreground">
            {getProgressMessage(document.progress, uiLanguage) || copy.analysisInProgress}
          </p>
        </div>
        <span className="font-mono text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
          {percent === null ? '...' : `${percent}%`}
        </span>
      </div>

      <Progress value={percent ?? undefined} indeterminate={percent === null} className="h-1.5" />

      <div className="flex flex-wrap gap-1.5">
        {ANALYSIS_STEPS.map((step, index) => (
          <span
            key={`${document.id}-${step}`}
            className={cn(
              'rounded-full px-2 py-1 font-mono text-[10px] uppercase tracking-[0.14em]',
              index < stepIndex && 'bg-primary text-primary-foreground',
              index === stepIndex && 'bg-secondary text-foreground',
              index > stepIndex && 'bg-background text-muted-foreground',
            )}
          >
            {getProgressStageLabel(step, uiLanguage)}
          </span>
        ))}
      </div>
    </div>
  )
}

function DocumentRow({
  document,
  onOpen,
  uiLanguage,
}: {
  document: DocumentRecord
  onOpen: () => void
  uiLanguage: 'en' | 'fr'
}) {
  const copy = getCopy(uiLanguage)
  const tone = getDocumentStatusTone(document, uiLanguage)
  const result = document.final_marking
    ? getMarkingLabel(document.final_marking, uiLanguage)
    : document.latest_job_error || document.processing_error
      ? copy.error
      : getProgressStageLabel(document.progress?.stage ?? document.latest_job_status, uiLanguage) || copy.queued

  return (
    <button type="button" className="list-row w-full text-left" onClick={onOpen}>
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <p className="truncate text-sm font-medium text-foreground">{document.original_filename}</p>
            <Badge variant={tone.variant}>{tone.label}</Badge>
          </div>
          <p className="mt-2 truncate text-sm text-muted-foreground">{result}</p>
        </div>

        <div className="flex items-center gap-5 text-sm text-muted-foreground">
          <span>{formatDurationMs(document.duration_ms)}</span>
          <span>{formatDateTime(document.updated_at)}</span>
        </div>
      </div>
    </button>
  )
}

function FolderTree({
  node,
  depth,
  openMap,
  onToggle,
  onOpenDocument,
  uiLanguage,
}: {
  node: FolderTreeNode
  depth: number
  openMap: Record<string, boolean>
  onToggle: (key: string) => void
  onOpenDocument: (documentId: string) => void
  uiLanguage: 'en' | 'fr'
}) {
  const copy = getCopy(uiLanguage)
  const isOpen = openMap[node.key] ?? depth === 0

  return (
    <div className="space-y-1">
      <button
        type="button"
        className="list-row w-full text-left"
        onClick={() => onToggle(node.key)}
        style={{ marginLeft: `${depth * 18}px` }}
      >
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              {isOpen ? (
                <ChevronDown className="h-4 w-4 text-muted-foreground" />
              ) : (
                <ChevronRight className="h-4 w-4 text-muted-foreground" />
              )}
              <FolderOpen className="h-4 w-4 text-muted-foreground" />
              <p className="truncate text-sm font-medium text-foreground">{node.name}</p>
              <Badge variant="outline">{node.documentCount}</Badge>
              {node.activeCount ? <Badge variant="warning">{copy.activeCount(node.activeCount)}</Badge> : null}
            </div>
            <p className="mt-2 truncate text-sm text-muted-foreground">
              {node.activeCount ? copy.activeAnalyses(node.activeCount) : copy.fileCount(node.documentCount)}
            </p>
          </div>

          <div className="flex items-center gap-5 text-sm text-muted-foreground">
            <span>{formatDateTime(node.latestUpdatedAt)}</span>
          </div>
        </div>
      </button>

      {isOpen ? (
        <div className="space-y-1">
          {node.folders.map((folder) => (
            <FolderTree
              key={folder.key}
              node={folder}
              depth={depth + 1}
              openMap={openMap}
              onToggle={onToggle}
              onOpenDocument={onOpenDocument}
              uiLanguage={uiLanguage}
            />
          ))}
          {node.documents.map((document) => (
            <div key={document.id} style={{ marginLeft: `${(depth + 1) * 18}px` }}>
              <DocumentRow document={document} onOpen={() => onOpenDocument(document.id)} uiLanguage={uiLanguage} />
            </div>
          ))}
        </div>
      ) : null}
    </div>
  )
}

export function DashboardPage() {
  const navigate = useNavigate()
  const { uiLanguage } = useLanguage()
  const copy = getCopy(uiLanguage)
  const [documents, setDocuments] = useState<DocumentRecord[]>([])
  const [clients, setClients] = useState<ClientProfile[]>([])
  const [selectedClientId, setSelectedClientId] = useState('all')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [dragActive, setDragActive] = useState(false)
  const [openFolders, setOpenFolders] = useState<Record<string, boolean>>({})
  const dragDepthRef = useRef(0)

  const activeDocuments = useMemo(
    () => documents.filter((document) => isDocumentActive(document)),
    [documents],
  )
  const historyItems = useMemo(() => buildHistoryItems(documents), [documents])
  const pickerInputClass =
    'absolute inset-0 h-full w-full cursor-pointer opacity-0 disabled:cursor-not-allowed'
  const folderPickerAttributes: React.InputHTMLAttributes<HTMLInputElement> & {
    directory: string
    webkitdirectory: string
  } = {
    directory: '',
    webkitdirectory: '',
  }

  async function refresh() {
    const [nextDocuments, nextClients] = await Promise.all([fetchDocuments(), fetchClients()])
    setDocuments(nextDocuments)
    setClients(nextClients)
  }

  useEffect(() => {
    void refresh()
    const intervalId = window.setInterval(() => {
      void refresh()
    }, busy || activeDocuments.length ? 2200 : 6000)
    return () => window.clearInterval(intervalId)
  }, [busy, activeDocuments.length])

  async function handleFiles(fileSource: FileList | UploadFileLike[] | null, options?: { forceBatch?: boolean }) {
    const files = dedupeFiles(
      Array.isArray(fileSource) ? fileSource : (Array.from(fileSource ?? []) as UploadFileLike[]),
    )
    if (!files.length) return

    const forceBatch = Boolean(options?.forceBatch)
    const hasDirectoryPaths = files.some((file) => Boolean(getRelativePath(file)))
    const batchName = deriveBatchName(files, uiLanguage)

    setBusy(true)
    setError(null)
    try {
      if (!forceBatch && files.length === 1 && !hasDirectoryPaths) {
        await submitDocument(files[0], undefined, selectedClientId === 'all' ? undefined : selectedClientId)
      } else {
        await submitBatch(files, batchName, selectedClientId === 'all' ? undefined : selectedClientId)
      }
      await refresh()
    } catch (nextError) {
      setError(getErrorMessage(nextError, uiLanguage))
    } finally {
      setBusy(false)
    }
  }

  function handleDragEnter(event: React.DragEvent<HTMLElement>) {
    event.preventDefault()
    event.stopPropagation()
    if (busy) return
    dragDepthRef.current += 1
    setDragActive(true)
  }

  function handleDragLeave(event: React.DragEvent<HTMLElement>) {
    event.preventDefault()
    event.stopPropagation()
    if (busy) return
    dragDepthRef.current = Math.max(0, dragDepthRef.current - 1)
    if (dragDepthRef.current === 0) setDragActive(false)
  }

  function handleDragOver(event: React.DragEvent<HTMLElement>) {
    event.preventDefault()
    event.stopPropagation()
    if (busy) return
    event.dataTransfer.dropEffect = 'copy'
    setDragActive(true)
  }

  async function handleDrop(event: React.DragEvent<HTMLElement>) {
    event.preventDefault()
    event.stopPropagation()
    dragDepthRef.current = 0
    setDragActive(false)
    if (busy) return
    const { files, containsDirectory } = await extractDroppedFiles(event.dataTransfer)
    await handleFiles(files, { forceBatch: containsDirectory })
  }

  return (
    <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_320px]">
      <div className="space-y-6">
        <section
          className={cn('drop-surface', dragActive && 'drop-surface-active', busy && 'pointer-events-none opacity-75')}
          onDragEnter={handleDragEnter}
          onDragLeave={handleDragLeave}
          onDragOver={handleDragOver}
          onDrop={(event) => {
            void handleDrop(event)
          }}
        >
          <div className="relative z-10 space-y-5">
            <div className="space-y-2">
              <p className="eyebrow">{copy.intake}</p>
              <h2 className="text-2xl font-semibold tracking-tight">{copy.addDocuments}</h2>
            </div>

            <div className="grid gap-4 lg:grid-cols-[240px_1fr] lg:items-end">
              <div className="space-y-2">
                <p className="metric-label">{copy.clientProfile}</p>
                <Select value={selectedClientId} onValueChange={setSelectedClientId} disabled={busy}>
                  <SelectTrigger className="h-11 rounded-2xl border-border/80 bg-surface">
                    <SelectValue placeholder={copy.noProfile} />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">{copy.noProfile}</SelectItem>
                    {clients.map((client) => (
                      <SelectItem key={client.id} value={client.id}>
                        {client.name} ({client.country})
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="flex flex-wrap gap-2">
                <div className="relative inline-flex">
                  <Button type="button" disabled={busy}>
                    {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Upload className="h-4 w-4" />}
                    {copy.files}
                  </Button>

                  <input
                    aria-label={copy.selectFiles}
                    className={pickerInputClass}
                    disabled={busy}
                    multiple
                    type="file"
                    onChange={(event) => {
                      const selectedFiles = event.target.files ? Array.from(event.target.files) : []
                      event.target.value = ''
                      void handleFiles(selectedFiles as UploadFileLike[])
                    }}
                  />
                </div>

                <div className="relative inline-flex">
                  <Button type="button" variant="outline" disabled={busy}>
                    <FolderOpen className="h-4 w-4" />
                    {copy.folder}
                  </Button>

                  <input
                    {...folderPickerAttributes}
                    aria-label={copy.selectFolder}
                    className={pickerInputClass}
                    disabled={busy}
                    multiple
                    type="file"
                    onChange={(event) => {
                      const selectedFiles = event.target.files ? Array.from(event.target.files) : []
                      event.target.value = ''
                      void handleFiles(selectedFiles as UploadFileLike[], { forceBatch: true })
                    }}
                  />
                </div>
              </div>
            </div>

            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <UploadCloud className="h-4 w-4" />
              {dragActive ? copy.releaseToImport : copy.dragAndDrop}
            </div>
          </div>
        </section>

        {error ? (
          <section className="app-panel border-destructive/25 bg-destructive/5">
            <div className="panel-body flex items-start gap-3">
              <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-destructive" />
              <p className="text-sm text-destructive">{error}</p>
            </div>
          </section>
        ) : null}

        <section className="app-panel overflow-hidden">
          <div className="panel-header">
            <h2 className="section-title">{copy.history}</h2>
            <span className="font-mono text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
              {documents.length}
            </span>
          </div>

          <div className="panel-body p-0">
            {historyItems.length ? (
              <div className="divide-y divide-border/70">
                {historyItems.map((item) => (
                  <div key={item.key} className="px-2 py-1.5 sm:px-3">
                    {item.type === 'document' ? (
                      <DocumentRow
                        document={item.document}
                        onOpen={() => navigate(`/documents/${item.document.id}`)}
                        uiLanguage={uiLanguage}
                      />
                    ) : (
                      <FolderTree
                        node={item.node}
                        depth={0}
                        openMap={openFolders}
                        onToggle={(key) =>
                          setOpenFolders((current) => ({ ...current, [key]: !(current[key] ?? true) }))
                        }
                        onOpenDocument={(documentId) => navigate(`/documents/${documentId}`)}
                        uiLanguage={uiLanguage}
                      />
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <div className="p-6">
                <EmptyState
                  icon={UploadCloud}
                  title={copy.noDocument}
                  description={copy.noDocumentDescription}
                />
              </div>
            )}
          </div>
        </section>
      </div>

      <aside className="sticky-rail">
        <section className="app-panel overflow-hidden">
          <div className="panel-header">
            <h2 className="section-title">{copy.inProgress}</h2>
            <Badge variant="outline">{activeDocuments.length}</Badge>
          </div>

          <div className="panel-body space-y-3">
            {activeDocuments.length ? (
              activeDocuments.map((document) => (
                <ActiveRow key={document.id} document={document} uiLanguage={uiLanguage} />
              ))
            ) : (
              <p className="text-sm text-muted-foreground">{copy.noActiveAnalysis}</p>
            )}
          </div>
        </section>
      </aside>
    </div>
  )
}
