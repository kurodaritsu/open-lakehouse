// SPDX-License-Identifier: Apache-2.0
// Copyright 2026 Containerized Lakehouse Platform Contributors

import { NextRequest, NextResponse } from "next/server";

const MINIO_URL = () =>
  process.env.MINIO_URL || "http://localhost:9000";

async function proxy(req: NextRequest, path: string) {
  const query = req.nextUrl.search;
  const url = `${MINIO_URL()}/${path}${query}`;

  try {
    const res = await fetch(url, {
      method: req.method,
      signal: AbortSignal.timeout(5000),
    });
    const data = await res.text();
    return new NextResponse(data, {
      status: res.status,
      headers: { "Content-Type": res.headers.get("Content-Type") || "text/plain" },
    });
  } catch {
    return NextResponse.json({ error: "MinIO unreachable" }, { status: 502 });
  }
}

export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const { path } = await params;
  return proxy(req, path.join("/"));
}
