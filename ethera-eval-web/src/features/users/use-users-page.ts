/**
 * Hook for the current page of users, with the page number kept in the URL.
 *
 * Role: reads ?page=N, fetches that page and offers goTo.
 * Used by: features/users/UsersList.tsx.
 * Depends on: ./api usersPageQueryOptions and PAGE_SIZE, react-router useSearchParams.
 * Key invariants: a missing or invalid ?page means page 1; page 1 is written as no parameter;
 *   `pages` is at least 1, also for an empty list.
 */
import { useQuery } from '@tanstack/react-query';
import { useSearchParams } from 'react-router';

import { PAGE_SIZE, usersPageQueryOptions } from './api';

function pageFromParams(params: URLSearchParams): number {
  const page = Number(params.get('page') ?? '1');
  return Number.isInteger(page) && page >= 1 ? page : 1;
}

/** The current page of users; the page number is kept in the URL (?page=2). */
export function useUsersPage() {
  const [params, setParams] = useSearchParams();
  const page = pageFromParams(params);
  const query = useQuery(usersPageQueryOptions((page - 1) * PAGE_SIZE));
  const pages = query.data ? Math.max(1, Math.ceil(query.data.total / PAGE_SIZE)) : 1;

  return {
    query,
    page,
    pages,
    goTo: (target: number) => {
      setParams(target === 1 ? {} : { page: String(target) });
    },
  };
}
