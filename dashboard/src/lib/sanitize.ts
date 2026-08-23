// SPDX-License-Identifier: Apache-2.0
// Copyright 2026 Containerized Lakehouse Platform Contributors

/**
 * Simple HTML sanitizer that strips dangerous tags and attributes.
 * For defense-in-depth against XSS in notebook output rendering.
 */
export function sanitizeHtml(html: string): string {
  // Remove script tags and their content
  let clean = html.replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, '');

  // Remove event handler attributes (onclick, onerror, onload, etc.)
  clean = clean.replace(/\s+on\w+\s*=\s*(?:"[^"]*"|'[^']*'|[^\s>]+)/gi, '');

  // Remove javascript: URLs (double-, single-, and unquoted)
  clean = clean.replace(
    /(?:href|src)\s*=\s*(?:"javascript:[^"]*"|'javascript:[^']*'|javascript:[^\s>]+)/gi,
    ''
  );

  // Remove non-image data: URLs in src attributes (double-, single-, and
  // unquoted) — data:image/* is kept for notebook image output.
  clean = clean.replace(
    /src\s*=\s*(?:"data:(?!image\/)[^"]*"|'data:(?!image\/)[^']*'|data:(?!image\/)[^\s>]+)/gi,
    ''
  );

  // Remove iframe, embed, object tags
  clean = clean.replace(/<(iframe|embed|object)\b[^>]*>[\s\S]*?<\/\1>/gi, '');
  clean = clean.replace(/<(iframe|embed|object)\b[^>]*\/?>/gi, '');

  // Remove form and input elements
  clean = clean.replace(/<(form|input|textarea|select|button)\b[^>]*>[\s\S]*?<\/\1>/gi, '');
  clean = clean.replace(/<(input|br)\b[^>]*\/?>/gi, '');

  return clean;
}
