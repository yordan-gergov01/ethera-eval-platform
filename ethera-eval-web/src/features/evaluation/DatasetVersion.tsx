/**
 * Loads one Dataset version of a Product and lists its Goldens.
 *
 * Role: body of the Dataset page: a version selector built from the summary's `versions`, the
 *   version's publication time and Golden count, and the table of its Goldens.
 * Used by: pages/DatasetPage.tsx (DatasetVersion); DatasetVersion.test.tsx (DatasetVersionView,
 *   GoldensTable).
 * Depends on: ./api, ./labels, ./paths, ./use-dataset-version-param, ErrorMessage, ApiError,
 *   react-router Link, TanStack Query.
 * Key invariants: without ?version the current version of the summary is shown; the selector
 *   writes ?version; DATASET_VERSION_NOT_FOUND is a not-found message with a link to the current
 *   version, DATASET_NOT_FOUND a quiet "No Dataset" note, every other error goes to
 *   ErrorMessage; branches on the error `code`, never on `detail`; Golden input, context and rule
 *   are untrusted text rendered as plain text, never HTML; decisions, failure types and owners
 *   go through their label maps; a missing owner shows as a dash; a Golden's expected numbers
 *   show under its rule as written ("Numbers: 4.90"), and not at all when it has none (D-026).
 */
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router';

import { datasetSummaryQueryOptions, datasetVersionQueryOptions } from './api';
import {
  DECISION_LABELS,
  FAILURE_TYPE_LABELS,
  GOLDEN_OWNER_LABELS,
  goldenCount,
  labelOf,
} from './labels';
import { datasetPagePath } from './paths';
import { useDatasetVersionParam } from './use-dataset-version-param';
import { ErrorMessage } from '@/components/ui/ErrorMessage';
import { ApiError } from '@/lib/api/errors';
import type { DatasetSummary, DatasetVersion as DatasetVersionData, Golden } from '@/lib/api/types';

const formatDate = (value: string) => new Date(value).toLocaleString();

const hasCode = (error: unknown, code: string) => error instanceof ApiError && error.code === code;

export interface DatasetVersionProps {
  clientId: string;
  projectId: string;
}

/** Loads the Dataset version chosen in the URL (the current one by default) and lists it. */
export function DatasetVersion({ clientId, projectId }: DatasetVersionProps) {
  const { version, select } = useDatasetVersionParam();
  const summary = useQuery(datasetSummaryQueryOptions(clientId, projectId));
  const chosen = version ?? (summary.data ? String(summary.data.current_version) : undefined);
  const detail = useQuery({
    ...datasetVersionQueryOptions(clientId, projectId, chosen ?? ''),
    enabled: chosen !== undefined,
  });

  if (summary.isPending) {
    return <p className="status">Loading…</p>;
  }
  if (hasCode(summary.error, 'DATASET_NOT_FOUND')) {
    return <p className="status">No Dataset.</p>;
  }
  if (summary.error) {
    return <ErrorMessage error={summary.error} />;
  }
  if (hasCode(detail.error, 'DATASET_VERSION_NOT_FOUND')) {
    return (
      <p>
        Dataset version not found.{' '}
        <Link to={datasetPagePath(clientId, projectId)}>Show the current version</Link>.
      </p>
    );
  }
  if (detail.error) {
    return <ErrorMessage error={detail.error} />;
  }
  if (detail.isPending) {
    return <p className="status">Loading…</p>;
  }
  return <DatasetVersionView summary={summary.data} version={detail.data} onSelect={select} />;
}

export interface DatasetVersionViewProps {
  summary: DatasetSummary;
  version: DatasetVersionData;
  onSelect: (version: number) => void;
}

/** Shows a loaded Dataset version with the selector of every published version. */
export function DatasetVersionView({ summary, version, onSelect }: DatasetVersionViewProps) {
  return (
    <>
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2 text-sm text-gray-600">
        <span>Client {version.client_id}</span>
        <label className="flex items-center gap-2 font-normal text-gray-600">
          Version
          <select
            className="w-auto py-1"
            value={String(version.number)}
            onChange={(event) => {
              onSelect(Number(event.target.value));
            }}
          >
            {summary.versions.map(({ number }) => (
              <option key={number} value={String(number)}>
                {number === summary.current_version ? `${String(number)} (current)` : number}
              </option>
            ))}
          </select>
        </label>
        <span>published {formatDate(version.published_at)}</span>
        <span>{goldenCount(version.goldens.length)}</span>
      </div>
      <GoldensTable goldens={version.goldens} />
    </>
  );
}

export interface GoldensTableProps {
  goldens: readonly Golden[];
}

/** The Goldens of one Dataset version, in position order; every text is plain text. */
export function GoldensTable({ goldens }: GoldensTableProps) {
  return (
    <div className="mt-4 overflow-x-auto">
      <table>
        <thead>
          <tr>
            <th scope="col">#</th>
            <th scope="col">Input</th>
            <th scope="col">Expected decision</th>
            <th scope="col">Rule</th>
            <th scope="col">Failure type</th>
            <th scope="col">Owner</th>
          </tr>
        </thead>
        <tbody>
          {goldens.map((golden) => (
            <tr key={golden.position} className="align-top">
              <td>{golden.position}</td>
              <td>
                {golden.input}
                {golden.context !== null && (
                  <p className="mt-1 mb-0 text-xs text-gray-600">Context: {golden.context}</p>
                )}
              </td>
              <td>
                <span className="rounded bg-gray-100 px-1.5 py-0.5 whitespace-nowrap">
                  {labelOf(DECISION_LABELS, golden.expected_decision)}
                </span>
              </td>
              <td>
                {golden.rule}
                {golden.expected_numbers.length > 0 && (
                  <p className="mt-1 mb-0 text-xs text-gray-600">
                    Numbers: {golden.expected_numbers.join(', ')}
                  </p>
                )}
              </td>
              <td>{labelOf(FAILURE_TYPE_LABELS, golden.failure_type)}</td>
              <td>
                {golden.owner === null ? '—' : labelOf(GOLDEN_OWNER_LABELS, golden.owner)}
                {golden.unfixable_by_code && (
                  <p className="mt-1 mb-0 text-xs text-gray-600">Unfixable by code</p>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
