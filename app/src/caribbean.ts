/** Source-country facts remain distinct; the picker exposes one regional market. */
export const caribbeanCountryNames: Record<string, string> = {
  AG: 'Antigua and Barbuda',
  AI: 'Anguilla',
  AW: 'Aruba',
  BB: 'Barbados',
  BL: 'Saint Barthélemy',
  BQ: 'Caribbean Netherlands',
  BS: 'Bahamas',
  BZ: 'Belize',
  CU: 'Cuba',
  CW: 'Curaçao',
  DM: 'Dominica',
  DO: 'Dominican Republic',
  GD: 'Grenada',
  GP: 'Guadeloupe',
  GY: 'Guyana',
  HT: 'Haiti',
  JM: 'Jamaica',
  KN: 'Saint Kitts and Nevis',
  KY: 'Cayman Islands',
  LC: 'Saint Lucia',
  MF: 'Saint Martin',
  MQ: 'Martinique',
  MS: 'Montserrat',
  PR: 'Puerto Rico',
  SR: 'Suriname',
  SX: 'Sint Maarten',
  TC: 'Turks and Caicos Islands',
  TT: 'Trinidad and Tobago',
  VC: 'Saint Vincent and the Grenadines',
  VG: 'British Virgin Islands',
  VI: 'US Virgin Islands',
  CARIBBEANREGIONAL: 'Caribbean (regional)',
}

export const caribbeanCountries = Object.keys(caribbeanCountryNames)

export function selectableMarket(country: string) {
  return Object.hasOwn(caribbeanCountryNames, country) ? 'CARIBBEAN' : country
}
