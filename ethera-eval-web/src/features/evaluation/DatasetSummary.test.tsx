/**
 * Unit tests for the Dataset summary's rendering.
 *
 * Role: proves the summary shows the current version, its Golden count, all six failure types in
 *   order with their labels and counts (zeros included) and the link to the Dataset page; and that
 *   the DatasetSummary container renders nothing for PRODUCT_NOT_FOUND, a quiet "No Dataset" for
 *   DATASET_NOT_FOUND and ErrorMessage for any other error.
 * Used by: Vitest.
 * Depends on: ./DatasetSummary (DatasetSummary, DatasetSummaryView), ./api
 *   datasetSummaryQueryOptions, react-dom/server renderToStaticMarkup, react-router MemoryRouter,
 *   TanStack Query; the global fetch and window config stubbed (the backend is external).
 * Key invariants: rendered to static markup in the node test environment, so no DOM library is
 *   needed; the Golden count comes from the current version's entry, not from an older one. The
 *   container cases fill the cache through the real query options, `api` client and error
 *   mapping from a stubbed fetch, then render; the test client sets `retry: false` and
 *   `retryOnMount: false` so a cached error is rendered instead of refetched.
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderToStaticMarkup } from 'react-dom/server';
import { MemoryRouter } from 'react-router';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { datasetSummaryQueryOptions } from './api';
import { DatasetSummary as DatasetSummaryContainer, DatasetSummaryView } from './DatasetSummary';
import type { DatasetSummary } from '@/lib/api/types';

const SUMMARY: DatasetSummary = {
  client_id: 'acme',
  project_id: 'support bot',
  current_version: 2,
  versions: [
    { number: 1, published_at: '2026-11-01T09:00:00+00:00', golden_count: 19 },
    { number: 2, published_at: '2026-11-02T09:00:00+00:00', golden_count: 21 },
  ],
  failure_type_counts: {
    date_math: 5,
    refund_rules: 4,
    invented_facts: 0,
    out_of_docs: 3,
    retrieval_miss: 2,
    order_status_tool: 7,
  },
};

const render = (summary: DatasetSummary) =>
  renderToStaticMarkup(
    <MemoryRouter>
      <DatasetSummaryView summary={summary} />
    </MemoryRouter>,
  );

describe('DatasetSummaryView', () => {
  it('shows the current version, its Golden count and the link to the Dataset page', () => {
    const html = render(SUMMARY);

    expect(html).toContain('Version 2');
    expect(html).toContain('21 Goldens');
    expect(html).not.toContain('19 Goldens');
    expect(html).toContain('href="/products/acme/support%20bot/dataset"');
  });

  it('lists every failure type in order with its label and count, zeros included', () => {
    const rows = [...render(SUMMARY).matchAll(/<tr><td>([^<]*)<\/td><td>(\d+)<\/td><\/tr>/g)].map(
      ([, label, count]) => [label, count],
    );

    expect(rows).toEqual([
      ['Date math', '5'],
      ['Refund rules', '4'],
      ['Invented facts', '0'],
      ['Out of documents', '3'],
      ['Retrieval miss', '2'],
      ['Order status (tool)', '7'],
    ]);
  });
});

function problem(status: number, code: string) {
  return new Response(JSON.stringify({ title: 'Error', status, detail: 'Refused.', code }), {
    status,
    headers: { 'Content-Type': 'application/problem+json' },
  });
}

describe('DatasetSummary (container)', () => {
  beforeEach(() => {
    vi.stubGlobal('window', { __APP_CONFIG__: { backendUrl: 'http://backend:8000' } });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  /** Fetches the summary through a fetch answering `response`, then renders the container. */
  async function renderAnswering(response: Response) {
    vi.stubGlobal(
      'fetch',
      vi.fn<typeof fetch>(() => Promise.resolve(response)),
    );
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, retryOnMount: false } },
    });
    await queryClient
      .query(datasetSummaryQueryOptions('acme', 'support-bot'))
      .catch(() => undefined);
    return renderToStaticMarkup(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <DatasetSummaryContainer clientId="acme" projectId="support-bot" />
        </MemoryRouter>
      </QueryClientProvider>,
    );
  }

  it('renders nothing when the Product is not found, which the Product detail reports', async () => {
    expect(await renderAnswering(problem(404, 'PRODUCT_NOT_FOUND'))).toBe('');
  });

  it('shows a quiet "No Dataset" note when the Product has no Dataset', async () => {
    const html = await renderAnswering(problem(404, 'DATASET_NOT_FOUND'));

    expect(html).toContain('No Dataset.');
    expect(html).not.toContain('role="alert"');
  });

  it('shows any other error through ErrorMessage', async () => {
    const html = await renderAnswering(problem(403, 'PERMISSION_DENIED'));

    expect(html).toContain('You are not allowed to do this.');
    expect(html).not.toContain('No Dataset.');
  });

  it('shows the loaded summary', async () => {
    const html = await renderAnswering(
      new Response(JSON.stringify(SUMMARY), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    );

    expect(html).toContain('Version 2');
  });
});
