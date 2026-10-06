// The web app's backend, faked inside the page for the documentation's
// screenshots (see capture.py): window.fetch answers /api/* from the sample
// data below — no Trapper, no real folders, no real account. Streaming
// endpoints send their NDJSON events a few milliseconds apart; with
// hold: true the stream stays open after them, so a screenshot catches the
// run midway. capture.py changes window.__mock before a step when needed.
(() => {
  const TRAPPER_URL = 'https://trapper.example.org'
  const DATA_DIR = '/home/me/Documents/wildintel-uploader'
  const COLLECTIONS = `${DATA_DIR}/collections`

  const PROJECT = { name: 'Doñana National Park', acronym: 'DONA', trapper_pk: 2 }

  const LOCATIONS = [
    { location_id: 'DONA_01', name: 'Doñana site 1', timezone: 'Europe/Madrid', ignore_dst: true, latitude: 37.0074, longitude: -6.4392, coordinate_uncertainty: 50, trapper_pk: 101 },
    { location_id: 'DONA_02', name: 'Doñana site 2', timezone: 'Europe/Madrid', ignore_dst: true, latitude: 37.0121, longitude: -6.4287, coordinate_uncertainty: 50, trapper_pk: 102 },
    { location_id: 'DONA_03', name: 'Doñana site 3', timezone: 'Europe/Madrid', ignore_dst: true, latitude: 36.9983, longitude: -6.4511, coordinate_uncertainty: 100, trapper_pk: 103 },
  ]

  const CAMERA = { model: 'Reconyx HyperFire 2', id: 'P800HG08' }

  const SCAN = {
    file_count: 241, image_count: 241, start_date: '2024-09-04T13:10:00', end_date: '2024-10-12T07:02:41',
    camera_model: CAMERA.model, camera_id: CAMERA.id, warnings: [],
  }

  const SESSION_SCAN = {
    deployments: [
      ['DONA_01', 241, '2024-09-04T13:10:00', '2024-10-12T07:02:41'],
      ['DONA_02', 188, '2024-09-04T14:02:11', '2024-10-12T07:40:09'],
      ['DONA_03', 305, '2024-09-05T09:31:00', '2024-10-13T08:15:33'],
    ].map(([name, n, start_date, end_date]) => ({
      name, path: `/home/me/Pictures/trip-2024-09/${name}`, file_count: n, image_count: n, start_date, end_date,
      camera_model: CAMERA.model, camera_id: CAMERA.id, warnings: [], from_timestamp_log: false, log_deployment_id: null,
    })),
    loose_files: 0, warnings: [], timestamp_log: null,
  }

  const VALIDATION = {
    checked_count: 241,
    corrupted: [],
    sequence_issues: [],
    subdirectories: [],
    cameras: [{ model: CAMERA.model, camera_id: CAMERA.id, count: 241, examples: ['IMG_0001.JPG', 'IMG_0002.JPG'] }],
    cameras_without_info: 0,
    exiftool: true,
    exif_missing: { date: { count: 0, examples: [] }, camera_model: { count: 0, examples: [] }, camera_id: { count: 0, examples: [] } },
    duplicates: [{ size: 1843211, files: ['IMG_0087.JPG', 'IMG_0087 (copy).JPG'] }],
  }

  const statistic = (value, reference, lower, upper, history, message) => ({
    ok: true, skipped: false, message, value, reference, lower, upper, previous: history.length,
    history: history.map(([revision, v]) => ({ revision, deployment_id: `R000${revision}-DONA_01`, value: v })),
  })

  const POSTVALIDATION = {
    checked_count: 241,
    deployment_id: { ok: true, message: 'R0003-DONA_01 is a valid deployment id.' },
    collection_prefix: { ok: true, message: 'The deployment id starts with its collection, R0003.' },
    collection_name: { ok: true, message: 'R0003 is a valid collection name.' },
    location: { ok: true, message: 'The id’s location, DONA_01, is the one chosen.' },
    image_count: statistic(241, 238, 119, 357, [[1, 224], [2, 252]], '241 images — like the previous revisions (median 238, ±50 %).'),
    sequence_count: statistic(62, 58, 29, 87, [[1, 55], [2, 61]], '62 sequences — like the previous revisions (median 58, ±50 %).'),
    sequence_length: statistic(3.9, 4.1, 2.1, 6.2, [[1, 4.1], [2, 4.1]], 'Sequences of 3.9 images on average — like the previous revisions (median 4.1, ±50 %).'),
    out_of_range: [], tolerance_hours: 1, camera_mismatches: [], camera_models_found: [CAMERA.model],
  }

  const PREVIOUS = {
    revision: 2, deployment_id: 'R0002-DONA_01',
    deployment: {
      deployment_id: 'R0002-DONA_01', location_id: 'DONA_01', location_name: 'Doñana site 1', latitude: 37.0074, longitude: -6.4392,
      coordinate_uncertainty: 50, start_date: '2024-06-01T09:00:00+02:00', end_date: '2024-07-10T08:00:00+02:00',
      setup_by: 'M. Ruiz', camera_id: CAMERA.id, camera_model: CAMERA.model, camera_interval: 5, camera_height: 0.6, camera_tilt: 0,
      camera_heading: 180, detection_distance: 12, bait_use: false, feature_type: 'trailGame', habitat: 'Mediterranean scrubland',
      deployment_groups: 'season:summer 2024', comments: null, tags: [],
    },
  }

  const SETTINGS = {
    GENERAL: { log_level: 'INFO', workers: 4, cpu_count: 8, log_file: '/home/me/.config/wildintel-uploader/logs/wildintel-uploader.log', log_level_override: null },
    TRAPPER: { base_url: TRAPPER_URL, user_name: 'field.team@example.org', has_password: true },
    DATA: { dir: DATA_DIR },
    VALIDATION: { corrupted: true, sequence: true, structure: true, camera: true, exif: true, duplicates: true },
    POSTVALIDATION: {
      deployment_id: true, collection_prefix: true, collection_name: true, location: true, time_range: true, camera: true,
      image_count: true, sequence_count: true, sequence_length: true,
      tolerance_hours: 1, sequence_gap_seconds: 60, min_revisions: 2, similarity_method: 'median',
      image_count_tolerance: 50, sequence_count_tolerance: 50, sequence_length_tolerance: 50,
    },
    PREPROCESSING: {
      rename: true, resize: true, resize_width: 2400, metadata: true, owner: 'Estación Biológica de Doñana', publisher: 'WildINTEL',
      coverage: 'Doñana National Park', license_url: 'https://creativecommons.org/licenses/by-nc/4.0/', ignore_dst: true, convert_to_utc: true,
    },
  }

  const TRAPPER_PROJECTS = [
    { pk: 2, name: 'Doñana National Park', acronym: 'DONA' },
    { pk: 5, name: 'Sierra Morena', acronym: 'SMOR' },
    { pk: 7, name: 'Bavarian Forest', acronym: 'BFNP' },
  ]

  const UPLOAD_COLLECTIONS = [{
    name: 'R0003', path: `${COLLECTIONS}/DONA/R0003`,
    deployments: [
      { deployment_id: 'R0003-DONA_01', location_id: 'DONA_01', start_date: '2024-09-04T13:10:00+02:00', end_date: '2024-10-12T07:02:41+02:00', images: 241, preprocessed: true, uploaded_at: null },
      { deployment_id: 'R0003-DONA_02', location_id: 'DONA_02', start_date: '2024-09-04T14:02:11+02:00', end_date: '2024-10-12T07:40:09+02:00', images: 188, preprocessed: true, uploaded_at: null },
      { deployment_id: 'R0003-DONA_03', location_id: 'DONA_03', start_date: '2024-09-05T09:31:00+02:00', end_date: '2024-10-13T08:15:33+02:00', images: 305, preprocessed: true, uploaded_at: '2026-09-27T10:12:00+00:00' },
    ],
  }]

  // The reports the validation, the postvalidation and the preprocessing leave.
  const VALIDATION_REPORT_ID = '20261006-094512_validation_R0003-DONA_01'
  const REPORTS = {
    [VALIDATION_REPORT_ID]: {
      id: VALIDATION_REPORT_ID, kind: 'validation', title: 'Validation of R0003-DONA_01', created_at: '2026-10-06T09:45:12+00:00',
      source_dir: '/home/me/Pictures/R0003-DONA_01', deployment_id: null, checked: 241, parameters: { checks: ['camera', 'corrupted', 'duplicates', 'exif', 'sequence', 'structure'] },
      checks: {
        corrupted: { label: 'Corrupted images', scope: 'images', ok: 241, failed: 0 },
        sequence: { label: 'Shooting order vs. filename sequence', scope: 'images', ok: 241, failed: 0 },
        exif: { label: 'Required EXIF fields', scope: 'images', ok: 241, failed: 0 },
        duplicates: { label: 'Duplicate images', scope: 'images', ok: 239, failed: 2 },
        structure: { label: 'Folder structure', scope: 'deployment', ok: 1, failed: 0 },
        camera: { label: 'Camera', scope: 'deployment', ok: 1, failed: 0 },
      },
      totals: { entries: 965, ok: 963, failed: 2 },
      entries: [
        { identifier: 'IMG_0087.JPG', check: 'duplicates', status: 'failed', message: 'same content as IMG_0087 (copy).JPG' },
        { identifier: 'IMG_0087 (copy).JPG', check: 'duplicates', status: 'failed', message: 'same content as IMG_0087.JPG' },
      ],
    },
    '20261006-094930_preprocessing_R0003-DONA_01': {
      id: '20261006-094930_preprocessing_R0003-DONA_01', kind: 'preprocessing', title: 'Preprocessing of R0003-DONA_01', created_at: '2026-10-06T09:49:30+00:00',
      source_dir: '/home/me/Pictures/R0003-DONA_01', deployment_id: 'R0003-DONA_01', checked: 241, parameters: {},
      checks: { preprocessing: { label: 'Preprocessing', scope: 'images', ok: 241, failed: 0 } },
      totals: { entries: 241, ok: 241, failed: 0 }, entries: [],
    },
  }
  const reportSummary = ({ entries, parameters, checks, ...summary }) => summary

  const step = (name, status, message) => ({ type: 'step', step: name, status, message })

  // One deployment's upload: all done — or, held, halfway through sending a zip.
  const uploadEvents = (body, halfway) => {
    const id = body.deployment_id
    const images = { 'R0003-DONA_01': 241, 'R0003-DONA_02': 188, 'R0003-DONA_03': 305 }[id]
    const events = [
      step('connect', 'done', `Connected to ${TRAPPER_URL}.`),
      step('classification', 'done', 'Classification project: DONA 2024.'),
      step('location', 'done', `Location ${id.split('-')[1]} already in Trapper.`),
      step('deployment', 'done', `Deployment ${id} created in Trapper.`),
      step('package', 'done', `Packed ${images} images in 1 zip (${Math.round(images * 0.49)} MB).`),
      step('csv', 'done', 'R0003_deployments.csv updated.'),
    ]
    if (halfway) {
      events.push(step('upload', 'running', 'Uploading R0003-DONA_02_part1.zip…'))
      events.push({ type: 'upload_progress', file: 'R0003-DONA_02_part1.zip', bytes: 52428800, total: 98566144 })
      return events
    }
    events.push(
      step('upload', 'done', 'Uploaded R0003-DONA_01_part1.zip.'),
      step('process', 'done', 'Trapper is processing the collection.'),
      step('wait', 'done', 'The collection is ready.'),
      { type: 'done', mode: body.mode, collection: 'R0003', deployment_id: id, parts: 1, location_created: false, deployment_created: true },
    )
    return events
  }

  const mock = {
    sessions: [],
    uploads: 0,
    streamDelay: 0,
    streams: {
      '/api/deployment-import/import-local': () => ({
        events: [
          ...Array.from({ length: 241 }, (_, i) => ({ type: 'copy', index: i + 1, total: 241, name: `IMG_${String(i + 1).padStart(4, '0')}.JPG` })),
          { type: 'metadata', total: 241 },
          { type: 'sealing' },
          { type: 'done', dest_dir: `${COLLECTIONS}/DONA/R0003/R0003-DONA_01`, processed: 241, skipped: 0, sealed: true },
        ],
      }),
      '/api/upload/deployment': (body) => {
        mock.uploads += 1
        // The run holds at its second deployment, so a screenshot catches it midway.
        const halfway = body.mode === 'upload' && mock.holdSecond && mock.uploads === 2
        return { events: uploadEvents(body, halfway), hold: halfway }
      },
      '/api/sync/collections': () => ({
        events: [
          { type: 'progress', message: 'Research project DONA: already there.' },
          { type: 'progress', message: 'Reading the locations from Trapper…' },
          { type: 'progress', message: 'Locations: 1 created, 2 already there.' },
          { type: 'progress', message: 'Reading the deployments and collections from Trapper…' },
          { type: 'progress', message: 'R0001: collection created.' },
          { type: 'progress', message: 'R0001-DONA_01: created (224 images).' },
          { type: 'progress', message: 'R0001-DONA_02: created (190 images).' },
          { type: 'progress', message: 'R0002: collection created.' },
          { type: 'progress', message: 'R0002-DONA_01: created (252 images).' },
          {
            type: 'done', research_project_id: 'DONA', folder: `${COLLECTIONS}/DONA`, collections: ['R0001', 'R0002'],
            created: {
              research_project: [], locations: ['DONA_03'], collections: ['R0001', 'R0002'],
              deployments: ['R0001-DONA_01', 'R0001-DONA_02', 'R0002-DONA_01'], timestamp_log: ['R0001', 'R0002'],
              images: ['R0001-DONA_01', 'R0001-DONA_02', 'R0002-DONA_01'],
            },
            kept: { research_project: ['DONA'], locations: ['DONA_01', 'DONA_02'], collections: [], deployments: [], timestamp_log: [], images: [] },
            unassigned: [], failed: [{ deployment_id: 'R0002-DONA_09', error: 'its start date is not valid' }],
          },
        ],
      }),
    },
    json: {
      'GET /api/health': () => ({ status: 'ok' }),
      'GET /api/version': () => ({ current: '0.1.0' }),
      'GET /api/version/check': () => ({ current: '0.1.0', latest: '0.1.0', update_available: false, release_url: null, download_url: null, error: null }),
      'GET /api/settings': () => SETTINGS,
      'PUT /api/settings': () => SETTINGS,
      'GET /api/settings/configs': () => [
        { id: 'default', name: 'Default config', path: '/home/me/.config/wildintel-uploader/settings.toml', active: true },
        { id: 'test-server', name: 'test-server', path: '/home/me/.config/wildintel-uploader/configs/test-server.toml', active: false },
      ],
      'GET /api/trapper/config': () => ({ base_url: TRAPPER_URL, user_name: 'field.team@example.org', has_password: true }),
      'POST /api/trapper/test-connection': () => ({ ok: true, research_projects_count: 3 }),
      'POST /api/trapper/research-projects': () => ({ results: TRAPPER_PROJECTS }),
      'POST /api/trapper/classification-projects': () => ({ results: [{ pk: 10, name: 'DONA 2024', is_active: true }, { pk: 11, name: 'DONA 2023', is_active: false }] }),
      'POST /api/trapper/locations': () => ({ results: LOCATIONS.map((l) => ({ pk: l.trapper_pk, location_id: l.location_id.toLowerCase(), name: l.name, timezone: l.timezone, ignore_dst: true, latitude: l.latitude, longitude: l.longitude })) }),
      'GET /api/deployment-import/exiftool': () => ({ available: true, path: '/usr/bin/exiftool' }),
      'POST /api/deployment-import/browse-folder': () => ({ path: mock.browse }),
      'POST /api/deployment-import/scan-folder': () => SCAN,
      'POST /api/deployment-import/scan-session': () => SESSION_SCAN,
      'POST /api/deployment-import/validate-images': () => ({ ...VALIDATION, report_id: VALIDATION_REPORT_ID }),
      'POST /api/deployment-import/validate-deployment': () => POSTVALIDATION,
      'POST /api/deployment-import/research-projects/list': () => ({ results: [{
        ...PROJECT, sampling_design: 1, sensor_method: 1, animal_types: 1, bait_use: 1, event_interval: 0, keywords: '', abstract: '', methods: '', description: '',
      }] }),
      'POST /api/deployment-import/locations/list': () => ({ results: LOCATIONS }),
      'POST /api/deployment-import/next-revision': () => ({ last: 2, next: 3 }),
      'POST /api/deployment-import/previous-deployments': (body) => ({ results: Object.fromEntries(body.deployment_ids.map((id) => [id, id.endsWith('DONA_01') ? PREVIOUS : null])) }),
      'POST /api/deployment-import/existing-deployments': (body) => ({ results: Object.fromEntries(body.deployment_ids.map((id) => [id, null])) }),
      'POST /api/deployment-import/collection-path': () => ({ path: `${COLLECTIONS}/DONA/R0003`, collection: 'R0003', exists: true, name: 'R0003' }),
      'POST /api/deployment-import/check-collection': () => ({ exists: true, name: 'R0003' }),
      'POST /api/deployment-import/timestamp-log': () => ({ path: `${COLLECTIONS}/DONA/R0003/R0003_FileTimestampLog.csv`, action: 'added', rows: 1, collection: 'R0003' }),
      'POST /api/deployment-import/open-folder': () => ({ opened: '' }),
      'GET /api/reports': () => Object.values(REPORTS).map(reportSummary).sort((a, b) => b.created_at.localeCompare(a.created_at)),
      'GET /api/sessions': () => mock.sessions,
      'POST /api/sessions/scan': (body) => ({ ...UNFINISHED[0], task_id: body.task_id ?? 'new', phase: 'scanned' }),
      'POST /api/sessions/selection': (body) => ({ ...UNFINISHED[0], task_id: body.task_id, phase: 'selected' }),
      'POST /api/sessions/details': (body) => ({ ...UNFINISHED[0], task_id: body.task_id, phase: 'ready' }),
      'POST /api/upload/collections': () => ({ results: UPLOAD_COLLECTIONS }),
      'POST /api/upload/classification-projects': () => ({ results: [{ pk: 10, name: 'DONA 2024', is_active: true }] }),
      'POST /api/upload/check-access': () => ({ checks: [
        { check: 'research_project', ok: true, message: 'Research project DONA found in Trapper (pk 2).' },
        { check: 'classification_project', ok: true, message: 'Classification project DONA 2024 (pk 10).' },
        { check: 'location', ok: true, message: 'The locations DONA_01, DONA_02 are in Trapper.' },
        { check: 'uploader', ok: true, message: 'The uploader accepted the login.' },
      ] }),
      'POST /api/sync/collection-names': () => ({ results: [
        { name: 'R0001', deployments: ['R0001-DONA_01', 'R0001-DONA_02'] },
        { name: 'R0002', deployments: ['R0002-DONA_01', 'R0002-DONA_09'] },
        { name: 'R0003', deployments: ['R0003-DONA_01', 'R0003-DONA_02', 'R0003-DONA_03'] },
      ] }),
    },
  }

  // Unfinished runs, for the resume page.
  const UNFINISHED = [
    {
      task_id: '5f0c2a1e-8d4b-4c61-9a57-2b3e7f1d6c90', created_at: '2026-09-26T16:02:00+00:00', updated_at: '2026-09-26T16:20:00+00:00',
      phase: 'ready', task: 'deployment', source_dir: '/home/me/Pictures/R0003-DONA_01', scan: SCAN,
      selection: {
        destination: 'local', mode: 'new', research_project: { pk: 2, name: PROJECT.name, acronym: 'DONA' },
        location: { pk: 101, location_id: 'DONA_01', name: 'Doñana site 1', timezone: 'Europe/Madrid' },
        collection_dir: `${COLLECTIONS}/DONA/R0003`, collection_name: 'R0003',
      },
      deployment: PREVIOUS.deployment,
    },
    {
      task_id: '0b7d9e44-1c2f-4a88-b3d1-7e5a0c9f2b61', created_at: '2026-09-22T11:15:00+00:00', updated_at: '2026-09-22T11:20:00+00:00',
      phase: 'scanned', task: 'deployment', source_dir: '/home/me/Pictures/R0003-DONA_02', scan: { ...SCAN, file_count: 188, image_count: 188 },
    },
  ]
  mock.unfinished = UNFINISHED
  mock.reports = REPORTS
  window.__mock = mock

  const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
  const realFetch = window.fetch.bind(window)

  window.fetch = async (input, init = {}) => {
    const url = new URL(typeof input === 'string' ? input : input.url, location.href)
    if (!url.pathname.startsWith('/api/')) return realFetch(input, init)
    const method = (init.method || 'GET').toUpperCase()
    const body = init.body ? JSON.parse(init.body) : {}
    await sleep(30)

    const stream = mock.streams[url.pathname]
    if (stream) {
      const { events, hold } = stream(body)
      const encoder = new TextEncoder()
      const signal = init.signal
      return new Response(new ReadableStream({
        async start(controller) {
          // A few at a time: the page renders as it would with a real run.
          for (let i = 0; i < events.length; i += 200) {
            if (signal?.aborted) return
            controller.enqueue(encoder.encode(events.slice(i, i + 200).map((e) => JSON.stringify(e) + '\n').join('')))
            await sleep(mock.streamDelay)
          }
          if (!hold) controller.close()
        },
      }), { status: 200, headers: { 'Content-Type': 'application/x-ndjson' } })
    }

    const report = url.pathname.match(/^\/api\/reports\/([^/]+)$/)
    if (report && method === 'GET' && mock.reports[decodeURIComponent(report[1])]) {
      return new Response(JSON.stringify(mock.reports[decodeURIComponent(report[1])]), { status: 200, headers: { 'Content-Type': 'application/json' } })
    }

    const key = `${method} ${url.pathname}`
    const handler = mock.json[key] ?? (method === 'DELETE' ? () => ({ status: 'ok' }) : null)
    if (!handler) {
      console.warn('[mock] unhandled', key)
      return new Response(JSON.stringify({ detail: `Not mocked: ${key}` }), { status: 404 })
    }
    return new Response(JSON.stringify(handler(body)), { status: 200, headers: { 'Content-Type': 'application/json' } })
  }
})()
