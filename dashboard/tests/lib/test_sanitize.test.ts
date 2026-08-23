import { describe, it, expect } from "vitest";
import { sanitizeHtml } from "@/lib/sanitize";

describe("sanitizeHtml", () => {
  it("strips script tags", () => {
    const input = '<p>Hello</p><script>alert("xss")</script>';
    expect(sanitizeHtml(input)).not.toContain("<script");
    expect(sanitizeHtml(input)).toContain("<p>Hello</p>");
  });

  it("strips event handlers", () => {
    const input = '<img src="x" onerror="alert(1)">';
    const result = sanitizeHtml(input);
    expect(result).not.toContain("onerror");
  });

  it("strips javascript: URLs", () => {
    const input = '<a href="javascript:alert(1)">click</a>';
    expect(sanitizeHtml(input)).not.toContain("javascript:");
  });

  it("preserves safe HTML", () => {
    const input = '<p>Hello <strong>world</strong></p>';
    expect(sanitizeHtml(input)).toBe(input);
  });

  it("preserves data:image URLs", () => {
    const input = '<img src="data:image/png;base64,abc123">';
    expect(sanitizeHtml(input)).toContain("data:image/png");
  });

  it("strips data: non-image URLs", () => {
    const input = '<img src="data:text/html,<script>alert(1)</script>">';
    expect(sanitizeHtml(input)).not.toContain("data:text/html");
  });

  it("strips single-quoted and unquoted data: non-image URLs", () => {
    expect(sanitizeHtml("<img src='data:text/html;base64,abc'>")).not.toContain(
      "data:text/html"
    );
    expect(sanitizeHtml("<img src=data:text/html,x>")).not.toContain("data:text/html");
  });

  it("strips single-quoted and unquoted javascript: URLs", () => {
    expect(sanitizeHtml("<a href='javascript:alert(1)'>x</a>")).not.toContain(
      "javascript:"
    );
    expect(sanitizeHtml("<img src=javascript:alert(1)>")).not.toContain("javascript:");
  });

  it("strips iframe tags", () => {
    const input = '<iframe src="http://evil.com"></iframe>';
    expect(sanitizeHtml(input)).not.toContain("iframe");
  });
});
