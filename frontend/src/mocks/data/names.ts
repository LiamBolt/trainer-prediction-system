/**
 * Ugandan name pools (§8.7). Given names split by gender so the roster reads
 * ~30% women; surnames are drawn from across the country's language groups.
 */
import type { Rng } from '../seed';

export const FEMALE_GIVEN = [
  'Grace',
  'Sarah',
  'Aisha',
  'Betty',
  'Immaculate',
  'Robinah',
  'Prossy',
  'Zainab',
  'Harriet',
  'Norah',
  'Specioza',
  'Justine',
];

export const MALE_GIVEN = [
  'Joseph',
  'Moses',
  'Hassan',
  'Ronald',
  'Patrick',
  'Godfrey',
  'Fredrick',
  'Ibrahim',
  'Denis',
  'Wilson',
  'Julius',
  'Emmanuel',
];

export const SURNAMES = [
  'Okello',
  'Nabirye',
  'Mugisha',
  'Kyaligonza',
  'Ssentongo',
  'Wanyama',
  'Draru',
  'Byaruhanga',
  'Opio',
  'Namubiru',
  'Otim',
  'Businge',
  'Achieng',
  'Kizza',
  'Adiru',
  'Tumwine',
  'Masaba',
  'Candia',
  'Lubega',
  'Amuge',
  'Ojok',
  'Nakato',
  'Wekesa',
  'Atuhaire',
  'Andama',
  'Nalwoga',
  'Ekwaru',
  'Kabagambe',
  'Odongo',
  'Ainembabazi',
];

export interface GeneratedName {
  given: string;
  surname: string;
  fullName: string; // "Grace Nabirye" (rank prepended elsewhere)
  isFemale: boolean;
}

export function makeName(rng: Rng, femaleShare = 0.3): GeneratedName {
  const isFemale = rng.bool(femaleShare);
  const given = rng.pick(isFemale ? FEMALE_GIVEN : MALE_GIVEN);
  const surname = rng.pick(SURNAMES);
  return { given, surname, fullName: `${given} ${surname}`, isFemale };
}

/** Email from name: firstname.surname@upf.go.ug (§8.8). */
export function makeEmail(given: string, surname: string): string {
  return `${given}.${surname}`.toLowerCase().replace(/[^a-z.]/g, '') + '@upf.go.ug';
}
