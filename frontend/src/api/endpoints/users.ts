import { client } from '../axiosClient';
import type { UserCreateInput, UserUpdateInput } from '@/types/api';
import type { Role, User } from '@/types/domain';

export const listUsers = (): Promise<User[]> => client.get('/users').then((r) => r.data);

export const createUser = (body: UserCreateInput): Promise<User> =>
  client.post('/users', body).then((r) => r.data);

export const updateUser = (userId: number, body: UserUpdateInput): Promise<User> =>
  client.patch(`/users/${userId}`, body).then((r) => r.data);

export const listRoles = (): Promise<Role[]> => client.get('/roles').then((r) => r.data);
