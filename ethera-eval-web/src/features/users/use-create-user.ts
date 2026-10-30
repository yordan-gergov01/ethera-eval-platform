/**
 * Mutation hook that creates a user.
 *
 * Role: posts the new user and invalidates every users query.
 * Used by: features/users/CreateUserForm.tsx.
 * Depends on: ./api createUser and USERS_KEY, TanStack Query.
 * Key invariants: never retried (lib/query-client.ts): a retried POST could create the user twice
 *   or answer with a confusing 409.
 */
import { useMutation, useQueryClient } from '@tanstack/react-query';

import { USERS_KEY, createUser } from './api';

/** Creates a user and refreshes the user list. */
export function useCreateUser() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: createUser,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: USERS_KEY });
    },
  });
}
