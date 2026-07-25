import { client } from '../axiosClient';
import { toPaginated } from '../normalize';
import type {
  Paginated,
  PasswordReset,
  UserCreateInput,
  UserCreated,
  UserFilters,
  UserUpdateInput,
} from '@/types/api';
import type { Role, User } from '@/types/domain';

/** FR-12 — the account directory. The API paginates; the page searches and pages. */
export const listUsers = (filters: UserFilters = {}): Promise<Paginated<User>> =>
  client.get('/users', { params: filters }).then((r) => toPaginated<User>(r.data));

/** Returns the one-time temporary password, which the admin must relay out-of-band. */
export const createUser = (body: UserCreateInput): Promise<UserCreated> =>
  client.post('/users', body).then((r) => r.data);

export const updateUser = (userId: number, body: UserUpdateInput): Promise<User> =>
  client.patch(`/users/${userId}`, body).then((r) => r.data);

/** §6.10 — issue a new temporary password AND clear any lockout; shown once. */
export const resetPassword = (userId: number): Promise<PasswordReset> =>
  client.post(`/users/${userId}/reset-password`).then((r) => r.data);

export const listRoles = (): Promise<Role[]> => client.get('/roles').then((r) => r.data);
