/**
 * The Replace Manifest form: an eval.yaml textarea prefilled with the current document.
 *
 * Role: loads the Product, lets an administrator edit the document and submits it with the version
 *   it replaces; shows refusals by field.
 * Used by: pages/ReplaceManifestPage.tsx.
 * Depends on: ./api productQueryOptions and fetchCurrentProduct, ./use-replace-manifest,
 *   ./replace-outcome, ./paths, ErrorMessage, Alert, Field, react-router Link and useNavigate, TanStack Query.
 * Key invariants: `base_version` and the text are captured ONCE when the Product first loads and
 *   change only through the explicit reload after a 409, so a background refetch can never move
 *   the base under the user's edits (INV-REG-08) or wipe them; 201 and 200 go back to the Product
 *   page; 422 MANIFEST_INVALID lists every problem as field, type label and the API's message
 *   (never the submitted values); 409 says the Manifest changed meanwhile and offers a reload that
 *   replaces the edits with the current document; 404 says the Product was not found; every text
 *   is rendered as plain text.
 */
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useState, type SubmitEvent } from 'react';
import { Link, useNavigate } from 'react-router';

import { fetchCurrentProduct, productQueryOptions } from './api';
import { productPagePath } from './paths';
import { replaceOutcome, type ProblemLine } from './replace-outcome';
import { useReplaceManifest } from './use-replace-manifest';
import { Alert } from '@/components/ui/Alert';
import { ErrorMessage } from '@/components/ui/ErrorMessage';
import { Field } from '@/components/ui/Field';
import type { Manifest } from '@/lib/api/types';

export interface ReplaceManifestFormProps {
  clientId: string;
  projectId: string;
}

/** Loads the Product, then shows the form for its current Manifest. */
export function ReplaceManifestForm({ clientId, projectId }: ReplaceManifestFormProps) {
  const { data, error, isPending } = useQuery(productQueryOptions(clientId, projectId));

  if (isPending) {
    return <p className="status">Loading…</p>;
  }
  if (error) {
    return <ErrorMessage error={error} />;
  }
  return <ManifestEditor clientId={clientId} projectId={projectId} initial={data.manifest} />;
}

interface ManifestEditorProps extends ReplaceManifestFormProps {
  /** The Manifest when the page opened; read once, never followed. */
  initial: Manifest;
}

function ManifestEditor({ clientId, projectId, initial }: ManifestEditorProps) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const mutation = useReplaceManifest(clientId, projectId);
  const [baseVersion, setBaseVersion] = useState(initial.version);
  const [text, setText] = useState(initial.document);
  const [reloadError, setReloadError] = useState<unknown>(null);
  const backTo = productPagePath(clientId, projectId);

  const submit = (event: SubmitEvent<HTMLFormElement>) => {
    event.preventDefault();
    mutation.mutate(
      { baseVersion, document: text },
      {
        onSuccess: () => {
          void navigate(backTo);
        },
      },
    );
  };

  const reload = async () => {
    setReloadError(null);
    try {
      const fresh = await fetchCurrentProduct(queryClient, clientId, projectId);
      setBaseVersion(fresh.manifest.version);
      setText(fresh.manifest.document);
      mutation.reset();
    } catch (error) {
      setReloadError(error);
    }
  };

  const outcome = mutation.error ? replaceOutcome(mutation.error) : null;
  const documentError = outcome?.kind === 'document' ? outcome.message : undefined;

  return (
    <form onSubmit={submit} noValidate className="max-w-none">
      <p className="status">
        Replaces version {baseVersion}. The current version is kept; nothing changes unless the new
        Manifest is valid.
      </p>

      {outcome?.kind === 'invalid' && <ProblemList problems={outcome.problems} />}
      {outcome?.kind === 'conflict' && (
        <Alert>
          <p className="my-0">
            The Manifest was changed by someone else since you opened this page. Nothing was
            changed. Reload to start from the current version; your edits here will be replaced.
          </p>
          <button
            type="button"
            className="mt-2"
            onClick={() => {
              void reload();
            }}
          >
            Reload the current Manifest
          </button>
        </Alert>
      )}
      {outcome?.kind === 'not-found' && (
        <Alert>
          <p className="my-0">This Product was not found.</p>
        </Alert>
      )}
      {outcome?.kind === 'other' && <ErrorMessage error={outcome.error} />}
      {reloadError !== null && <ErrorMessage error={reloadError} />}

      <fieldset disabled={mutation.isPending} className="max-w-none">
        <Field label="eval.yaml" error={documentError}>
          {(props) => (
            <textarea
              {...props}
              name="document"
              rows={18}
              spellCheck={false}
              className="font-mono text-xs"
              value={text}
              onChange={(event) => {
                setText(event.target.value);
              }}
            />
          )}
        </Field>
        <div className="flex items-center gap-4">
          <button type="submit">
            {mutation.isPending ? 'Validating…' : 'Validate and replace'}
          </button>
          <Link to={backTo}>Cancel</Link>
        </div>
      </fieldset>
    </form>
  );
}

interface ProblemListProps {
  problems: readonly ProblemLine[];
}

/** The problems of a refused Manifest, one line each: field, type label, message. */
function ProblemList({ problems }: ProblemListProps) {
  const count = problems.length === 1 ? '1 problem' : `${String(problems.length)} problems`;
  return (
    <Alert>
      <p className="my-0 font-medium">The Manifest was refused — {count}. Nothing was changed.</p>
      <ul className="mt-2 mb-0 list-disc pl-5">
        {problems.map(({ field, type, typeLabel, message }) => (
          // The API lists each (field, type) pair at most once (contract §3.3).
          <li key={`${field}|${type}`}>
            <code>{field}</code> — <strong>{typeLabel}</strong>: {message}
          </li>
        ))}
      </ul>
    </Alert>
  );
}
