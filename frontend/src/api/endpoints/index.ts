// Service-layer barrel (§9.1). Signatures here are final and survive the
// mock -> live backend swap (§9.3).
export * as authApi from './auth';
export * as dashboardApi from './dashboard';
export * as trainersApi from './trainers';
export * as programmesApi from './programmes';
export * as predictionsApi from './predictions';
export * as allocationsApi from './allocations';
export * as evaluationsApi from './evaluations';
export * as reportsApi from './reports';
export * as usersApi from './users';
export * as auditApi from './audit';
export * as notificationsApi from './notifications';
export * as policyApi from './policy';
export * as referenceApi from './reference';
