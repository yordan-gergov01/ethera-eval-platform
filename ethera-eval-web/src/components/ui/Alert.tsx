/**
 * Red error box that screen readers announce when it appears.
 *
 * Role: shared presentational wrapper for error messages.
 * Used by: components/ui/ErrorMessage.tsx, features/auth/LoginForm.tsx.
 * Depends on: React ReactNode; Tailwind utility classes (template_web D-007).
 * Key invariants: role="alert" is what makes screen readers announce the message; keep it.
 */
import type { ReactNode } from 'react';

export interface AlertProps {
  children: ReactNode;
}

/** An error message box, announced to screen readers when it appears. */
export function Alert({ children }: AlertProps) {
  return (
    <div
      role="alert"
      className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800"
    >
      {children}
    </div>
  );
}
