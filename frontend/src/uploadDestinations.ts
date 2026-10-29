/** The platforms a deployment can be uploaded to — Trapper is the only one for now. Each is set up in the Uploader section of the settings, and each has its
 * uploads in the Uploads dashboard: a new platform is one more line here. */
export const UPLOAD_DESTINATIONS = [{ id: 'trapper', label: 'Trapper' }] as const

export type UploadDestinationId = (typeof UPLOAD_DESTINATIONS)[number]['id']

/** What a platform is called: its label, or the id when it is one this version does not know. */
export const destinationLabel = (id: string): string => UPLOAD_DESTINATIONS.find((d) => d.id === id)?.label ?? id
