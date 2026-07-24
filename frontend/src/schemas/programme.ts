import { z } from 'zod';

/**
 * FR-04 — create a training request. Submit is blocked without a category and at
 * least one date; the disabled Submit tooltip names the missing field.
 */
export const programmeCreateSchema = z
  .object({
    title: z.string().min(3, 'Enter a title for this training request.'),
    category: z.string().min(1, 'Choose a category.'),
    startDate: z.string().min(1, 'Choose a start date.'),
    endDate: z.string().min(1, 'Choose an end date.'),
    location: z.string().min(1, 'Enter a location.'),
  })
  .refine((v) => !v.endDate || !v.startDate || v.endDate >= v.startDate, {
    message: 'The end date cannot be before the start date.',
    path: ['endDate'],
  });

export type ProgrammeCreateForm = z.infer<typeof programmeCreateSchema>;

/** FR-05 — define requirements. Prediction is blocked without a specialisation. */
export const requirementsSchema = z.object({
  requiredSpecialization: z.string().min(1, 'Choose the specialisation this course requires.'),
  minimumExperience: z.coerce.number().min(0, 'Enter 0 or more years.').max(40),
  minimumQualification: z.string().nullable(),
});

export type RequirementsForm = z.infer<typeof requirementsSchema>;
