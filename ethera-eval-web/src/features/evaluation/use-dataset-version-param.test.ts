/**
 * Unit tests for the Dataset version chosen in the URL.
 *
 * Role: proves a missing or empty ?version means the current version (undefined), any other
 *   value is passed on exactly as given, and select writes ?version=N.
 * Used by: Vitest.
 * Depends on: ./use-dataset-version-param, react-dom/server renderToStaticMarkup, react-router
 *   MemoryRouter (reads are real) with `useSearchParams`'s setter replaced by a spy.
 * Key invariants: the hook runs inside a statically rendered probe, so the router's real search
 *   params are read; writing cannot be observed without a DOM (react-router only navigates after
 *   a layout effect), so the setter of `useSearchParams` — a third-party library, not our code —
 *   is the one thing replaced, and the test asserts what the hook hands it.
 */
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { MemoryRouter } from 'react-router';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { useDatasetVersionParam } from './use-dataset-version-param';

const setParams = vi.hoisted(() => vi.fn());

vi.mock('react-router', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router')>();
  return {
    ...actual,
    useSearchParams: () => [actual.useSearchParams()[0], setParams] as const,
  };
});

beforeEach(() => {
  setParams.mockClear();
});

/** Renders the hook at `url` and returns what it gave back. */
function renderAt(url: string): ReturnType<typeof useDatasetVersionParam> {
  let result: ReturnType<typeof useDatasetVersionParam> | undefined;
  function Probe() {
    result = useDatasetVersionParam();
    return null;
  }
  renderToStaticMarkup(
    createElement(MemoryRouter, { initialEntries: [url] }, createElement(Probe)),
  );
  if (!result) {
    throw new Error('the probe did not render');
  }
  return result;
}

describe('useDatasetVersionParam', () => {
  it('a missing version param means the current version', () => {
    expect(renderAt('/products/acme/bot/dataset').version).toBeUndefined();
  });

  it('an empty version param means the current version', () => {
    expect(renderAt('/products/acme/bot/dataset?version=').version).toBeUndefined();
  });

  it('passes any other version on exactly as given', () => {
    expect(renderAt('/products/acme/bot/dataset?version=2').version).toBe('2');
    expect(renderAt('/products/acme/bot/dataset?version=abc').version).toBe('abc');
  });

  it('select writes the version param', () => {
    renderAt('/products/acme/bot/dataset').select(2);

    expect(setParams).toHaveBeenCalledExactlyOnceWith({ version: '2' });
  });
});
