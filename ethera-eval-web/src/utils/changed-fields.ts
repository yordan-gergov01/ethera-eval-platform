/**
 * Diff of two flat form states for PATCH requests.
 *
 * Role: lets edit forms send only what changed.
 * Used by: features/profile/ProfileForm.tsx, features/users/EditUserForm.tsx,
 *   changed-fields.test.ts.
 * Depends on: nothing.
 * Key invariants: shallow comparison with !==, over the keys of `current` only; an empty result
 *   means nothing to save and the forms then skip the request.
 */
/**
 * The fields of `current` whose values differ from `initial`, for PATCH
 * requests that send only what changed. An empty result means nothing to save.
 */
export function changedFields<T extends object>(initial: T, current: T): Partial<T> {
  const result: Partial<T> = {};
  for (const key of Object.keys(current) as (keyof T)[]) {
    if (current[key] !== initial[key]) {
      result[key] = current[key];
    }
  }
  return result;
}
