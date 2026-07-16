"use client";

import type { ReactNode } from "react";
import { useMemo, useState } from "react";

import { Icon } from "./icons";

type MarkdownBlock =
  | { kind: "code"; value: string; language: string }
  | { kind: "heading"; value: string; level: number }
  | { kind: "quote"; value: string }
  | { kind: "list"; items: string[]; ordered: boolean }
  | { kind: "table"; headers: string[]; rows: string[][] }
  | { kind: "paragraph"; value: string }
  | { kind: "rule" };

export function MessageContent({
  content,
  streaming = false
}: {
  content: string;
  streaming?: boolean;
}) {
  const blocks = useMemo(() => parseMarkdownBlocks(content), [content]);

  return (
    <div className="eidolon-prose">
      {blocks.map((block, index) => {
        const key = `${block.kind}-${index}`;
        if (block.kind === "code") {
          return <CodeBlock code={block.value} key={key} language={block.language} />;
        }
        if (block.kind === "heading") {
          const Heading = block.level === 1 ? "h3" : block.level === 2 ? "h4" : "h5";
          const className =
            block.level === 1
              ? "font-eidolon-display text-[1.35em] leading-tight text-[#f0e6dc]"
              : "font-eidolon-display text-[1.15em] leading-tight text-[#ece2d8]";
          return <Heading className={className} key={key}>{inlineMarkdown(block.value)}</Heading>;
        }
        if (block.kind === "quote") {
          return <blockquote key={key}>{inlineMarkdown(block.value)}</blockquote>;
        }
        if (block.kind === "list") {
          const List = block.ordered ? "ol" : "ul";
          return <List key={key}>{block.items.map((item, itemIndex) => <li key={`${itemIndex}-${item}`}>{inlineMarkdown(item)}</li>)}</List>;
        }
        if (block.kind === "table") {
          return (
            <div className="overflow-x-auto rounded-xl border border-white/[0.09]" key={key}>
              <table className="w-full min-w-[28rem] border-collapse text-left text-[0.82em]">
                <thead className="bg-white/[0.04] text-[#ded3c8]"><tr>{block.headers.map((header, headerIndex) => <th className="border-b border-white/[0.09] px-3 py-2.5 font-semibold" key={`${headerIndex}-${header}`}>{inlineMarkdown(header)}</th>)}</tr></thead>
                <tbody>{block.rows.map((row, rowIndex) => <tr className="border-b border-white/[0.06] last:border-0" key={rowIndex}>{block.headers.map((_, cellIndex) => <td className="px-3 py-2.5 align-top" key={cellIndex}>{inlineMarkdown(row[cellIndex] ?? "")}</td>)}</tr>)}</tbody>
              </table>
            </div>
          );
        }
        if (block.kind === "rule") {
          return <hr className="border-white/[0.1]" key={key} />;
        }
        return <p key={key}>{inlineMarkdown(block.value)}</p>;
      })}
      {streaming ? <span aria-hidden="true" className="ml-1 inline-block h-4 w-px animate-pulse bg-[color:var(--color-accent)]" /> : null}
    </div>
  );
}

function CodeBlock({ code, language }: { code: string; language: string }) {
  const [copyState, setCopyState] = useState<"idle" | "copied" | "error">("idle");

  async function copy() {
    try {
      await copyText(code);
      setCopyState("copied");
      window.setTimeout(() => setCopyState("idle"), 1800);
    } catch {
      setCopyState("error");
    }
  }

  return (
    <div className="eidolon-code">
      <div className="flex min-h-10 items-center justify-between gap-4 border-b border-white/[0.07] px-3 text-[0.65rem] text-[#7f766e]">
        <span>{language || "code"}</span>
        <button className="flex min-h-11 items-center gap-1.5 rounded-full px-2.5 text-[#9f958b] transition hover:bg-white/[0.05] hover:text-[#ddd2c7]" onClick={() => void copy()} type="button">
          <Icon className="h-3.5 w-3.5" name={copyState === "copied" ? "check" : "copy"} />
          {copyState === "copied" ? "Copied" : copyState === "error" ? "Couldn’t copy" : "Copy"}
        </button>
      </div>
      <pre><code>{code}</code></pre>
    </div>
  );
}

function parseMarkdownBlocks(content: string): MarkdownBlock[] {
  const lines = content.replaceAll("\r\n", "\n").split("\n");
  const blocks: MarkdownBlock[] = [];
  let index = 0;

  while (index < lines.length) {
    const line = lines[index];
    if (!line.trim()) {
      index += 1;
      continue;
    }
    const fence = line.match(/^\s*```([^`]*)$/u);
    if (fence) {
      const code: string[] = [];
      index += 1;
      while (index < lines.length && !/^\s*```\s*$/u.test(lines[index])) {
        code.push(lines[index]);
        index += 1;
      }
      if (index < lines.length) index += 1;
      blocks.push({ kind: "code", value: code.join("\n"), language: cleanLanguage(fence[1]) });
      continue;
    }
    if (/^\s*(?:-{3,}|\*{3,}|_{3,})\s*$/u.test(line)) {
      blocks.push({ kind: "rule" });
      index += 1;
      continue;
    }
    const heading = line.match(/^\s*(#{1,3})\s+(.+)$/u);
    if (heading) {
      blocks.push({ kind: "heading", value: heading[2].trim(), level: heading[1].length });
      index += 1;
      continue;
    }
    if (line.includes("|") && index + 1 < lines.length && isTableSeparator(lines[index + 1])) {
      const headers = splitTableRow(line);
      const rows: string[][] = [];
      index += 2;
      while (index < lines.length && lines[index].includes("|") && lines[index].trim()) {
        rows.push(splitTableRow(lines[index]));
        index += 1;
      }
      blocks.push({ kind: "table", headers, rows });
      continue;
    }
    if (/^\s*>\s?/u.test(line)) {
      const quote: string[] = [];
      while (index < lines.length && /^\s*>\s?/u.test(lines[index])) {
        quote.push(lines[index].replace(/^\s*>\s?/u, ""));
        index += 1;
      }
      blocks.push({ kind: "quote", value: quote.join(" ").trim() });
      continue;
    }
    const listItem = line.match(/^\s*(?:(\d+)\.|[-*+])\s+(.+)$/u);
    if (listItem) {
      const ordered = Boolean(listItem[1]);
      const items: string[] = [];
      while (index < lines.length) {
        const item = lines[index].match(/^\s*(?:(\d+)\.|[-*+])\s+(.+)$/u);
        if (!item || Boolean(item[1]) !== ordered) break;
        items.push(item[2].trim());
        index += 1;
      }
      blocks.push({ kind: "list", items, ordered });
      continue;
    }

    const paragraph = [line.trim()];
    index += 1;
    while (index < lines.length && lines[index].trim() && !startsMarkdownBlock(lines[index])) {
      paragraph.push(lines[index].trim());
      index += 1;
    }
    blocks.push({ kind: "paragraph", value: paragraph.join(" ") });
  }

  return blocks.length > 0 ? blocks : [{ kind: "paragraph", value: content }];
}

function startsMarkdownBlock(line: string): boolean {
  return (
    /^\s*```/u.test(line) ||
    /^\s*(?:#{1,3}\s+|>\s?|(?:(?:\d+)\.|[-*+])\s+)/u.test(line) ||
    /^\s*(?:-{3,}|\*{3,}|_{3,})\s*$/u.test(line)
  );
}

function isTableSeparator(line: string): boolean {
  const cells = splitTableRow(line);
  return cells.length > 0 && cells.every((cell) => /^:?-{3,}:?$/u.test(cell));
}

function splitTableRow(line: string): string[] {
  return line.trim().replace(/^\|/u, "").replace(/\|$/u, "").split("|").map((cell) => cell.trim());
}

function inlineMarkdown(value: string): ReactNode[] {
  const pattern = /(`[^`]+`|\[[^\]]+\]\([^\s)]+\)|\*\*[^*]+\*\*|__[^_]+__|\*[^*]+\*|_[^_]+_)/gu;
  const nodes: ReactNode[] = [];
  let cursor = 0;
  for (const match of value.matchAll(pattern)) {
    const index = match.index ?? 0;
    if (index > cursor) nodes.push(value.slice(cursor, index));
    const token = match[0];
    const key = `${index}-${token}`;
    if (token.startsWith("`")) {
      nodes.push(<code key={key}>{token.slice(1, -1)}</code>);
    } else if (token.startsWith("[")) {
      const link = token.match(/^\[([^\]]+)\]\(([^\s)]+)\)$/u);
      const href = link ? safeHref(link[2]) : null;
      nodes.push(href ? <a href={href} key={key} rel="noreferrer noopener" target="_blank">{link?.[1]}</a> : token);
    } else if (token.startsWith("**") || token.startsWith("__")) {
      nodes.push(<strong className="font-semibold text-[#f0e7de]" key={key}>{token.slice(2, -2)}</strong>);
    } else {
      nodes.push(<em key={key}>{token.slice(1, -1)}</em>);
    }
    cursor = index + token.length;
  }
  if (cursor < value.length) nodes.push(value.slice(cursor));
  return nodes;
}

function safeHref(value: string): string | null {
  try {
    const url = new URL(value);
    return url.protocol === "https:" || url.protocol === "http:" || url.protocol === "mailto:"
      ? url.toString()
      : null;
  } catch {
    return null;
  }
}

function cleanLanguage(value: string): string {
  return value.trim().replace(/[^a-z0-9_+#.-]/giu, "").slice(0, 32);
}

async function copyText(value: string): Promise<void> {
  if (navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(value);
      return;
    } catch {
      // Some browsers expose the API but deny it outside a trusted context.
    }
  }
  const textarea = document.createElement("textarea");
  textarea.value = value;
  textarea.setAttribute("readonly", "");
  textarea.style.position = "fixed";
  textarea.style.opacity = "0";
  document.body.append(textarea);
  textarea.select();
  const copied = document.execCommand("copy");
  textarea.remove();
  if (!copied) throw new Error("Copy is unavailable.");
}
