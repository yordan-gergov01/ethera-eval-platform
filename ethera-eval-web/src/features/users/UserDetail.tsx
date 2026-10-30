/**
 * Loads one user and shows its details and edit form.
 *
 * Role: detail view of the users feature.
 * Used by: pages/UserDetailPage.tsx.
 * Depends on: ./api userQueryOptions, ./EditUserForm, ErrorMessage, TanStack Query.
 * Key invariants: EditUserForm is keyed by the user id so its form state resets when another user
 *   loads; dates use the browser's locale.
 */
import { useQuery } from '@tanstack/react-query';

import { userQueryOptions } from './api';
import { EditUserForm } from './EditUserForm';
import { ErrorMessage } from '@/components/ui/ErrorMessage';

const formatDate = (value: string) => new Date(value).toLocaleString();

export interface UserDetailProps {
  userId: string;
}

/** Loads one user and shows its details and edit form. */
export function UserDetail({ userId }: UserDetailProps) {
  const { data, error, isPending } = useQuery(userQueryOptions(userId));

  if (isPending) {
    return <p className="status">Loading…</p>;
  }
  if (error) {
    return <ErrorMessage error={error} />;
  }
  return (
    <>
      <dl className="details">
        <dt>Username</dt>
        <dd>{data.username}</dd>
        <dt>Created</dt>
        <dd>{formatDate(data.created_at)}</dd>
        <dt>Updated</dt>
        <dd>{formatDate(data.updated_at)}</dd>
      </dl>
      <EditUserForm key={data.id} user={data} />
    </>
  );
}
