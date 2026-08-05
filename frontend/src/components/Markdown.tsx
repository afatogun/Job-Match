/**
 * Minimal renderer for the markdown job descriptions jobspy returns.
 *
 * Deliberately builds React elements rather than setting innerHTML: the content
 * is scraped from third-party sites, so no HTML from it is ever interpreted.
 */

function renderInline(text: string, keyPrefix: string) {
  // Split on **bold** and `code`, keeping the delimiters' content.
  const parts = text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g)
  return parts.map((part, i) => {
    const key = `${keyPrefix}-${i}`
    if (part.startsWith('**') && part.endsWith('**') && part.length > 4) {
      return (
        <strong key={key} className="font-semibold text-slate-900">
          {part.slice(2, -2)}
        </strong>
      )
    }
    if (part.startsWith('`') && part.endsWith('`') && part.length > 2) {
      return (
        <code key={key} className="rounded bg-slate-100 px-1 py-0.5 text-[0.85em]">
          {part.slice(1, -1)}
        </code>
      )
    }
    return <span key={key}>{part}</span>
  })
}

export function Markdown({ text }: { text: string }) {
  const lines = text.replace(/\r\n/g, '\n').split('\n')
  const blocks: React.ReactNode[] = []
  let listItems: string[] = []

  const flushList = (key: string) => {
    if (!listItems.length) return
    blocks.push(
      <ul key={key} className="my-3 list-disc space-y-1.5 pl-5 marker:text-slate-400">
        {listItems.map((item, i) => (
          <li key={i}>{renderInline(item, `${key}-${i}`)}</li>
        ))}
      </ul>,
    )
    listItems = []
  }

  lines.forEach((raw, index) => {
    const line = raw.trimEnd()
    const bullet = line.match(/^\s*[-*+]\s+(.*)$/)
    const heading = line.match(/^(#{1,6})\s+(.*)$/)

    if (bullet) {
      listItems.push(bullet[1])
      return
    }
    flushList(`list-${index}`)

    if (heading) {
      blocks.push(
        <h3 key={index} className="mt-5 mb-2 text-base font-semibold text-slate-900">
          {renderInline(heading[2], `h-${index}`)}
        </h3>,
      )
    } else if (line.trim()) {
      blocks.push(
        <p key={index} className="my-2 leading-relaxed">
          {renderInline(line, `p-${index}`)}
        </p>,
      )
    }
  })
  flushList('list-final')

  return <div className="text-[15px] text-slate-700">{blocks}</div>
}
