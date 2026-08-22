// SPDX-License-Identifier: Apache-2.0
// Copyright 2026 Containerized Lakehouse Platform Contributors

import { NextRequest, NextResponse } from "next/server";
import { requireEnv } from "@/lib/env";

const DS_URL = () =>
  process.env.DELTA_SHARING_URL || "https://delta-sharing:8443";
const DS_TOKEN = () => requireEnv("DELTA_SHARING_TOKEN");

async function proxy(req: NextRequest, path: string) {
  const url = `${DS_URL()}/delta-sharing/${path}`;
  try {
    const res = await fetch(url, {
      method: req.method,
      headers: {
        Authorization: `Bearer ${DS_TOKEN()}`,
        "Content-Type": "application/json",
      },
      signal: AbortSignal.timeout(5000),
      // @ts-expect-error Node.js fetch rejectUnauthorized for self-signed certs
      rejectUnauthorized: false,
    });
    const data = await res.text();
    return new NextResponse(data, {
      status: res.status,
      headers: {
        "Content-Type":
          res.headers.get("Content-Type") || "application/json",
      },
    });
  } catch {
    return NextResponse.json(
      { error: "Delta Sharing server unreachable" },
      { status: 502 }
    );
  }
}

export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const { path } = await params;
  return proxy(req, path.join("/"));
}
