import { useState } from 'react'
import { Search, ChevronDown, Link2 } from 'lucide-react'
import { parseSearchOutput } from '@/lib/fileUtils'

interface SearchCardProps {
  resultText: string
}

export function SearchCard({ resultText }: SearchCardProps) {
  const parsed = parseSearchOutput(resultText)
  const [collapsed, setCollapsed] = useState(false)

  if (!parsed.query && parsed.results.length === 0) return null

  return (
    <div className="search-card">
      <div
        className="search-card-header"
        style={{ cursor: 'pointer', userSelect: 'none' }}
        onClick={() => setCollapsed(!collapsed)}
      >
        <Search size={14} className="search-card-icon" style={{ color: 'hsl(210,100%,45%)' }} />
        <span className="search-card-query">{parsed.query || '搜索结果'}</span>
        {parsed.engine && <span className="search-card-engine">{parsed.engine}</span>}
        {parsed.results.length > 0 && <span className="search-card-count">{parsed.results.length} 条结果</span>}
        <span className="search-card-toggle">
          <ChevronDown size={14} className="search-card-toggle-icon" style={{ transform: collapsed ? 'rotate(-90deg)' : '' }} />
        </span>
      </div>
      <div className={`search-card-results${collapsed ? ' collapsed' : ''}`}>
        {parsed.results.length > 0 ? (
          parsed.results.map((r, i) => <SearchResultItem key={i} title={r.title} url={r.url} snippet={r.snippet} />)
        ) : (
          <div style={{ padding: 16, textAlign: 'center', color: 'hsl(var(--muted-foreground))', fontSize: 13 }}>
            未找到相关结果
          </div>
        )}
      </div>
    </div>
  )
}

function SearchResultItem({ title, url, snippet }: { title: string; url: string; snippet: string }) {
  const [expanded, setExpanded] = useState(false)
  let domain = ''
  try {
    domain = new URL(url).hostname
  } catch {
    domain = url.slice(0, 40)
  }

  return (
    <div className={`search-result-item${expanded ? ' expanded' : ''}`}>
      <div className="search-result-title">
        {url ? (
          <a href={url} target="_blank" rel="noopener">{title}</a>
        ) : title}
      </div>
      <div className="search-result-url">
        <Link2 size={10} />
        {domain}
      </div>
      {snippet && <div className="search-result-snippet">{snippet}</div>}
      {snippet && snippet.length > 150 && (
        <div className="search-result-toggle" onClick={() => setExpanded(!expanded)}>
          {expanded ? '收起 ▴' : '展开全文 ▾'}
        </div>
      )}
    </div>
  )
}
