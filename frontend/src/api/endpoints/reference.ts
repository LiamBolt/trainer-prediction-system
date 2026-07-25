import { client } from '../axiosClient';

/**
 * Reference data (§6.15). The create/requirements forms must submit the numeric IDs
 * the backend keys on (categoryId, stationId, specializationAreaId, levelId) — not
 * free-text names — so these dropdowns are populated from here rather than hardcoded.
 */
export interface CategoryRef {
  categoryId: number;
  name: string;
  description?: string;
  isActive?: boolean;
}
export interface StationRef {
  stationId: number;
  name: string;
  regionName?: string;
  district?: string;
}
export interface SpecializationRef {
  specializationAreaId: number;
  name: string;
  disciplineGroup?: string;
}
export interface QualificationLevelRef {
  levelId: number;
  code: string;
  name: string;
  rankOrder: number;
}
export interface RegionRef {
  regionId: number;
  name: string;
  headquarters?: string;
}

export const getCategories = (): Promise<CategoryRef[]> =>
  client.get('/reference/categories').then((r) => r.data);

export const getStations = (): Promise<StationRef[]> =>
  client.get('/reference/stations').then((r) => r.data);

export const getSpecializations = (): Promise<SpecializationRef[]> =>
  client.get('/reference/specializations').then((r) => r.data);

export const getQualificationLevels = (): Promise<QualificationLevelRef[]> =>
  client.get('/reference/qualification-levels').then((r) => r.data);

export const getRegions = (): Promise<RegionRef[]> =>
  client.get('/reference/regions').then((r) => r.data);
