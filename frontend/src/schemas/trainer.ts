import { z } from 'zod';

/**
 * FR-02 — trainer self-service profile. Rank, station, and contact number cannot
 * be saved blank.
 */
export const trainerProfileSchema = z.object({
  policeRank: z.string().min(1, 'Choose your rank.'),
  station: z.string().min(1, 'Choose your station.'),
  yearsExperience: z.coerce.number().min(0, 'Enter 0 or more years.').max(45),
  contactNumber: z.string().min(13, 'Enter a valid contact number.'),
  availabilityStatus: z.string().min(1),
});

export type TrainerProfileForm = z.infer<typeof trainerProfileSchema>;
