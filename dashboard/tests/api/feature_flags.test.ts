/**
 * F-10: code-execution feature-flag gating (D6 / T-3.8).
 *
 * With DASHBOARD_ALLOW_CODE_EXECUTION off, the exec/write routes must be
 * disabled (403); with it on, /api/features reports true and the write routes
 * reach their normal logic. The fs module is mocked so these run without Docker.
 */

import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { NextRequest } from "next/server";

vi.mock("fs", () => ({
  readFileSync: vi.fn().mockReturnValue("name: test\n"),
  readdirSync: vi.fn().mockReturnValue([]),
  writeFileSync: vi.fn(),
  mkdirSync: vi.fn(),
  existsSync: vi.fn().mockReturnValue(true),
  statSync: vi.fn().mockReturnValue({ mtime: new Date() }),
}));

import { GET as featuresGET } from "@/app/api/features/route";
import { POST as pipelinesPOST } from "@/app/api/pipelines/route";
import { POST as jupyterExecPOST } from "@/app/api/jupyter-exec/route";
import { POST as pipelinesRunPOST } from "@/app/api/pipelines/run/route";
import { DELETE as historyDELETE } from "@/app/api/pipelines/history/route";

const ORIGINAL = process.env.DASHBOARD_ALLOW_CODE_EXECUTION;

function jsonReq(url: string, body: unknown): NextRequest {
  return new NextRequest(url, {
    method: "POST",
    body: JSON.stringify(body),
    headers: { "Content-Type": "application/json" },
  });
}

describe("code-execution feature flag (F-10)", () => {
  afterEach(() => {
    process.env.DASHBOARD_ALLOW_CODE_EXECUTION = ORIGINAL;
  });

  describe("with the flag OFF", () => {
    beforeEach(() => {
      process.env.DASHBOARD_ALLOW_CODE_EXECUTION = "false";
    });

    it("GET /api/features reports codeExecution:false", async () => {
      const data = await (await featuresGET()).json();
      expect(data.codeExecution).toBe(false);
    });

    it("disables POST /api/jupyter-exec (403)", async () => {
      const res = await jupyterExecPOST(
        jsonReq("http://localhost:3000/api/jupyter-exec", {
          kernelId: "k",
          code: "print(1)",
        })
      );
      expect(res.status).toBe(403);
    });

    it("disables POST /api/pipelines/run (403)", async () => {
      const res = await pipelinesRunPOST(
        jsonReq("http://localhost:3000/api/pipelines/run", { specPath: "x.yml" })
      );
      expect(res.status).toBe(403);
    });

    it("disables POST /api/pipelines (403)", async () => {
      const res = await pipelinesPOST(
        jsonReq("http://localhost:3000/api/pipelines", {
          specName: "x",
          specContent: "y",
        })
      );
      expect(res.status).toBe(403);
    });

    it("disables DELETE /api/pipelines/history (403)", async () => {
      const res = await historyDELETE(
        jsonReq("http://localhost:3000/api/pipelines/history", { id: "1" })
      );
      expect(res.status).toBe(403);
    });
  });

  describe("with the flag ON", () => {
    beforeEach(() => {
      process.env.DASHBOARD_ALLOW_CODE_EXECUTION = "true";
    });

    it("GET /api/features reports codeExecution:true", async () => {
      const data = await (await featuresGET()).json();
      expect(data.codeExecution).toBe(true);
    });

    it("allows POST /api/pipelines with a valid spec (not disabled)", async () => {
      const res = await pipelinesPOST(
        jsonReq("http://localhost:3000/api/pipelines", {
          specName: "test-pipeline",
          specContent: "name: test\n",
        })
      );
      expect(res.status).not.toBe(403);
      expect(res.status).toBe(200);
    });
  });
});
