/** The EXIF fields offered when choosing the ones expected on every image, by the names ExifTool gives them, with what each one is. Any other name ExifTool
 * knows can be typed too. The capture date (DateTimeOriginal) is always expected: WildINTEL Uploader needs it, so it is not offered. */
export interface ExifTag { name: string; label: string }

export const CAPTURE_DATE_TAG: ExifTag = { name: 'DateTimeOriginal', label: 'Capture date' }

export const EXIF_TAGS: ExifTag[] = [
  { name: 'Make', label: 'Make of the camera' },
  { name: 'Model', label: 'Model of the camera (with its make)' },
  { name: 'SerialNumber', label: 'Serial number of the camera' },
  { name: 'CreateDate', label: 'Date the image was digitized' },
  { name: 'ModifyDate', label: 'Date the file was changed' },
  { name: 'ExposureTime', label: 'Exposure time' },
  { name: 'FNumber', label: 'Aperture (f-number)' },
  { name: 'ISO', label: 'ISO speed' },
  { name: 'Flash', label: 'Whether the flash fired' },
  { name: 'FocalLength', label: 'Focal length' },
  { name: 'ImageWidth', label: 'Width in pixels' },
  { name: 'ImageHeight', label: 'Height in pixels' },
  { name: 'Orientation', label: 'Orientation' },
  { name: 'Software', label: 'Firmware or software' },
  { name: 'Artist', label: 'Author' },
  { name: 'Copyright', label: 'Copyright' },
  { name: 'ImageDescription', label: 'Description (some cameras write their name here)' },
  { name: 'UserComment', label: 'User comment' },
  { name: 'GPSLatitude', label: 'GPS latitude' },
  { name: 'GPSLongitude', label: 'GPS longitude' },
  { name: 'GPSAltitude', label: 'GPS altitude' },
  { name: 'AmbientTemperature', label: 'Ambient temperature (some camera traps)' },
  { name: 'MoonPhase', label: 'Moon phase (some camera traps)' },
  { name: 'SequenceNumber', label: 'Number in the burst (some camera traps)' },
  { name: 'TriggerMode', label: 'What triggered it (some camera traps)' },
]

/** Whether a name can be the one ExifTool gives a field: letters, digits, _ and -, maybe with its group before a colon (XMP:Rating). */
export const isExifTagName = (name: string) => /^[A-Za-z][A-Za-z0-9_-]*(:[A-Za-z][A-Za-z0-9_-]*)?$/.test(name.trim())

/** What a field is, as the list says it — its own name when it is not in it. */
export const exifTagLabel = (name: string) => (name === CAPTURE_DATE_TAG.name ? CAPTURE_DATE_TAG.label : EXIF_TAGS.find((t) => t.name.toLowerCase() === name.toLowerCase())?.label ?? name)
