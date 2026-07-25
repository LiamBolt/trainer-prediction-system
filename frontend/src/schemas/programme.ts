import { z } from 'zod';

/**
 * FR-04 — create a training request. The category and location are chosen from
 * reference data, so the fields hold the numeric IDs (as strings from the Select)
 * that the backend keys on. Title min length matches the backend's (5).
 */
export const programmeCreateSchema = z
  .object({
    title: z.string().min(5, 'Enter a title of at least 5 characters.'),
    categoryId: z.string().min(1, 'Choose a category.'),
    startDate: z.string().min(1, 'Choose a start date.'),
    endDate: z.string().min(1, 'Choose an end date.'),
    stationId: z.string().min(1, 'Choose a location.'),
  })
  .refine((v) => !v.endDate || !v.startDate || v.endDate >= v.startDate, {
    message: 'The end date cannot be before the start date.',
    path: ['endDate'],
  });

export type ProgrammeCreateForm = z.infer<typeof programmeCreateSchema>;

/** FR-05 — define requirements. Prediction is blocked without a specialisation.
 *  Fields hold reference IDs (as strings); the minimum qualification is optional. */
export const requirementsSchema = z.object({
  requiredSpecializationAreaId: z.string().min(1, 'Choose the specialisation this course requires.'),
  minimumExperience: z.coerce.number().min(0, 'Enter 0 or more years.').max(40),
  minimumQualificationLevelId: z.string().nullable(),
});

export type RequirementsForm = z.infer<typeof requirementsSchema>;
