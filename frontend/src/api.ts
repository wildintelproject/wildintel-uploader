import type {
  AppSettings, AppSettingsUpdate, ConfigInfo, UpdateCheck, PreviousDeployment, ClassificationProject, PreprocessingOptions, CollectionCheck, CollectionPath, LocalLocation, LocalResearchProject, DeploymentCheck, DeploymentCheckResult, DeploymentFields,
  DeploymentSelection, ExistingDeployment, ImageCheck, ImportEvent, Location, LocalDeployment, ResearchProject,
  ScanResult, SessionSummary, StatisticsParams, TimestampLogResult, SessionScan, UploadCollection, UploadEvent, UploadMode, ValidationResult,
} from './types'

/** A failed response's message — FastAPI's `detail` when there is one. */
async function errorMessage(r: Response): Promise<string> {
  const text = await r.text().catch(() => r.statusText)
  let message = text
  try { message = JSON.parse(text).detail ?? text } catch { /* not JSON */ }
  return typeof message === 'string' ? message : JSON.stringify(message)
}

async function req<T>(url: string, options?: RequestInit): Promise<T> {
  const r = await fetch(url, options)
  if (!r.ok) throw new Error(await errorMessage(r))
  return r.json() as Promise<T>
}

function post<T>(url: string, body: unknown): Promise<T> {
  return req<T>(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}

/** POSTs body and reads the response as NDJSON: every event goes to
 * onEvent; resolves on {"type": "done"}, rejects on {"type": "error"} — or
 * with endedEarly if the stream ends before either. */
async function streamNdjson<E extends { type: string }>(
  url: string, body: unknown, onEvent: (event: E) => void, endedEarly: string,
): Promise<void> {
  const r = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!r.ok || !r.body) throw new Error(await errorMessage(r))
  const reader = r.body.pipeThrough(new TextDecoderStream()).getReader()
  let buffer = ''
  for (;;) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += value
    const lines = buffer.split('\n')
    buffer = lines.pop() ?? ''
    for (const line of lines.filter(Boolean)) {
      const event = JSON.parse(line) as E
      if (event.type === 'error') throw new Error((event as unknown as { detail: string }).detail)
      onEvent(event)
      if (event.type === 'done') return
    }
  }
  throw new Error(endedEarly)
}

/** Blank fields fall back to what's saved in settings.toml (the password is
 * never sent back to the frontend — see services.trapper_service). */
export interface TrapperCredentials {
  url: string
  username: string
  password: string
}

export const api = {
  checkHealth: async (): Promise<boolean> => {
    try {
      const r = await fetch('/api/health')
      return r.ok
    } catch {
      return false
    }
  },

  checkVersion: () => req<{ current: string }>('/api/version'),

  // Asks GitHub whether a newer release exists (only when the user presses the button).
  checkForUpdate: () => req<UpdateCheck>('/api/version/check'),

  trapperGetConfig: () =>
    req<{ base_url: string | null; user_name: string | null; has_password: boolean }>('/api/trapper/config'),

  trapperTestConnection: (creds: TrapperCredentials) =>
    post<{ ok: boolean; research_projects_count: number }>('/api/trapper/test-connection', creds),

  trapperResearchProjects: (creds: TrapperCredentials) =>
    post<{ results: ResearchProject[] }>('/api/trapper/research-projects', creds),

  trapperClassificationProjects: (creds: TrapperCredentials, researchProjectPk: number) =>
    post<{ results: ClassificationProject[] }>('/api/trapper/classification-projects', {
      ...creds, research_project_pk: researchProjectPk,
    }),

  trapperLocations: (creds: TrapperCredentials, researchProjectPk: number) =>
    post<{ results: Location[] }>('/api/trapper/locations', {
      ...creds, research_project_pk: researchProjectPk,
    }),

  trapperDeployments: (creds: TrapperCredentials, researchProjectPk: number) =>
    post<{ results: ExistingDeployment[] }>('/api/trapper/deployments', {
      ...creds, research_project_pk: researchProjectPk,
    }),

  // The backend and frontend always run on the same machine (a local
  // desktop app — see web.app_entry), so this pops the OS's own native
  // folder dialog and returns what was picked (null if cancelled).
  browseFolder: (title?: string) =>
    post<{ path: string | null }>('/api/deployment-import/browse-folder', { title: title ?? null }),

  scanFolder: (path: string) =>
    post<ScanResult>('/api/deployment-import/scan-folder', { path }),

  // For each deployment id, the folder where it is already kept in the collections folder (null if it is not there yet).
  existingDeployments: (researchProjectId: string, deploymentIds: string[]) =>
    post<{ results: Record<string, string | null> }>('/api/deployment-import/existing-deployments', { research_project_id: researchProjectId, deployment_ids: deploymentIds }),

  // For each deployment id, the details of the closest earlier revision of its location (null if there is none).
  previousDeployments: (researchProjectId: string, deploymentIds: string[]) =>
    post<{ results: Record<string, PreviousDeployment | null> }>('/api/deployment-import/previous-deployments', { research_project_id: researchProjectId, deployment_ids: deploymentIds }),

  // A session folder: one subfolder per deployment, each scanned.
  scanSession: (path: string) =>
    post<SessionScan>('/api/deployment-import/scan-session', { path }),

  checkCollection: (path: string) =>
    post<CollectionCheck>('/api/deployment-import/check-collection', { path }),

  // The research projects and locations kept in the collections folder.
  listResearchProjects: () =>
    post<{ results: LocalResearchProject[] }>('/api/deployment-import/research-projects/list', {}),

  saveResearchProject: (project: LocalResearchProject) =>
    post<LocalResearchProject>('/api/deployment-import/research-projects/save', project),

  listLocalLocations: (researchProjectId: string) =>
    post<{ results: LocalLocation[] }>('/api/deployment-import/locations/list', { research_project_id: researchProjectId }),

  saveLocalLocation: (researchProjectId: string, location: LocalLocation) =>
    post<LocalLocation>('/api/deployment-import/locations/save', { research_project_id: researchProjectId, location }),

  collectionPath: (researchProjectId: string, deploymentId: string) =>
    post<CollectionPath>('/api/deployment-import/collection-path', { research_project_id: researchProjectId, deployment_id: deploymentId }),

  listLocalDeployments: (collectionDir: string) =>
    post<{ results: LocalDeployment[] }>('/api/deployment-import/list-local-deployments', { path: collectionDir }),

  // checks omitted (or undefined) runs every check.
  validateImages: (path: string, checks?: ImageCheck[]) =>
    post<ValidationResult>('/api/deployment-import/validate-images', { path, checks: checks ?? null }),

  // collectionName: the collection folder's name (Local folder) — omitted for Trapper, whose collection is the id's own prefix.
  validateDeployment: (
    path: string, deployment: DeploymentFields, checks: DeploymentCheck[] | undefined,
    options: {
      collectionName?: string | null; expectedLocationId?: string | null; toleranceHours?: number
      /** Whose collections hold the previous revisions of the location, for the statistical checks. */
      researchProjectId?: string | null; statistics?: StatisticsParams
    } = {},
  ) =>
    post<DeploymentCheckResult>('/api/deployment-import/validate-deployment', {
      path, deployment, checks: checks ?? null, collection_name: options.collectionName ?? null,
      expected_location_id: options.expectedLocationId ?? null, tolerance_hours: options.toleranceHours ?? 1,
      research_project_id: options.researchProjectId ?? null, ...(options.statistics ? { statistics: options.statistics } : {}),
    }),

  // Puts the deployment's start and end in its collection's <collection>_FileTimestampLog.csv — before the postvalidation.
  writeTimestampLog: (researchProjectId: string, deployment: DeploymentFields) =>
    post<TimestampLogResult>('/api/deployment-import/timestamp-log', { research_project_id: researchProjectId, deployment }),

  importDeployment: (
    creds: TrapperCredentials, researchProjectPk: number, classificationProjectPk: number | null,
    sourceDir: string, deployment: DeploymentFields, timezone: string | null, registerDeployment: boolean,
    researchProjectId: string, onEvent: (event: ImportEvent) => void,
  ) =>
    streamNdjson<ImportEvent>('/api/deployment-import/import', {
      ...creds, research_project_pk: researchProjectPk, research_project_id: researchProjectId, classification_project_pk: classificationProjectPk,
      source_dir: sourceDir, deployment, timezone, register_deployment: registerDeployment,
    }, onEvent, 'The import ended unexpectedly.'),

  // preprocessing null copies the images as they are.
  importLocal: (
    sourceDir: string, collectionDir: string, collectionName: string | null, deployment: DeploymentFields,
    preprocessing: PreprocessingOptions | null, onEvent: (event: ImportEvent) => void,
  ) =>
    streamNdjson<ImportEvent>('/api/deployment-import/import-local', {
      source_dir: sourceDir, collection_dir: collectionDir, collection_name: collectionName, deployment, preprocessing,
    }, onEvent, 'The import ended unexpectedly.'),

  // The collections kept for a research project, and the deployments in each — what can be uploaded to Trapper.
  uploadCollections: (researchProjectId: string) =>
    post<{ results: UploadCollection[] }>('/api/upload/collections', { research_project_id: researchProjectId }),

  // Uploads one deployment: creates its location and the deployment in Trapper if need be, packs it and sends it — or,
  // as `mode` says, only shows what that would do, or only writes the files. The Trapper credentials are the saved ones.
  uploadDeployment: (
    researchProjectId: string, collection: string, deploymentId: string, maxZipMb: number, mode: UploadMode,
    onEvent: (event: UploadEvent) => void,
  ) =>
    streamNdjson<UploadEvent>('/api/upload/deployment', {
      research_project_id: researchProjectId, collection, deployment_id: deploymentId, max_zip_mb: maxZipMb, mode,
    }, onEvent, 'The upload ended unexpectedly.'),

  // Whether ExifTool is installed — adding metadata needs it.
  // Opens a folder kept by the app (inside its data folder) in the system's file explorer.
  openFolder: (path: string) => post<{ opened: string }>('/api/deployment-import/open-folder', { path }),
  exiftoolStatus: () => req<{ available: boolean; path: string | null }>('/api/deployment-import/exiftool'),

  listSessions: () => req<SessionSummary[]>('/api/sessions'),

  // The wizard's first step — task_id is undefined for a brand new run,
  // which creates its session.
  saveScan: (sourceDir: string, scan: ScanResult, taskId?: string) =>
    post<SessionSummary>('/api/sessions/scan', { task_id: taskId ?? null, source_dir: sourceDir, scan }),

  saveSelection: (taskId: string, selection: DeploymentSelection) =>
    post<SessionSummary>('/api/sessions/selection', { task_id: taskId, selection }),

  saveDetails: (taskId: string, deployment: DeploymentFields, timezone: string | null, ignoreDst: boolean) =>
    post<SessionSummary>('/api/sessions/details', { task_id: taskId, deployment, timezone, ignore_dst: ignoreDst }),

  discardSession: (taskId: string) =>
    req<{ status: string }>(`/api/sessions/${taskId}`, { method: 'DELETE' }),

  getSettings: () => req<AppSettings>('/api/settings'),

  saveSettings: (settings: AppSettingsUpdate) =>
    req<AppSettings>('/api/settings', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(settings),
    }),

  clearLog: () => req<{ deleted: number }>('/api/settings/log', { method: 'DELETE' }),

  // The settings files the user can switch to (the default settings.toml plus the ones created with addConfig);
  // each one's file itself is downloaded straight from /api/settings/configs/<id>/download.
  configs: () => req<ConfigInfo[]>('/api/settings/configs'),
  addConfig: (name: string) => post<ConfigInfo[]>('/api/settings/configs', { name }),
  activateConfig: (id: string) => post<ConfigInfo[]>(`/api/settings/configs/${encodeURIComponent(id)}/activate`, {}),
  openConfigFolder: (id: string) => post<{ ok: boolean }>(`/api/settings/configs/${encodeURIComponent(id)}/open-folder`, {}),
}
