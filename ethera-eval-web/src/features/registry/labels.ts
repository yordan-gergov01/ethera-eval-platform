/**
 * Label maps for the registry's machine values.
 *
 * Role: English labels for Model Binding roles, providers and Manifest problem types (D-012).
 * Used by: features/registry ProductDetail and replace-outcome.ts; labels.test.ts.
 * Depends on: the BindingRole and Provider types from lib/api/types (generated from the
 *   registry's response enums). The problem types restate contract §3.3: the core's problem schema
 *   carries them as plain `string` (the core never imports the registry).
 * Key invariants: every map is typed `Record<Value, Label>`; roles and providers are keyed on the
 *   generated unions, so a value the backend adds without a label fails the type check; a value
 *   the map does not know is shown raw (never hidden) so a newer backend stays readable; labels
 *   are plain text.
 */

import type { BindingRole, Provider } from '@/lib/api/types';

/** The roles a Model Binding can have (glossary value set, generated from the backend enum). */
export const BINDING_ROLE_LABELS: Record<BindingRole, string> = {
  generation: 'Generation',
  judge: 'Judge',
  embedding: 'Embedding',
};

/** The known providers of the PoC (PP-011, generated from the backend's provider set). */
export const PROVIDER_LABELS: Record<Provider, string> = {
  mock: 'Mock provider',
};

/** The fixed set of Manifest problem types (contract §3.3, C-10). */
export const PROBLEM_TYPES = [
  'malformed',
  'unsupported_syntax',
  'duplicate_key',
  'unknown_key',
  'missing',
  'wrong_type',
  'invalid_value',
  'product_mismatch',
  'unknown_provider',
  'alias',
  'provider_not_allowed',
  'duplicate_role',
  'generation_required',
  'duplicate_value',
] as const;
export type ProblemType = (typeof PROBLEM_TYPES)[number];

export const PROBLEM_TYPE_LABELS: Record<ProblemType, string> = {
  malformed: 'Not a valid document',
  unsupported_syntax: 'Unsupported YAML syntax',
  duplicate_key: 'Duplicate key',
  unknown_key: 'Unknown key',
  missing: 'Missing',
  wrong_type: 'Wrong type',
  invalid_value: 'Invalid value',
  product_mismatch: 'Names another Product',
  unknown_provider: 'Unknown provider',
  alias: 'Not a full model ID',
  provider_not_allowed: 'Provider not allowed',
  duplicate_role: 'Duplicate role',
  generation_required: 'Generation binding required',
  duplicate_value: 'Duplicate provider',
};

/** The label of a value, or the value itself when the map does not know it. */
export function labelOf(labels: Readonly<Record<string, string>>, value: string): string {
  return Object.hasOwn(labels, value) ? (labels[value] ?? value) : value;
}
