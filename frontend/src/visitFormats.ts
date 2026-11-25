/** The formats of the files of visits that WildINTEL Uploader reads, as the panel of the supported formats tells them: what each one is, and what goes in each of its
 * columns. The columns of the Custom CSV are those of its template (visitsTemplate.csv), in its order: a test keeps the two the same. */
export interface FormatColumn { name: string; meaning: string; example?: string; required?: boolean }
export interface VisitFormat {
  key: 'custom' | 'epicollect'
  name: string
  /** One sentence: what the file is. */
  summary: string
  /** What is worth knowing before its columns. */
  intro: string
  columns: FormatColumn[]
  /** The columns that are in the file and are not read. */
  ignored?: string
  /** The name of the template downloaded, when the format has one. */
  template?: string
}

export const CUSTOM_COLUMNS: FormatColumn[] = [
  { name: 'location_id', required: true, meaning: 'The location of the visit, written exactly as the research project has it: WICP_02_001 and WICP_02_1 are two different locations.', example: 'WICP_02_001' },
  { name: 'session', meaning: 'The revision: R0013, or only its number. Without it, the visits of each location are numbered in the order of their dates: the first R0001, the second R0002…', example: 'R0001' },
  { name: 'date', required: true, meaning: 'The day of the visit: YYYY-MM-DD or DD/MM/YYYY.', example: '2026-09-14' },
  { name: 'time', required: true, meaning: 'The time of the visit, on the clock of the location: HH:MM or HH:MM:SS.', example: '08:30:00' },
  { name: 'actions', required: true, meaning: 'What was done: Installation, Revision, Desinstallation, Stolen or Archive. Several are joined with +.', example: 'Revision + Desinstallation' },
  { name: 'trappers', meaning: 'Who went, with the names written as in the field. Several are separated by commas, all in quotes.', example: '"Ana Pérez, Luis Gómez"' },
  { name: 'status', meaning: 'How the camera was found: OK, Altered, Stolen, Not revised (the visit could not be made), New site or Inactive site. Empty when the camera is put up.', example: 'OK' },
  { name: 'camera_id', meaning: 'The camera: its serial number, as the research project has it.', example: 'BR5071050724' },
  { name: 'camera_model', meaning: 'The model of the camera.', example: 'Browning-BTC-8A' },
  { name: 'sd', meaning: 'The SD card left in the camera, with the name written on it. Empty when no card is left.', example: '1' },
  { name: 'card_batteries_ok', meaning: 'The card and the batteries when the camera was found: OK, Card full, No batteries, or Card full and no batteries. Empty when the camera is put up.', example: 'OK' },
  { name: 'num_photos', meaning: 'How many images the card collected has, a whole number. Empty when no card is collected.', example: '1620' },
  { name: 'date_time_ok', meaning: 'Whether the date and the time of the camera were right: Yes or No.', example: 'Yes' },
  { name: 'camera_height', meaning: 'The height of the camera above the ground, in metres, with a point for the decimals.', example: '0.5' },
  { name: 'camera_interval', meaning: 'The seconds the camera waits between two triggers.', example: '30' },
  { name: 'comments', meaning: 'Notes of the visit, free text. In quotes when it has commas.', example: '"Card full, batteries changed"' },
  { name: 'latitude', meaning: 'Where the visit was noted, in decimal degrees (−90 to 90). Empty: the coordinates of the location are used.', example: '37.012340' },
  { name: 'longitude', meaning: 'Where the visit was noted, in decimal degrees (−180 to 180). Empty: the coordinates of the location are used.', example: '-6.441230' },
]

/** The questions of the WildINTEL form of Epicollect5, as its download names them: the number of the question, an underscore and its text, cut at 20 characters. */
export const EPICOLLECT_COLUMNS: FormatColumn[] = [
  { name: 'created_at', required: true, meaning: 'When the entry was created, in UTC: the form has no date nor time, so it is when the visit happened. It is told on the clock of the location.' },
  { name: '1_setupBy', meaning: 'Who went.' },
  { name: '2_Revision', meaning: 'The revision.', example: 'R0001' },
  { name: '3_locationID', required: true, meaning: 'The location of the visit.', example: 'WICP_02_001' },
  { name: '4_Status_of_the_came', meaning: 'How the camera was found: OK, Altered, Stolen, New site (a location made on the spot, with its camera) or Inactive site (a location with no camera that gets one).' },
  { name: '5_Batteries_Status', meaning: 'The batteries: OK or No batteries.' },
  { name: '6_Card_Status', meaning: 'The card: OK or Full Card. With the card full, the images are not counted.' },
  { name: '7_N_pictures_collect', meaning: 'How many images the card collected has. Empty when the card is full.' },
  { name: '8_Date_and_time_OK', meaning: 'Whether the date and the time of the camera were right.' },
  { name: '9_Action_after_inspe', meaning: 'What was done after the inspection: Keep the camera (the card is changed), Camera replacement, Camera removal or Site removal.' },
  { name: '10_Action_after_thef', meaning: 'What was done after a theft: Camera replacement, Site removal or None (the location stays open, with no camera).' },
  { name: '11_cameraModel, 12_Camera_name, 13_Serial_number', meaning: 'The camera put up: its model, its name and its serial number.' },
  { name: '14_cameraHeight', meaning: 'The height of the camera, in centimetres: it is kept in metres.', example: '120' },
  { name: '15_cameraDelay … 21_habitat', meaning: 'How the camera was put up: the seconds between triggers, its tilt and heading in degrees, the detection distance in metres, whether bait is used, the feature type and the habitat.' },
  { name: '22_SD_to_insert', meaning: 'The SD card left in the camera: SD 1, sd-1 or 1 — the number of the card is read.' },
  { name: '23_Calibration', meaning: 'Whether the camera was calibrated.' },
  { name: '24_Observations', meaning: 'Notes of the visit.' },
  { name: 'lat_25_Coordinates, long_25_Coordinates', meaning: 'Where the visit was noted: the only coordinates the form has. A location made from a visit (New site) takes them.' },
]

export const VISIT_FORMATS: VisitFormat[] = [
  {
    key: 'epicollect', name: 'WildINTEL Epicollect CSV',
    summary: 'The CSV downloaded from the WildINTEL form of an Epicollect5 project, as it is.',
    intro: 'Download the entries of the project as a CSV in Epicollect5 and choose the file: it is read as it is, and no column has to be matched. These are the questions of the form it reads.',
    columns: EPICOLLECT_COLUMNS,
    ignored: 'ec5_uuid, uploaded_at, created_by, title, and the accuracy and the UTM of the coordinates.',
  },
  {
    key: 'custom', name: 'Custom CSV',
    summary: 'A CSV of your own, with one row for each visit: you say which column is each field in the next step.',
    intro: 'One row for each visit. The first row has the names of the columns: their order does not matter, a column that is not used can be left empty or out, and columns with other names (in Spanish, for example) are matched in the next step. These are the columns of the template.',
    columns: CUSTOM_COLUMNS,
    template: 'visits_template.csv',
  },
]
