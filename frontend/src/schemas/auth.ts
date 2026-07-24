import { z } from 'zod';

/** Sign-in form (FR-01). Validation on blur and submit (§9.2). */
export const loginSchema = z.object({
  username: z.string().min(1, 'Enter your username.'),
  password: z.string().min(1, 'Enter your password.'),
});

export type LoginForm = z.infer<typeof loginSchema>;
