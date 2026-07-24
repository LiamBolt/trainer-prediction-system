import { client } from '../axiosClient';
import type { DashboardData } from '@/types/api';
import type { RoleName } from '@/types/domain';

export const getDashboard = (role: RoleName, userId?: number): Promise<DashboardData> =>
  client.get('/dashboard', { params: { role, userId } }).then((r) => r.data);
