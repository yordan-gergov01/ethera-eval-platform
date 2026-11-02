/**
 * Unit tests for the Dataset version's rendering.
 *
 * Role: proves the Goldens table shows every Golden with labelled decision, failure type and
 *   owner, context under its input, the "unfixable by code" marker, and that Golden text is
 *   rendered as plain text, never HTML; and that the version selector lists every published
 *   version with the current one marked and the shown one selected; and that the DatasetVersion
 *   container shows "No Dataset" for DATASET_NOT_FOUND, a not-found message linking to the current
 *   version for DATASET_VERSION_NOT_FOUND, ErrorMessage for any other error, and the current
 *   version when ?version is absent.
 * Used by: Vitest.
 * Depends on: ./DatasetVersion (DatasetVersion, DatasetVersionView, GoldensTable), ./api query
 *   options, react-dom/server renderToStaticMarkup, react-router MemoryRouter, TanStack Query; the
 *   global fetch and window config stubbed (the backend is external).
 * Key invariants: rendered to static markup in the node test environment, so no DOM library is
 *   needed; the markup injection case puts HTML into input, context and rule and requires it
 *   escaped. The container cases fill the cache through the real query options, `api` client and
 *   error mapping from a fetch stubbed per backend path, then render at a URL; the test client
 *   sets `retry: false` and `retryOnMount: false` so a cached error is rendered, not refetched.
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderToStaticMarkup } from 'react-dom/server';
import { MemoryRouter } from 'react-router';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { datasetSummaryQueryOptions, datasetVersionQueryOptions } from './api';
import {
  DatasetVersion as DatasetVersionContainer,
  DatasetVersionView,
  GoldensTable,
} from './DatasetVersion';
import type { DatasetSummary, DatasetVersion, Golden } from '@/lib/api/types';

const PLAIN: Golden = {
  position: 1,
  input: 'I bought these sneakers 5 weeks ago, can I return them?',
  expected_decision: 'deny_return',
  rule: 'Returns within 30 days of delivery — doc returns',
  failure_type: 'date_math',
  context: null,
  expected_numbers: ['30'],
  owner: null,
  unfixable_by_code: false,
};

const UNFIXABLE: Golden = {
  position: 2,
  input: 'Do you sell gift cards?',
  expected_decision: 'answer_from_docs',
  rule: 'Gift-card policy — document to be written',
  failure_type: 'out_of_docs',
  context: 'Order 1042, delivered 2026-10-01',
  expected_numbers: [],
  owner: 'support_content',
  unfixable_by_code: true,
};

const MARKUP = '<img src=x onerror=alert(1)>';

const cells = (html: string) =>
  [...html.matchAll(/<tr class="align-top">(.*?)<\/tr>/g)].map(([, row]) =>
    [...(row ?? '').matchAll(/<td>(.*?)<\/td>/g)].map(([, cell]) => cell),
  );

describe('GoldensTable', () => {
  it('shows every Golden with its labels, dashes a missing owner and marks unfixable ones', () => {
    const rows = cells(renderToStaticMarkup(<GoldensTable goldens={[PLAIN, UNFIXABLE]} />));

    expect(rows).toHaveLength(2);
    expect(rows[0]?.[0]).toBe('1');
    expect(rows[0]?.[2]).toContain('Deny return');
    expect(rows[0]?.[4]).toBe('Date math');
    expect(rows[0]?.[5]).toBe('—');
    expect(rows[0]?.join('')).not.toContain('Context');
    expect(rows[1]?.[1]).toContain('Context: Order 1042, delivered 2026-10-01');
    expect(rows[1]?.[2]).toContain('Answer from documents');
    expect(rows[1]?.[4]).toBe('Out of documents');
    expect(rows[1]?.[5]).toContain('Support content');
    expect(rows[1]?.[5]).toContain('Unfixable by code');
    expect(rows[0]?.[5]).not.toContain('Unfixable by code');
  });

  it('shows the expected numbers of a Golden that has them, under its rule', () => {
    const numbers = { ...PLAIN, expected_numbers: ['5', '7'] };

    const rows = cells(renderToStaticMarkup(<GoldensTable goldens={[numbers, UNFIXABLE]} />));

    expect(rows[0]?.[3]).toContain('Numbers: 5, 7');
    expect(rows[1]?.[3]).not.toContain('Numbers');
  });

  it('renders Golden text as plain text, never as HTML', () => {
    const golden = { ...PLAIN, input: MARKUP, context: MARKUP, rule: MARKUP };

    const html = renderToStaticMarkup(<GoldensTable goldens={[golden]} />);

    expect(html).not.toContain('<img');
    expect(html.match(/&lt;img src=x onerror=alert\(1\)&gt;/g)).toHaveLength(3);
  });
});

describe('DatasetVersionView', () => {
  const summary: DatasetSummary = {
    client_id: 'acme',
    project_id: 'support-bot',
    current_version: 2,
    versions: [
      { number: 1, published_at: '2026-11-01T09:00:00+00:00', golden_count: 1 },
      { number: 2, published_at: '2026-11-02T09:00:00+00:00', golden_count: 2 },
    ],
    failure_type_counts: {
      date_math: 1,
      refund_rules: 0,
      invented_facts: 0,
      out_of_docs: 1,
      retrieval_miss: 0,
      order_status_tool: 0,
    },
  };
  const version: DatasetVersion = {
    client_id: 'acme',
    project_id: 'support-bot',
    number: 1,
    published_at: '2026-11-01T09:00:00+00:00',
    is_current: false,
    goldens: [PLAIN],
  };

  it('lists every published version, marks the current one and selects the shown one', () => {
    const html = renderToStaticMarkup(
      <DatasetVersionView summary={summary} version={version} onSelect={() => undefined} />,
    );

    expect(html).toContain('<option value="1" selected="">1</option>');
    expect(html).toContain('<option value="2">2 (current)</option>');
    expect(html).toContain('1 Golden<');
    expect(html).toContain('Client acme');
  });
});

describe('DatasetVersion (container)', () => {
  const SUMMARY_PATH = '/api/v1/products/acme/support-bot/dataset';
  const summary: DatasetSummary = {
    client_id: 'acme',
    project_id: 'support-bot',
    current_version: 1,
    versions: [{ number: 1, published_at: '2026-11-01T09:00:00+00:00', golden_count: 1 }],
    failure_type_counts: {
      date_math: 1,
      refund_rules: 0,
      invented_facts: 0,
      out_of_docs: 0,
      retrieval_miss: 0,
      order_status_tool: 0,
    },
  };
  const current: DatasetVersion = {
    client_id: 'acme',
    project_id: 'support-bot',
    number: 1,
    published_at: '2026-11-01T09:00:00+00:00',
    is_current: true,
    goldens: [PLAIN],
  };

  const json = (body: unknown) =>
    new Response(JSON.stringify(body), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    });
  const problem = (status: number, code: string) =>
    new Response(JSON.stringify({ title: 'Error', status, detail: 'Refused.', code }), {
      status,
      headers: { 'Content-Type': 'application/problem+json' },
    });

  beforeEach(() => {
    vi.stubGlobal('window', { __APP_CONFIG__: { backendUrl: 'http://backend:8000' } });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  /**
   * Answers each backend path from `answers`, fetches what the container asks for at `search`
   * (the summary, then the chosen version) and renders the container there.
   */
  async function renderAt(search: string, answers: Record<string, () => Response>) {
    vi.stubGlobal(
      'fetch',
      vi.fn<typeof fetch>((input) => {
        const path = new URL(input instanceof Request ? input.url : String(input)).pathname;
        const answer = answers[path];
        if (!answer) {
          throw new Error(`unexpected request to ${path}`);
        }
        return Promise.resolve(answer());
      }),
    );
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, retryOnMount: false } },
    });
    const loaded = await queryClient
      .query(datasetSummaryQueryOptions('acme', 'support-bot'))
      .catch(() => undefined);
    const chosen =
      new URLSearchParams(search).get('version') || String(loaded?.current_version ?? '');
    if (loaded) {
      await queryClient
        .query(datasetVersionQueryOptions('acme', 'support-bot', chosen))
        .catch(() => undefined);
    }
    return renderToStaticMarkup(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={[`/products/acme/support-bot/dataset${search}`]}>
          <DatasetVersionContainer clientId="acme" projectId="support-bot" />
        </MemoryRouter>
      </QueryClientProvider>,
    );
  }

  it('shows a quiet "No Dataset" note when the Product has no Dataset', async () => {
    const html = await renderAt('', { [SUMMARY_PATH]: () => problem(404, 'DATASET_NOT_FOUND') });

    expect(html).toContain('No Dataset.');
    expect(html).not.toContain('role="alert"');
  });

  it('shows any other summary error through ErrorMessage', async () => {
    const html = await renderAt('', { [SUMMARY_PATH]: () => problem(404, 'PRODUCT_NOT_FOUND') });

    expect(html).toContain('role="alert"');
    expect(html).not.toContain('No Dataset.');
  });

  it('shows a not-found message linking to the current version for an unknown version', async () => {
    const html = await renderAt('?version=9', {
      [SUMMARY_PATH]: () => json(summary),
      [`${SUMMARY_PATH}/versions/9`]: () => problem(404, 'DATASET_VERSION_NOT_FOUND'),
    });

    expect(html).toContain('Dataset version not found.');
    expect(html).toContain('href="/products/acme/support-bot/dataset"');
    expect(html).not.toContain('role="alert"');
  });

  it('shows any other version error through ErrorMessage', async () => {
    const html = await renderAt('?version=9', {
      [SUMMARY_PATH]: () => json(summary),
      [`${SUMMARY_PATH}/versions/9`]: () => problem(403, 'PERMISSION_DENIED'),
    });

    expect(html).toContain('You are not allowed to do this.');
    expect(html).not.toContain('Dataset version not found.');
  });

  it('shows the current version when the URL names none', async () => {
    const html = await renderAt('', {
      [SUMMARY_PATH]: () => json(summary),
      [`${SUMMARY_PATH}/versions/1`]: () => json(current),
    });

    expect(html).toContain('<option value="1" selected="">1 (current)</option>');
    expect(html).toContain('1 Golden<');
  });
});
