import React, { useEffect, useRef } from 'react';
import { marked } from 'marked';
import hljs from 'highlight.js';

interface Props {
  content: string;
}

export const MarkdownContent: React.FC<Props> = ({ content }) => {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.querySelectorAll('pre code').forEach((el) => {
        hljs.highlightElement(el as HTMLElement);
      });
    }
  }, [content]);

  // Configure marked for line breaks and GitHub flavored markdown
  marked.setOptions({
    gfm: true,
    breaks: true,
  });

  const parsedHtml = marked.parse(content || '') as string;

  return (
    <div
      ref={containerRef}
      className="prose dark:prose-invert prose-sm sm:prose-base max-w-none text-slate-800 dark:text-slate-200 break-words leading-relaxed"
      dangerouslySetInnerHTML={{ __html: parsedHtml }}
    />
  );
};
