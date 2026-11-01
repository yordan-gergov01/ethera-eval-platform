/**
 * Loads one Product and shows its current Manifest.
 *
 * Role: detail view of the registry feature: header line (client, Manifest version, changed at
 *   and by), Model Bindings table, allowed providers and the eval.yaml text.
 * Used by: pages/ProductPage.tsx.
 * Depends on: ./api productQueryOptions, ./labels, ./paths, ErrorMessage, useAuth().can,
 *   react-router Link, TanStack Query.
 * Key invariants: shows only what exists in slice 001 (PP-009: no Baseline, no Eval Run history,
 *   not even as placeholders); the eval.yaml text is rendered as plain text in a <pre>, never as
 *   HTML; roles and providers go through their label maps (PP-011), model IDs are shown as
 *   identifiers; the "Replace Manifest" link shows only with manifests:write (cosmetic: the route
 *   guard and the backend also check); a missing Product and a non-member's Product look the
 *   same (the backend answers both with PRODUCT_NOT_FOUND).
 */
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router';

import { productQueryOptions } from './api';
import { BINDING_ROLE_LABELS, PROVIDER_LABELS, labelOf } from './labels';
import { replaceManifestPagePath } from './paths';
import { ErrorMessage } from '@/components/ui/ErrorMessage';
import { useAuth } from '@/providers/auth/auth-context';

const formatDate = (value: string) => new Date(value).toLocaleString();

export interface ProductDetailProps {
  clientId: string;
  projectId: string;
}

/** Loads one Product and shows its current Manifest. */
export function ProductDetail({ clientId, projectId }: ProductDetailProps) {
  const { can } = useAuth();
  const { data, error, isPending } = useQuery(productQueryOptions(clientId, projectId));

  if (isPending) {
    return <p className="status">Loading…</p>;
  }
  if (error) {
    return <ErrorMessage error={error} />;
  }
  const { manifest } = data;

  return (
    <>
      <h1>{data.project_id}</h1>
      <p className="status">
        Client {data.client_id} · Manifest version {manifest.version} · changed{' '}
        {formatDate(manifest.created_at)} by {manifest.created_by}
      </p>
      {can('manifests:write') && (
        <p>
          <Link to={replaceManifestPagePath(data.client_id, data.project_id)}>
            Replace Manifest
          </Link>
        </p>
      )}

      <h2>Model Bindings</h2>
      <div className="overflow-x-auto">
        <table>
          <thead>
            <tr>
              <th scope="col">Role</th>
              <th scope="col">Provider</th>
              <th scope="col">Model ID</th>
            </tr>
          </thead>
          <tbody>
            {manifest.bindings.map((binding) => (
              <tr key={binding.role}>
                <td>{labelOf(BINDING_ROLE_LABELS, binding.role)}</td>
                <td>{labelOf(PROVIDER_LABELS, binding.provider)}</td>
                <td>
                  <code>{binding.model}</code>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <h2>Allowed providers</h2>
      <ul className="list-disc pl-6 text-sm">
        {manifest.allowed_providers.map((provider) => (
          <li key={provider}>{labelOf(PROVIDER_LABELS, provider)}</li>
        ))}
      </ul>

      <h2>eval.yaml (version {manifest.version})</h2>
      <pre className="overflow-x-auto rounded-md border border-gray-200 bg-gray-50 p-4">
        {manifest.document}
      </pre>
    </>
  );
}
