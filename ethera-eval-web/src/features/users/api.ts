/**
 * Queries and backend calls of the users feature.
 *
 * Role: query options for the user list, one user and the roles, plus the create and update calls.
 * Used by: features/users CreateUserForm, EditUserForm, UserDetail, use-create-user,
 *   use-update-user, use-users-page.
 * Depends on: api from lib/api/http, TanStack Query; GET/POST /api/v1/users, GET/PATCH
 *   /api/v1/users/{id}, GET /api/v1/roles.
 * Key invariants: every users query key starts with USERS_KEY so one invalidation refreshes them
 *   all; 20 users per page; ids are URL-encoded; roles stay fresh for 5 minutes; the list keeps the
 *   previous page as placeholder while the next loads.
 */
import { keepPreviousData, queryOptions } from '@tanstack/react-query';

import { api } from '@/lib/api/http';
import type { Role, User, UserAdminUpdate, UserCreate, UserPage } from '@/lib/api/types';

export const PAGE_SIZE = 20;

/** Every cached users query starts with this key, so one invalidation refreshes them all. */
export const USERS_KEY = ['users'] as const;

export const usersPageQueryOptions = (offset: number) =>
  queryOptions({
    queryKey: [...USERS_KEY, 'page', offset],
    queryFn: ({ signal }) =>
      api.get<UserPage>('/api/v1/users', { query: { limit: PAGE_SIZE, offset }, signal }),
    // Keep showing the current page while the next one loads.
    placeholderData: keepPreviousData,
  });

export const userQueryOptions = (id: string) =>
  queryOptions({
    queryKey: [...USERS_KEY, 'detail', id],
    queryFn: ({ signal }) => api.get<User>(`/api/v1/users/${encodeURIComponent(id)}`, { signal }),
  });

export const rolesQueryOptions = queryOptions({
  queryKey: ['roles'],
  queryFn: ({ signal }) => api.get<Role[]>('/api/v1/roles', { signal }),
  staleTime: 5 * 60_000,
});

export function createUser(body: UserCreate) {
  return api.post<User>('/api/v1/users', { json: body });
}

export function updateUser(id: string, changes: UserAdminUpdate) {
  return api.patch<User>(`/api/v1/users/${encodeURIComponent(id)}`, { json: changes });
}
