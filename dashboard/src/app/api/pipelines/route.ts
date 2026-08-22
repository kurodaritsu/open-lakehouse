// SPDX-License-Identifier: Apache-2.0
// Copyright 2026 Containerized Lakehouse Platform Contributors

import { NextRequest, NextResponse } from "next/server";
import { readFileSync, readdirSync, writeFileSync, mkdirSync, existsSync, statSync } from "fs";
import { join, relative } from "path";

const PIPELINES_DIR = "/app/pipelines";

function walkDir(dir: string): string[] {
  const files: string[] = [];
  if (!existsSync(dir)) return files;
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = join(dir, entry.name);
    if (entry.isDirectory()) {
      files.push(...walkDir(full));
    } else {
      files.push(relative(PIPELINES_DIR, full));
    }
  }
  return files;
}

export async function GET() {
  try {
    if (!existsSync(PIPELINES_DIR)) {
      return NextResponse.json({ specs: [], transformations: [] });
    }

    const allFiles = walkDir(PIPELINES_DIR);
    const specs = allFiles.filter((f) => f.endsWith(".yml") || f.endsWith(".yaml"));
    const transformations = allFiles.filter((f) => f.endsWith(".py") || f.endsWith(".sql"));

    const specContents = specs.map((f) => {
      const full = join(PIPELINES_DIR, f);
      return {
        path: f,
        content: readFileSync(full, "utf-8"),
        modified: statSync(full).mtime.toISOString(),
      };
    });

    const transformationContents = transformations.map((f) => {
      const full = join(PIPELINES_DIR, f);
      return {
        path: f,
        content: readFileSync(full, "utf-8"),
        modified: statSync(full).mtime.toISOString(),
      };
    });

    return NextResponse.json({
      specs: specContents,
      transformations: transformationContents,
    });
  } catch {
    return NextResponse.json({ error: "Failed to read pipelines" }, { status: 500 });
  }
}

export async function POST(req: NextRequest) {
  try {
    const { specName, specContent, transformations } = await req.json();

    if (!specName || !specContent) {
      return NextResponse.json({ error: "specName and specContent required" }, { status: 400 });
    }

    const specPath = join(PIPELINES_DIR, specName.endsWith(".yml") ? specName : `${specName}.yml`);

    // Prevent path traversal
    const resolvedSpec = require("path").resolve(PIPELINES_DIR, specName.endsWith(".yml") ? specName : `${specName}.yml`);
    if (!resolvedSpec.startsWith(require("path").resolve(PIPELINES_DIR))) {
      return NextResponse.json({ error: "Invalid path" }, { status: 400 });
    }

    writeFileSync(specPath, specContent, "utf-8");

    if (transformations && Array.isArray(transformations)) {
      for (const t of transformations) {
        if (!t.path || !t.content) continue;
        // Prevent path traversal
        const resolvedT = require("path").resolve(PIPELINES_DIR, t.path);
        if (!resolvedT.startsWith(require("path").resolve(PIPELINES_DIR))) {
          return NextResponse.json({ error: "Invalid path" }, { status: 400 });
        }
        const tPath = join(PIPELINES_DIR, t.path);
        const tDir = join(tPath, "..");
        if (!existsSync(tDir)) mkdirSync(tDir, { recursive: true });
        writeFileSync(tPath, t.content, "utf-8");
      }
    }

    return NextResponse.json({ ok: true, specPath: relative(PIPELINES_DIR, specPath) });
  } catch {
    return NextResponse.json({ error: "Failed to create pipeline" }, { status: 500 });
  }
}
