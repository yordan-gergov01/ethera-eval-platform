/**
 * Loads a Product's Dataset summary and shows it.
 *
 * Role: the Dataset block of the Product page: current version, its publication time, its Golden
 *   count, the count per failure type and the link to the Dataset page.
 * Used by: pages/ProductPage.tsx (DatasetSummary); DatasetSummary.test.tsx (DatasetSummaryView).
 * Depends on: ./api datasetSummaryQueryOptions, ./labels, ./paths, ErrorMessage, ApiError,
 *   react-router Link, TanStack Query.
 * Key invariants: DATASET_NOT_FOUND is a quiet "No Dataset" note, not an error; PRODUCT_NOT_FOUND
 *   renders nothing, because the Product detail beside it already reports it; branches on the
 *   error `code`, never on `detail`; all six failure types are listed in FAILURE_TYPES order,
 *   zeros included; the Golden count is that of the current version's entry in `versions`; only
 *   `published_at` is shown (the contract carries no publisher); everything is plain text.
 */
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router';

import { datasetSummaryQueryOptions } from './api';
import { FAILURE_TYPES, FAILURE_TYPE_LABELS, goldenCount } from './labels';
import { datasetPagePath } from './paths';
import { ErrorMessage } from '@/components/ui/ErrorMessage';
import { ApiError } from '@/lib/api/errors';
import type { DatasetSummary as DatasetSummaryData } from '@/lib/api/types';

const formatDate = (value: string) => new Date(value).toLocaleString();

export interface DatasetSummaryProps {
  clientId: string;
  projectId: string;
}

/** Loads a Product's Dataset summary and shows it, or a quiet note when there is none. */
export function DatasetSummary({ clientId, projectId }: DatasetSummaryProps) {
  const { data, error, isPending } = useQuery(datasetSummaryQueryOptions(clientId, projectId));

  if (isPending) {
    return <p className="status">Loading the Dataset…</p>;
  }
  if (error instanceof ApiError && error.code === 'PRODUCT_NOT_FOUND') {
    return null;
  }
  if (error instanceof ApiError && error.code === 'DATASET_NOT_FOUND') {
    return (
      <>
        <h2>Dataset</h2>
        <p className="status">No Dataset.</p>
      </>
    );
  }
  if (error) {
    return <ErrorMessage error={error} />;
  }
  return <DatasetSummaryView summary={data} />;
}

export interface DatasetSummaryViewProps {
  summary: DatasetSummaryData;
}

/** Shows a loaded Dataset summary. */
export function DatasetSummaryView({ summary }: DatasetSummaryViewProps) {
  const current = summary.versions.find((version) => version.number === summary.current_version);

  return (
    <>
      <h2>Dataset</h2>
      <p className="status">
        Version {summary.current_version}
        {current && (
          <>
            {' '}
            · published {formatDate(current.published_at)} · {goldenCount(current.golden_count)}
          </>
        )}{' '}
        · <Link to={datasetPagePath(summary.client_id, summary.project_id)}>Open Dataset</Link>
      </p>
      <div className="overflow-x-auto">
        <table>
          <thead>
            <tr>
              <th scope="col">Failure type</th>
              <th scope="col">Goldens</th>
            </tr>
          </thead>
          <tbody>
            {FAILURE_TYPES.map((failureType) => (
              <tr key={failureType}>
                <td>{FAILURE_TYPE_LABELS[failureType]}</td>
                <td>{summary.failure_type_counts[failureType]}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
