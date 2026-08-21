"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";
import "highlight.js/styles/github-dark.css";
import { useState } from "react";
import { Check, Copy } from "lucide-react";
import { cn } from "@/lib/utils/cn";

function CodeBlock({
  language,
  code,
}: {
  language: string;
  code: string;
}) {
  const [copied, setCopied] = useState(false);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      setTimeout(() => setCopied(false), 1200);
    } catch {
      /* clipboard unavailable */
    }
  };

  return (
    <div className="group/code my-2 overflow-hidden rounded-lg border border-border bg-code-bg">
      <div className="flex h-7 items-center gap-2 border-b border-border bg-muted/40 px-3">
        <span className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
          {language || "text"}
        </span>
        <span className="flex-1" />
        <button
          onClick={copy}
          className="inline-flex h-5 items-center gap-1 rounded px-1 text-[10px] text-muted-foreground opacity-0 transition-opacity hover:text-foreground group-hover/code:opacity-100"
          aria-label="Copy code"
        >
          {copied ? <Check className="h-3 w-3 text-success" /> : <Copy className="h-3 w-3" />}
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
      <pre className="overflow-x-auto p-3 text-[13px] leading-relaxed">
        <code className={language ? `hljs language-${language}` : "hljs"}>
          {code}
        </code>
      </pre>
    </div>
  );
}

export function MarkdownContent({ content }: { content: string }) {
  return (
    <div className="prose-invert space-y-1.5 text-[14px] leading-relaxed">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeHighlight]}
        components={{
          a: ({ href, children }) => (
            <a
              href={href}
              target="_blank"
              rel="noopener noreferrer"
              className="text-accent underline decoration-accent/40 underline-offset-2 hover:decoration-accent"
            >
              {children}
            </a>
          ),
          code({ className, children, ...props }) {
            const match = /language-(\w+)/.exec(className || "");
            const code = String(children).replace(/\n$/, "");
            if (!match) {
              return (
                <code
                  className={cn(
                    "rounded bg-muted px-1.5 py-0.5 font-mono text-[0.85em] text-accent",
                    className
                  )}
                  {...props}
                >
                  {children}
                </code>
              );
            }
            return <CodeBlock language={match[1]} code={code} />;
          },
          pre: ({ children }) => <div>{children}</div>,
          h1: ({ children }) => (
            <h1 className="pb-1 pt-2 text-xl font-semibold tracking-tight">{children}</h1>
          ),
          h2: ({ children }) => (
            <h2 className="pb-1 pt-2 text-lg font-semibold tracking-tight">{children}</h2>
          ),
          h3: ({ children }) => (
            <h3 className="pb-1 pt-2 text-base font-semibold tracking-tight">{children}</h3>
          ),
          ul: ({ children }) => (
            <ul className="list-disc space-y-1 pl-5 marker:text-muted-foreground">{children}</ul>
          ),
          ol: ({ children }) => (
            <ol className="list-decimal space-y-1 pl-5 marker:text-muted-foreground">{children}</ol>
          ),
          li: ({ children }) => <li className="leading-relaxed">{children}</li>,
          blockquote: ({ children }) => (
            <blockquote className="border-l-2 border-border pl-3 text-muted-foreground">
              {children}
            </blockquote>
          ),
          hr: () => <hr className="my-3 border-border" />,
          table: ({ children }) => (
            <div className="my-2 overflow-x-auto rounded-lg border border-border">
              <table className="w-full border-collapse text-[13px]">{children}</table>
            </div>
          ),
          th: ({ children }) => (
            <th className="border-b border-border bg-muted/40 px-3 py-1.5 text-left font-semibold">
              {children}
            </th>
          ),
          td: ({ children }) => (
            <td className="border-b border-border/60 px-3 py-1.5 align-top">{children}</td>
          ),
          strong: ({ children }) => <strong className="font-semibold text-foreground">{children}</strong>,
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
