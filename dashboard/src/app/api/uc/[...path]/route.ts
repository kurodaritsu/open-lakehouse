// SPDX-License-Identifier: Apache-2.0
// Copyright 2026 Containerized Lakehouse Platform Contributors

import { NextRequest, NextResponse } from "next/server";

const UC_URL = () =>
  process.env.UNITY_CATALOG_URL || "http://localhost:8080";

async function proxy(req: NextRequest, path: string) {
  const query = req.nextUrl.search;
  const url = `${UC_URL()}/api/2.1/unity-catalog/${path}${query}`;

  const headers: Record<string, string> = {};
  if (req.method !== "GET") {
    headers["Content-Type"] = "application/json";
  }

  try {
    const res = await fetch(url, {
      method: req.method,
      headers,
      body: req.method !== "GET" ? await req.text() : undefined,
      signal: AbortSignal.timeout(10000),
    });
    const data = await res.text();
    return new NextResponse(data, {
      status: res.status,
      headers: { "Content-Type": res.headers.get("Content-Type") || "application/json" },
    });
  } catch {
    return NextResponse.json({ error: "Unity Catalog unreachable" }, { status: 502 });
  }
}

export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const { path } = await params;
  return proxy(req, path.join("/"));
}

export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const { path } = await params;
  return proxy(req, path.join("/"));
}
