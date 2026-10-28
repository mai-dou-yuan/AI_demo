import { Fragment } from 'react';
import { safeHref } from '@/lib/api';
function inline(text: string) {
  return text.split(/(\[[^\]]+\]\([^\s)]+\)|\*\*[^*]+\*\*|`[^`]+`)/g).map((part, i) => {
    const link = part.match(/^\[([^\]]+)\]\(([^\s)]+)\)$/);
    if (link) return safeHref(link[2]) ? <a key={i} href={safeHref(link[2])} target="_blank" rel="noreferrer">{link[1]}</a> : <Fragment key={i}>{link[1]}</Fragment>;
    if (part.startsWith('**')) return <strong key={i}>{part.slice(2, -2)}</strong>;
    if (part.startsWith('`')) return <code key={i}>{part.slice(1, -1)}</code>;
    return <Fragment key={i}>{part}</Fragment>;
  });
}
export function Markdown({ text }: { text: string }) {
  return <div className="markdown">{text.split(/(```[\s\S]*?```)/g).map((block, index) => block.startsWith('```') ? <pre key={index}><code>{block.replace(/^```[^\n]*\n?/, '').replace(/```$/, '')}</code></pre> : <Fragment key={index}>{block.split('\n').map((line, i) => {
    if (/^#+ /.test(line)) return <h3 key={i}>{inline(line.replace(/^#+ /, ''))}</h3>;
    if (/^\s*[-*] /.test(line)) return <div className="markdown-item" key={i}><span>•</span><div>{inline(line.replace(/^\s*[-*] /, ''))}</div></div>;
    if (line.startsWith('> ')) return <blockquote key={i}>{inline(line.slice(2))}</blockquote>;
    return line ? <p key={i}>{inline(line)}</p> : <div className="paragraph-gap" key={i} />;
  })}</Fragment>)}</div>;
}
