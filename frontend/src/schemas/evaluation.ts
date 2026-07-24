import { z } from 'zod';

/** FR-10 — record a performance evaluation. Comments are required (min 20 chars). */
export const evaluationSchema = z.object({
  scoreAwarded: z
    .number({ invalid_type_error: 'Award a score.' })
    .min(1, 'The lowest score is 1.0.')
    .max(5, 'The highest score is 5.0.'),
  evaluatorComments: z
    .string()
    .min(20, 'Please write at least 20 characters so the record is useful later.'),
  evaluationDate: z.string().min(1, 'Choose the evaluation date.'),
});

export type EvaluationForm = z.infer<typeof evaluationSchema>;

/** FR-09 — a trainer must give a reason when declining. */
export const declineSchema = z.object({
  reason: z.string().min(10, 'Please give a reason so the Administrator can reallocate.'),
});

export type DeclineForm = z.infer<typeof declineSchema>;
