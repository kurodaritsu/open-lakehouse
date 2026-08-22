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

  // Remove javascript: URLs
  clean = clean.replace(/href\s*=\s*(?:"javascript:[^"]*"|'javascript:[^']*')/gi, '');
  clean = clean.replace(/src\s*=\s*(?:"javascript:[^"]*"|'javascript:[^']*')/gi, '');

  // Remove data: URLs in src attributes (except data:image which is used for notebook output)
  clean = clean.replace(/src\s*=\s*"data:(?!image\/)[^"]*"/gi, '');

  // Remove iframe, embed, object tags
  clean = clean.replace(/<(iframe|embed|object)\b[^>]*>[\s\S]*?<\/\1>/gi, '');
  clean = clean.replace(/<(iframe|embed|object)\b[^>]*\/?>/gi, '');

  // Remove form and input elements
  clean = clean.replace(/<(form|input|textarea|select|button)\b[^>]*>[\s\S]*?<\/\1>/gi, '');
  clean = clean.replace(/<(input|br)\b[^>]*\/?>/gi, '');

  return clean;
}
