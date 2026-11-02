/**
 * Hook for the Dataset version chosen in the URL (?version=N).
 *
 * Role: reads ?version and offers select, which writes it back.
 * Used by: features/evaluation/DatasetVersion.tsx.
 * Depends on: react-router useSearchParams.
 * Key invariants: a missing or empty ?version means the current version (`undefined`); any other
 *   value is passed on exactly as given, never parsed here, so the backend alone decides whether
 *   it names a published version (contract C-205).
 */
import { useSearchParams } from 'react-router';

/** The version chosen in the URL, or undefined for the current one, and a way to choose another. */
export function useDatasetVersionParam() {
  const [params, setParams] = useSearchParams();
  const version = params.get('version') ?? '';

  return {
    version: version === '' ? undefined : version,
    select: (target: number) => {
      setParams({ version: String(target) });
    },
  };
}
