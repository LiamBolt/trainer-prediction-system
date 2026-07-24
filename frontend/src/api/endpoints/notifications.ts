import { client } from '../axiosClient';
import type { Notification } from '@/types/domain';

export const listNotifications = (recipientId?: number): Promise<Notification[]> =>
  client.get('/notifications', { params: { recipientId } }).then((r) => r.data);

export const markAllNotificationsRead = (recipientId?: number): Promise<{ ok: boolean }> =>
  client.post('/notifications/read-all', null, { params: { recipientId } }).then((r) => r.data);

export const markNotificationRead = (notificationId: number): Promise<Notification> =>
  client.patch(`/notifications/${notificationId}/read`).then((r) => r.data);
