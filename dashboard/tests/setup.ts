/**
 * Vitest test setup for frontend tests.
 *
 * Provides global mocks for Next.js server-side APIs and fetch
 * so tests can run without a real Next.js server or Docker services.
 */

import { vi } from "vitest";

// Mock global fetch for all tests
global.fetch = vi.fn();

// Mock AbortSignal.timeout (not available in all Node.js versions)
if (!AbortSignal.timeout) {
  (AbortSignal as unknown as Record<string, unknown>).timeout = (ms: number) => {
    const controller = new AbortController();
    setTimeout(() => controller.abort(), ms);
    return controller.signal;
  };
}
