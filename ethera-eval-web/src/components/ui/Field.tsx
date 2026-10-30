/**
 * Labelled form control with an optional hint and error message.
 *
 * Role: shared accessible form field; the caller renders the control through a render prop.
 * Used by: features LoginForm, PasswordForm, ProfileForm, CreateUserForm, EditUserForm.
 * Depends on: React useId.
 * Key invariants: the control must spread the props it receives (id, aria-invalid,
 *   aria-describedby) so label, hint and error stay connected for screen readers; aria-describedby
 *   is undefined when there is neither hint nor error.
 */
import { useId, type ReactNode } from 'react';

export interface FieldControlProps {
  id: string;
  'aria-invalid': boolean;
  'aria-describedby': string | undefined;
}

export interface FieldProps {
  label: string;
  error?: string | undefined;
  hint?: ReactNode;
  /** Renders the control with the props that connect it to the label and messages. */
  children: (props: FieldControlProps) => ReactNode;
}

/**
 * A labelled form control with an optional hint and error. The control is
 * rendered by `children`, which receives the props that connect it to the
 * label and messages.
 */
export function Field({ label, error, hint, children }: FieldProps) {
  const id = useId();
  const hintId = `${id}-hint`;
  const errorId = `${id}-error`;
  const describedBy = [hint ? hintId : null, error ? errorId : null].filter(Boolean).join(' ');

  return (
    <div className="grid gap-1.5">
      <label htmlFor={id}>{label}</label>
      {children({
        id,
        'aria-invalid': Boolean(error),
        'aria-describedby': describedBy || undefined,
      })}
      {hint && (
        <small id={hintId} className="text-xs text-gray-600">
          {hint}
        </small>
      )}
      {error && (
        <small id={errorId} className="text-xs font-medium text-red-700">
          {error}
        </small>
      )}
    </div>
  );
}
