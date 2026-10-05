/** Who can own, or publish, WildINTEL images — the institutions wildintel-publisher already
 * knows (its CAMTRAPDP_RIGHTS_HOLDER_OPTIONS, and WildINTEL itself as the publisher). They
 * are suggestions: the fields they feed are open, so any other name can be typed. */
export const ENTITIES: { title: string; website: string }[] = [
  { title: 'WildINTEL', website: 'https://wildintel.eu/' },
  { title: 'Institute of Nature Conservation PAS', website: 'https://www.iop.krakow.pl/' },
  { title: 'University of Huelva', website: 'https://www.uhu.es/' },
  { title: 'University of South-Eastern Norway', website: 'https://www.usn.no/' },
  { title: 'German Centre for Integrative Biodiversity Research', website: 'https://www.idiv.de/' },
  { title: 'Spanish National Research Council', website: 'https://www.csic.es/' },
  { title: 'Massachusetts Institute of Technology', website: 'https://www.mit.edu/' },
  { title: 'Spanish Node of the Global Biodiversity Information Facility', website: 'https://www.gbif.es/' },
]

/** The areas WildINTEL's camera traps cover — suggestions for where the images were taken; any other can be typed. */
export const COVERAGE_AREAS: string[] = [
  'Doñana National Park',
  'Tatra National Park',
  'Hardangervidda National Park',
  'Lower Oder Valley National Park',
]
