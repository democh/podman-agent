import { memo, useEffect, useRef, useState, useCallback, type ReactNode } from 'react'
import ReactMarkdown, { type Components } from 'react-markdown'
import remarkGfm from 'remark-gfm'
import remarkBreaks from 'remark-breaks'
import hljs from 'highlight.js/lib/core'
import 'highlight.js/styles/vs2015.css'
import 'katex/dist/katex.min.css'
// 按需注册常用语言（减小包体积）
import javascript from 'highlight.js/lib/languages/javascript'
import typescript from 'highlight.js/lib/languages/typescript'
import python from 'highlight.js/lib/languages/python'
import bash from 'highlight.js/lib/languages/bash'
import json from 'highlight.js/lib/languages/json'
import css from 'highlight.js/lib/languages/css'
import xml from 'highlight.js/lib/languages/xml'
import sql from 'highlight.js/lib/languages/sql'
import yaml from 'highlight.js/lib/languages/yaml'
import markdown from 'highlight.js/lib/languages/markdown'
import java from 'highlight.js/lib/languages/java'
import go from 'highlight.js/lib/languages/go'
import rust from 'highlight.js/lib/languages/rust'
import cpp from 'highlight.js/lib/languages/cpp'
import diff from 'highlight.js/lib/languages/diff'
import mermaid from 'mermaid'
import * as echarts from 'echarts/core'
import {
  BarChart, LineChart, PieChart, ScatterChart, RadarChart,
  FunnelChart, GaugeChart, TreemapChart, HeatmapChart, SunburstChart, CandlestickChart,
  BoxplotChart, PictorialBarChart, SankeyChart, TreeChart, GraphChart,
} from 'echarts/charts'
import {
  TitleComponent, TooltipComponent, LegendComponent,
  GridComponent, RadarComponent, VisualMapComponent,
  CalendarComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import remarkMath from 'remark-math'
import rehypeKatex from 'rehype-katex'

echarts.use([
  BarChart, LineChart, PieChart, ScatterChart, RadarChart,
  FunnelChart, GaugeChart, TreemapChart, HeatmapChart, SunburstChart, CandlestickChart,
  BoxplotChart, PictorialBarChart, SankeyChart, TreeChart, GraphChart,
  TitleComponent, TooltipComponent, LegendComponent, GridComponent, RadarComponent,
  VisualMapComponent, CalendarComponent,
  CanvasRenderer,
])

// ── PlantUML 图表组件 (via Kroki) ─────────────────────────────────
type DiagramView = 'preview' | 'code'

function PlantUMLBlock({ code }: { code: string }) {
  const [svg, setSvg] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [view, setView] = useState<DiagramView>('preview')
  const codeRef = useRef<HTMLElement>(null)

  useEffect(() => {
    if (!code.trim()) return
    setLoading(true)
    fetch('https://kroki.io/plantuml/svg', {
      method: 'POST',
      headers: { 'Content-Type': 'text/plain' },
      body: code,
    })
      .then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.text() })
      .then(svgText => { setSvg(svgText); setLoading(false) })
      .catch(e => { setError(String(e.message || e)); setLoading(false) })
    return () => { setLoading(false) }
  }, [code])

  useEffect(() => {
    if (view === 'code' && codeRef.current) {
      try { hljs.highlightElement(codeRef.current) } catch { /* ignore */ }
    }
  }, [view])

  return (
    <div className="diagram-block plantuml-block">
      <div className="diagram-toolbar">
        <span className="diagram-label">PlantUML</span>
        {error && <span className="diagram-error-label">渲染失败</span>}
        <div className="diagram-view-toggle">
          <button className={`diagram-view-btn${view === 'preview' ? ' active' : ''}`} onClick={() => setView('preview')}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M2.062 12.348a1 1 0 0 1 0-.696 10.75 10.75 0 0 1 19.876 0 1 1 0 0 1 0 .696 10.75 10.75 0 0 1-19.876 0"/><circle cx="12" cy="12" r="3"/></svg>
            <span>图表</span>
          </button>
          <button className={`diagram-view-btn${view === 'code' ? ' active' : ''}`} onClick={() => setView('code')}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>
            <span>代码</span>
          </button>
        </div>
      </div>
      {view === 'preview' ? (
        loading ? (
          <div className="diagram-loading"><div className="diagram-skeleton-bar" /></div>
        ) : error ? (
          <div className="diagram-error">
            <pre><code>{code}</code></pre>
            <div className="diagram-error-msg">{error}</div>
          </div>
        ) : (
          <div className="diagram-content" dangerouslySetInnerHTML={{ __html: svg }} />
        )
      ) : (
        <div className="diagram-code-view">
          <pre><code ref={codeRef} className="language-plantuml">{code}</code></pre>
        </div>
      )}
    </div>
  )
}

// ── D2 图表组件 (via Kroki) ────────────────────────────────────────
function D2Block({ code }: { code: string }) {
  const [svg, setSvg] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [view, setView] = useState<DiagramView>('preview')
  const codeRef = useRef<HTMLElement>(null)

  useEffect(() => {
    if (!code.trim()) return
    setLoading(true)
    fetch('https://kroki.io/d2/svg', {
      method: 'POST',
      headers: { 'Content-Type': 'text/plain' },
      body: code,
    })
      .then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.text() })
      .then(svgText => { setSvg(svgText); setLoading(false) })
      .catch(e => { setError(String(e.message || e)); setLoading(false) })
    return () => { setLoading(false) }
  }, [code])

  useEffect(() => {
    if (view === 'code' && codeRef.current) {
      try { hljs.highlightElement(codeRef.current) } catch { /* ignore */ }
    }
  }, [view])

  return (
    <div className="diagram-block d2-block">
      <div className="diagram-toolbar">
        <span className="diagram-label">D2</span>
        {error && <span className="diagram-error-label">渲染失败</span>}
        <div className="diagram-view-toggle">
          <button className={`diagram-view-btn${view === 'preview' ? ' active' : ''}`} onClick={() => setView('preview')}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M2.062 12.348a1 1 0 0 1 0-.696 10.75 10.75 0 0 1 19.876 0 1 1 0 0 1 0 .696 10.75 10.75 0 0 1-19.876 0"/><circle cx="12" cy="12" r="3"/></svg>
            <span>图表</span>
          </button>
          <button className={`diagram-view-btn${view === 'code' ? ' active' : ''}`} onClick={() => setView('code')}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>
            <span>代码</span>
          </button>
        </div>
      </div>
      {view === 'preview' ? (
        loading ? (
          <div className="diagram-loading"><div className="diagram-skeleton-bar" /></div>
        ) : error ? (
          <div className="diagram-error">
            <pre><code>{code}</code></pre>
            <div className="diagram-error-msg">{error}</div>
          </div>
        ) : (
          <div className="diagram-content" dangerouslySetInnerHTML={{ __html: svg }} />
        )
      ) : (
        <div className="diagram-code-view">
          <pre><code ref={codeRef} className="language-d2">{code}</code></pre>
        </div>
      )}
    </div>
  )
}

// ── HTML 代码块组件（代码高亮 + 展开预览）──────────────────────────
function HtmlPreviewBlock({ code }: { code: string }) {
  const codeRef = useRef<HTMLElement>(null)
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    if (codeRef.current) {
      try { hljs.highlightElement(codeRef.current) } catch { /* ignore */ }
    }
  }, [])

  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(code)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      const ta = document.createElement('textarea')
      ta.value = code; ta.style.position = 'fixed'; ta.style.opacity = '0'
      document.body.appendChild(ta); ta.select(); document.execCommand('copy')
      document.body.removeChild(ta); setCopied(true); setTimeout(() => setCopied(false), 2000)
    }
  }, [code])

  const openInNewWindow = () => {
    const blob = new Blob([code], { type: 'text/html' })
    const url = URL.createObjectURL(blob)
    window.open(url, '_blank', 'width=900,height=700')
  }

  return (
    <div className="diagram-block html-preview-block">
      <div className="diagram-toolbar">
        <span className="diagram-label">HTML</span>
        <div className="diagram-view-toggle">
          <button className="diagram-view-btn" onClick={handleCopy} title={copied ? '已复制' : '复制代码'}>
            {copied ? (
              <><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12"/></svg><span>已复制</span></>
            ) : (
              <><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect width="14" height="14" x="8" y="8" rx="2" ry="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/></svg><span>复制</span></>
            )}
          </button>
          <button className="diagram-view-btn" onClick={openInNewWindow} title="在新窗口预览">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
            <span>展开</span>
          </button>
        </div>
      </div>
      <div className="diagram-code-view">
        <pre><code ref={codeRef} className="language-html">{code}</code></pre>
      </div>
    </div>
  )
}

// ── SVG 实时预览组件 ───────────────────────────────────────────────
function SvgPreviewBlock({ code }: { code: string }) {
  const [view, setView] = useState<DiagramView>('preview')
  const codeRef = useRef<HTMLElement>(null)
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    if (view === 'code' && codeRef.current) {
      try { hljs.highlightElement(codeRef.current) } catch { /* ignore */ }
    }
  }, [view])

  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(code)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      const ta = document.createElement('textarea')
      ta.value = code; ta.style.position = 'fixed'; ta.style.opacity = '0'
      document.body.appendChild(ta); ta.select(); document.execCommand('copy')
      document.body.removeChild(ta); setCopied(true); setTimeout(() => setCopied(false), 2000)
    }
  }, [code])

  return (
    <div className="diagram-block svg-preview-block">
      <div className="diagram-toolbar">
        <span className="diagram-label">SVG</span>
        <div className="diagram-view-toggle">
          <button className={`diagram-view-btn${view === 'preview' ? ' active' : ''}`} onClick={() => setView('preview')}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M2.062 12.348a1 1 0 0 1 0-.696 10.75 10.75 0 0 1 19.876 0 1 1 0 0 1 0 .696 10.75 10.75 0 0 1-19.876 0"/><circle cx="12" cy="12" r="3"/></svg>
            <span>预览</span>
          </button>
          <button className={`diagram-view-btn${view === 'code' ? ' active' : ''}`} onClick={() => setView('code')}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>
            <span>代码</span>
          </button>
          <button className="diagram-view-btn" onClick={handleCopy} title={copied ? '已复制' : '复制代码'}>
            {copied ? (
              <><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12"/></svg><span>已复制</span></>
            ) : (
              <><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect width="14" height="14" x="8" y="8" rx="2" ry="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/></svg><span>复制</span></>
            )}
          </button>
        </div>
      </div>
      {view === 'preview' ? (
        <div className="diagram-content svg-preview-content">
          <div dangerouslySetInnerHTML={{ __html: code }} />
        </div>
      ) : (
        <div className="diagram-code-view">
          <pre><code ref={codeRef} className="language-xml">{code}</code></pre>
        </div>
      )}
    </div>
  )
}

// ── Admonition 提示块 ──────────────────────────────────────────────
type AdmonitionType = 'note' | 'tip' | 'important' | 'warning' | 'caution'

const ADMONITION_ICONS: Record<AdmonitionType, ReactNode> = {
  note: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/></svg>,
  tip: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M15 14c.2-1 .7-1.7 1.7-1.7 1 0 1.5.7 1.7 1.7.2 1 .2 2.3-.7 3.3-.5.6-.7 1.3-.7 2 0 .4 0 .8-.2 1.2H7.2c-.2-.4-.2-.8-.2-1.2 0-.7-.2-1.4-.7-2-.9-1-.9-2.3-.7-3.3"/><path d="M9 18h6"/><path d="M10 22h4"/></svg>,
  important: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 22c5.5 0 10-4.5 10-10S17.5 2 12 2 2 6.5 2 12s4.5 10 10 10"/><path d="m9 12 2 2 4-4"/></svg>,
  warning: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3"/><path d="M12 9v4"/><path d="M12 17h.01"/></svg>,
  caution: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3"/><path d="M12 9v4"/><path d="M12 17h.01"/></svg>,
}

const ADMONITION_LABELS: Record<AdmonitionType, string> = {
  note: '注意', tip: '提示', important: '重要', warning: '警告', caution: '注意',
}

function extractTextContent(node: ReactNode): string {
  if (typeof node === 'string') return node
  if (typeof node === 'number') return String(node)
  if (Array.isArray(node)) return node.map(extractTextContent).join('')
  if (node && typeof node === 'object' && 'props' in node)
    return extractTextContent((node as { props: { children?: ReactNode } }).props.children)
  return ''
}

function stripAdmonitionHead(children: ReactNode): ReactNode {
  const arr = Array.isArray(children) ? children : [children]
  if (arr.length === 0) return null
  const first = arr[0]
  if (first && typeof first === 'object' && 'props' in first) {
    const text = extractTextContent(first)
    if (/^\s*\[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\]/i.test(text)) {
      const cleaned = text.replace(/^\s*\[!\w+\]\s*\n?/, '')
      if (!cleaned.trim()) return arr.slice(1)
      return [<span key="adm-body">{cleaned}</span>, ...arr.slice(1)]
    }
  }
  return children
}

// 图表配色板
const CHART_PALETTE = [
  '#3b82f6', '#22c55e', '#f59e0b', '#ef4444', '#8b5cf6',
  '#06b6d4', '#ec4899', '#14b8a6', '#f97316', '#6366f1',
]

// 注册语言
hljs.registerLanguage('javascript', javascript)
hljs.registerLanguage('js', javascript)
hljs.registerLanguage('typescript', typescript)
hljs.registerLanguage('ts', typescript)
hljs.registerLanguage('python', python)
hljs.registerLanguage('py', python)
hljs.registerLanguage('bash', bash)
hljs.registerLanguage('sh', bash)
hljs.registerLanguage('shell', bash)
hljs.registerLanguage('json', json)
hljs.registerLanguage('css', css)
hljs.registerLanguage('html', xml)
hljs.registerLanguage('xml', xml)
hljs.registerLanguage('sql', sql)
hljs.registerLanguage('yaml', yaml)
hljs.registerLanguage('yml', yaml)
hljs.registerLanguage('markdown', markdown)
hljs.registerLanguage('md', markdown)
hljs.registerLanguage('java', java)
hljs.registerLanguage('go', go)
hljs.registerLanguage('rust', rust)
hljs.registerLanguage('cpp', cpp)
hljs.registerLanguage('c', cpp)
hljs.registerLanguage('diff', diff)

// 初始化 mermaid
mermaid.initialize({
  startOnLoad: false,
  theme: 'neutral',
  fontFamily: 'Inter, -apple-system, BlinkMacSystemFont, sans-serif',
  fontSize: 14,
  securityLevel: 'loose',
  flowchart: { curve: 'basis', htmlLabels: true },
  sequence: { mirrorActors: false, messageFontSize: 13 },
})

// ── Mermaid 渲染组件 ────────────────────────────────────────────
let mermaidId = 0

type MermaidView = 'preview' | 'code'

function MermaidBlock({ code }: { code: string }) {
  const containerRef = useRef<HTMLDivElement>(null)
  const codeRef = useRef<HTMLElement>(null)
  const [svg, setSvg] = useState<string>('')
  const [error, setError] = useState<string>('')
  const [loading, setLoading] = useState(true)
  const [view, setView] = useState<MermaidView>('preview')
  const [zoom, setZoom] = useState(1)
  const [offset, setOffset] = useState({ x: 0, y: 0 })
  const contentRef = useRef<HTMLDivElement>(null)
  const isDragging = useRef(false)
  const dragState = useRef<{ startX: number; startY: number; origX: number; origY: number }>({
    startX: 0, startY: 0, origX: 0, origY: 0,
  })

  useEffect(() => {
    if (!code.trim()) return
    setLoading(true)
    const id = `mermaid-${mermaidId++}`
    mermaid.render(id, code)
      .then(({ svg }) => { setSvg(svg); setLoading(false) })
      .catch((e) => { setError(String(e.message || e)); setLoading(false) })
  }, [code])

  // 代码视图时高亮
  useEffect(() => {
    if (view === 'code' && codeRef.current) {
      try {
        hljs.highlightElement(codeRef.current)
      } catch { /* ignore */ }
    }
  }, [view])

  // 滚轮缩放
  const handleWheel = (e: React.WheelEvent) => {
    if (!e.ctrlKey && !e.metaKey) return
    e.preventDefault()
    setZoom((z) => Math.min(3, Math.max(0.25, z + (e.deltaY < 0 ? 0.1 : -0.1))))
  }

  // 拖动平移
  const handleMouseDown = (e: React.MouseEvent) => {
    if (zoom <= 1) return
    e.preventDefault()
    isDragging.current = true
    contentRef.current?.classList.add('mermaid-dragging')
    dragState.current = { startX: e.clientX, startY: e.clientY, origX: offset.x, origY: offset.y }
  }
  const handleMouseMove = (e: React.MouseEvent) => {
    if (!isDragging.current) return
    const ds = dragState.current
    setOffset({ x: ds.origX + (e.clientX - ds.startX), y: ds.origY + (e.clientY - ds.startY) })
  }
  const handleMouseUp = () => {
    isDragging.current = false
    contentRef.current?.classList.remove('mermaid-dragging')
  }

  const zoomIn = () => setZoom((z) => Math.min(3, +(z + 0.25).toFixed(2)))
  const zoomOut = () => setZoom((z) => Math.max(0.25, +(z - 0.25).toFixed(2)))
  const zoomReset = () => { setZoom(1); setOffset({ x: 0, y: 0 }) }

  if (error) {
    return (
      <div className="mermaid-block mermaid-error-block">
        <div className="mermaid-toolbar">
          <span className="mermaid-label">Mermaid</span>
          <span className="mermaid-error-label">渲染失败</span>
        </div>
        <pre className="mermaid-error">
          <code>{code}</code>
          <div className="mermaid-error-msg">{error}</div>
        </pre>
      </div>
    )
  }

  const canDrag = zoom > 1

  return (
    <div className="mermaid-block" ref={containerRef}>
      <div className="mermaid-toolbar">
        <span className="mermaid-label">Mermaid</span>
        <div className="mermaid-view-toggle">
          <button
            className={`mermaid-view-btn${view === 'preview' ? ' active' : ''}`}
            onClick={() => setView('preview')}
            title="查看图表"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M2.062 12.348a1 1 0 0 1 0-.696 10.75 10.75 0 0 1 19.876 0 1 1 0 0 1 0 .696 10.75 10.75 0 0 1-19.876 0"/><circle cx="12" cy="12" r="3"/></svg>
            <span>图表</span>
          </button>
          <button
            className={`mermaid-view-btn${view === 'code' ? ' active' : ''}`}
            onClick={() => setView('code')}
            title="查看代码"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>
            <span>代码</span>
          </button>
        </div>
        {view === 'preview' && !loading && (
          <div className="mermaid-zoom-controls">
            <button className="mermaid-zoom-btn" onClick={zoomOut} title="缩小" disabled={zoom <= 0.25}>−</button>
            <span className="mermaid-zoom-label" onClick={zoomReset} title="点击重置">{Math.round(zoom * 100)}%</span>
            <button className="mermaid-zoom-btn" onClick={zoomIn} title="放大" disabled={zoom >= 3}>+</button>
          </div>
        )}
      </div>
      {view === 'preview' ? (
        <div
          ref={contentRef}
          className={`mermaid-content${canDrag ? ' mermaid-draggable' : ''}`}
          onWheel={handleWheel}
          onMouseDown={handleMouseDown}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          onMouseLeave={handleMouseUp}
        >
          {loading ? (
            <div className="mermaid-skeleton">
              <div className="mermaid-skeleton-bar" />
              <div className="mermaid-skeleton-bar short" />
            </div>
          ) : (
            <div
              className="mermaid-svg-wrapper"
              style={{
                transform: `translate(${offset.x}px, ${offset.y}px) scale(${zoom})`,
                transformOrigin: 'top center',
              }}
              dangerouslySetInnerHTML={{ __html: svg }}
            />
          )}
        </div>
      ) : (
        <div className="mermaid-code-view">
          <pre>
            <code ref={codeRef} className="language-mermaid">{code}</code>
          </pre>
        </div>
      )}
    </div>
  )
}

// ── ECharts 数据图表组件 ────────────────────────────────────────
type ChartView = 'preview' | 'code'

interface ChartConfig {
  type: 'bar' | 'line' | 'pie' | 'scatter' | 'radar' | 'area'
    | 'funnel' | 'gauge' | 'treemap' | 'heatmap' | 'sunburst' | 'candlestick'
    | 'boxplot' | 'pictorialBar' | 'sankey' | 'tree' | 'graph'
  title?: string
  xAxis?: string[]
  yAxis?: string[]
  series: Array<{
    name?: string
    data: unknown[]
    children?: unknown[]
    value?: number
    links?: Array<{ source: string; target: string; value?: number }>
    nodes?: Array<{ name: string; value?: number; symbolSize?: number }>
  }>
  legend?: boolean
  smooth?: boolean
  stack?: boolean
  min?: number
  max?: number
  unit?: string
  orient?: string
  shape?: string
  layout?: string
  roam?: boolean
  edgeLabel?: boolean
  symbolSize?: number
}

function buildOption(cfg: ChartConfig): echarts.EChartsCoreOption {
  const type = cfg.type === 'area' ? 'line' : cfg.type
  const colors = CHART_PALETTE

  // 饼图
  if (type === 'pie') {
    const data = (cfg.series[0]?.data ?? []).map((v, i) => ({
      name: cfg.xAxis?.[i] ?? cfg.series[0]?.name ?? `项${i + 1}`,
      value: typeof v === 'number' ? v : 0,
    }))
    return {
      color: colors,
      title: cfg.title ? { text: cfg.title, left: 'center', textStyle: { fontSize: 14, fontWeight: 600, color: '#1e293b' } } : undefined,
      tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
      legend: cfg.legend !== false ? { bottom: 8, textStyle: { fontSize: 12 } } : undefined,
      series: [{ type: 'pie', radius: ['35%', '65%'], center: ['50%', '50%'], data, label: { show: true, fontSize: 11 }, emphasis: { itemStyle: { shadowBlur: 10, shadowColor: 'rgba(0,0,0,0.15)' } } }],
    }
  }

  // 雷达图
  if (type === 'radar') {
    const indicator = (cfg.xAxis ?? []).map((name) => ({ name, max: Math.max(...cfg.series.flatMap((s) => s.data as number[])) * 1.2 || 100 }))
    return {
      color: colors,
      title: cfg.title ? { text: cfg.title, left: 'center', textStyle: { fontSize: 14, fontWeight: 600, color: '#1e293b' } } : undefined,
      tooltip: { trigger: 'item' },
      legend: cfg.legend !== false ? { bottom: 8, textStyle: { fontSize: 12 } } : undefined,
      radar: { indicator, radius: '60%' },
      series: [{ type: 'radar', data: cfg.series.map((s, i) => ({ name: s.name || `系列${i + 1}`, value: s.data })) }],
    }
  }

  // 散点图
  if (type === 'scatter') {
    return {
      color: colors,
      title: cfg.title ? { text: cfg.title, left: 'center', textStyle: { fontSize: 14, fontWeight: 600, color: '#1e293b' } } : undefined,
      tooltip: { trigger: 'item' },
      legend: cfg.legend !== false && cfg.series.length > 1 ? { bottom: 8, textStyle: { fontSize: 12 } } : undefined,
      xAxis: { type: 'value', splitLine: { lineStyle: { color: '#e2e8f0' } }, axisLine: { lineStyle: { color: '#94a3b8' } } },
      yAxis: { type: 'value', splitLine: { lineStyle: { color: '#e2e8f0' } }, axisLine: { lineStyle: { color: '#94a3b8' } } },
      grid: { left: 50, right: 20, top: cfg.title ? 40 : 20, bottom: cfg.legend !== false && cfg.series.length > 1 ? 50 : 30 },
      series: cfg.series.map((s, i) => ({
        name: s.name || `系列${i + 1}`,
        type: 'scatter',
        symbolSize: 10,
        data: s.data as Array<[number, number]>,
      })),
    }
  }

  // 漏斗图
  if (type === 'funnel') {
    const data = (cfg.series[0]?.data ?? []).map((v, i) => ({
      name: cfg.xAxis?.[i] ?? `项${i + 1}`,
      value: typeof v === 'number' ? v : 0,
    }))
    return {
      color: colors,
      title: cfg.title ? { text: cfg.title, left: 'center', textStyle: { fontSize: 14, fontWeight: 600, color: '#1e293b' } } : undefined,
      tooltip: { trigger: 'item', formatter: '{b}: {c}' },
      legend: cfg.legend !== false ? { bottom: 8, textStyle: { fontSize: 12 } } : undefined,
      series: [{
        type: 'funnel', left: '15%', right: '15%', top: cfg.title ? 50 : 20, bottom: cfg.legend !== false ? 50 : 20,
        min: cfg.min ?? 0, max: cfg.max ?? Math.max(...data.map((d) => d.value)) * 1.1,
        sort: 'descending', gap: 2,
        label: { show: true, position: 'inside', fontSize: 12, color: '#fff' },
        itemStyle: { borderWidth: 0 },
        data,
      }],
    }
  }

  // 仪表盘
  if (type === 'gauge') {
    const val = typeof cfg.series[0]?.data?.[0] === 'number'
      ? cfg.series[0].data[0] as number
      : (cfg.series[0]?.value ?? 0)
    return {
      color: colors,
      title: cfg.title ? { text: cfg.title, left: 'center', top: 10, textStyle: { fontSize: 14, fontWeight: 600, color: '#1e293b' } } : undefined,
      tooltip: { formatter: `{b}: ${val}${cfg.unit || '%'}` },
      series: [{
        type: 'gauge',
        radius: '85%',
        min: cfg.min ?? 0,
        max: cfg.max ?? 100,
        progress: { show: true, width: 14, roundCap: true },
        axisLine: { lineStyle: { width: 14, color: [[1, '#e2e8f0']] } },
        axisTick: { show: false },
        splitLine: { length: 8, lineStyle: { width: 2, color: '#94a3b8' } },
        axisLabel: { distance: 20, fontSize: 11, color: '#64748b' },
        pointer: { width: 4, length: '60%' },
        anchor: { show: true, size: 12, itemStyle: { borderWidth: 2, borderColor: colors[0] } },
        detail: {
          valueAnimation: true, fontSize: 24, fontWeight: 700, color: '#1e293b',
          offsetCenter: [0, '70%'],
          formatter: `${val}${cfg.unit || '%'}`,
        },
        data: [{ value: val, name: cfg.series[0]?.name || '' }],
      }],
    }
  }

  // 矩形树图
  if (type === 'treemap') {
    const buildTreemapData = (items: unknown[]): Array<{ name: string; value?: number; children?: unknown[] }> => {
      if (!Array.isArray(items)) return []
      return items.map((item) => {
        if (typeof item === 'object' && item !== null) {
          const obj = item as Record<string, unknown>
          return {
            name: String(obj.name ?? ''),
            value: typeof obj.value === 'number' ? obj.value : undefined,
            children: obj.children ? buildTreemapData(obj.children as unknown[]) : undefined,
          }
        }
        return { name: String(item), value: 1 }
      })
    }
    return {
      color: colors,
      title: cfg.title ? { text: cfg.title, left: 'center', textStyle: { fontSize: 14, fontWeight: 600, color: '#1e293b' } } : undefined,
      tooltip: { trigger: 'item', formatter: '{b}: {c}' },
      series: [{
        type: 'treemap',
        top: cfg.title ? 40 : 10,
        breadcrumb: { show: false },
        label: { show: true, fontSize: 12, color: '#fff', formatter: '{b}\n{c}' },
        itemStyle: { borderColor: '#1e293b', borderWidth: 1, gapWidth: 1 },
        levels: [
          { itemStyle: { borderWidth: 2, borderColor: '#334155', gapWidth: 2 }, upperLabel: { show: false } },
          { colorSaturation: [0.35, 0.5], itemStyle: { borderColorSaturation: 0.6, gapWidth: 1, borderWidth: 1 } },
        ],
        data: buildTreemapData(cfg.series[0]?.children ?? cfg.series[0]?.data ?? []),
      }],
    }
  }

  // 旭日图
  if (type === 'sunburst') {
    const buildSunburstData = (items: unknown[]): Array<{ name: string; value?: number; children?: unknown[] }> => {
      if (!Array.isArray(items)) return []
      return items.map((item) => {
        if (typeof item === 'object' && item !== null) {
          const obj = item as Record<string, unknown>
          return {
            name: String(obj.name ?? ''),
            value: typeof obj.value === 'number' ? obj.value : undefined,
            children: obj.children ? buildSunburstData(obj.children as unknown[]) : undefined,
          }
        }
        return { name: String(item), value: 1 }
      })
    }
    return {
      color: colors,
      title: cfg.title ? { text: cfg.title, left: 'center', textStyle: { fontSize: 14, fontWeight: 600, color: '#1e293b' } } : undefined,
      tooltip: { trigger: 'item', formatter: '{b}: {c}' },
      series: [{
        type: 'sunburst',
        radius: ['15%', '85%'],
        top: cfg.title ? 40 : 10,
        label: { fontSize: 11, color: '#1e293b', minAngle: 15 },
        itemStyle: { borderColor: '#1e293b', borderWidth: 1, borderRadius: 2 },
        emphasis: { itemStyle: { shadowBlur: 10, shadowColor: 'rgba(0,0,0,0.2)' } },
        data: buildSunburstData(cfg.series[0]?.children ?? cfg.series[0]?.data ?? []),
      }],
    }
  }

  // 热力图
  if (type === 'heatmap') {
    const xData = cfg.xAxis ?? []
    const yData = cfg.yAxis ?? []
    const heatData = cfg.series[0]?.data ?? []
    const allValues = heatData.map((d) => (Array.isArray(d) ? d[2] : 0)) as number[]
    const minVal = cfg.min ?? Math.min(...allValues)
    const maxVal = cfg.max ?? Math.max(...allValues)
    return {
      color: colors,
      title: cfg.title ? { text: cfg.title, left: 'center', textStyle: { fontSize: 14, fontWeight: 600, color: '#1e293b' } } : undefined,
      tooltip: { position: 'top', formatter: (p: unknown) => { const d = (p as { data: number[] }).data; return `${xData[d[0]] ?? d[0]} / ${yData[d[1]] ?? d[1]}: ${d[2]}` } },
      xAxis: { type: 'category', data: xData, axisLine: { lineStyle: { color: '#94a3b8' } }, axisLabel: { color: '#475569', fontSize: 11 }, splitArea: { show: true } },
      yAxis: { type: 'category', data: yData, axisLine: { lineStyle: { color: '#94a3b8' } }, axisLabel: { color: '#475569', fontSize: 11 }, splitArea: { show: true } },
      visualMap: {
        min: minVal, max: maxVal, calculable: true,
        orient: 'horizontal', left: 'center', bottom: 8,
        inRange: { color: ['#dbeafe', '#3b82f6', '#1e3a5f'] },
        textStyle: { fontSize: 11 },
      },
      grid: { left: 60, right: 20, top: cfg.title ? 45 : 20, bottom: 60 },
      series: [{ type: 'heatmap', data: heatData as number[][], label: { show: true, fontSize: 11 }, emphasis: { itemStyle: { shadowBlur: 10, shadowColor: 'rgba(0,0,0,0.2)' } } }],
    }
  }

  // K线图
  if (type === 'candlestick') {
    const candleData = cfg.series[0]?.data ?? []
    return {
      color: colors,
      title: cfg.title ? { text: cfg.title, left: 'center', textStyle: { fontSize: 14, fontWeight: 600, color: '#1e293b' } } : undefined,
      tooltip: { trigger: 'axis', axisPointer: { type: 'cross' } },
      xAxis: {
        type: 'category',
        data: cfg.xAxis ?? candleData.map((_, i) => `${i + 1}`),
        axisLine: { lineStyle: { color: '#94a3b8' } },
        axisLabel: { color: '#475569', fontSize: 11 },
      },
      yAxis: {
        type: 'value',
        scale: true,
        splitLine: { lineStyle: { color: '#e2e8f0' } },
        axisLine: { show: false },
        axisLabel: { color: '#475569', fontSize: 11 },
      },
      grid: { left: 55, right: 20, top: cfg.title ? 40 : 20, bottom: 30 },
      series: [{
        type: 'candlestick',
        data: candleData,
        itemStyle: {
          color: '#ef4444', color0: '#22c55e',
          borderColor: '#ef4444', borderColor0: '#22c55e',
        },
      }],
    }
  }

  // 箱线图
  if (type === 'boxplot') {
    const boxData = cfg.series[0]?.data ?? []
    return {
      color: colors,
      title: cfg.title ? { text: cfg.title, left: 'center', textStyle: { fontSize: 14, fontWeight: 600, color: '#1e293b' } } : undefined,
      tooltip: { trigger: 'item', formatter: (p: unknown) => { const d = (p as { data: number[] }).data; return `最小: ${d[1]}<br/>Q1: ${d[2]}<br/>中位数: ${d[3]}<br/>Q3: ${d[4]}<br/>最大: ${d[5]}` } },
      xAxis: {
        type: 'category',
        data: cfg.xAxis ?? boxData.map((_, i) => `${i + 1}`),
        axisLine: { lineStyle: { color: '#94a3b8' } },
        axisLabel: { color: '#475569', fontSize: 11 },
      },
      yAxis: {
        type: 'value',
        scale: true,
        splitLine: { lineStyle: { color: '#e2e8f0' } },
        axisLine: { show: false },
        axisLabel: { color: '#475569', fontSize: 11 },
      },
      grid: { left: 55, right: 20, top: cfg.title ? 40 : 20, bottom: 30 },
      series: [{
        type: 'boxplot',
        data: boxData,
        itemStyle: { color: '#fff', borderColor: colors[0], borderWidth: 2 },
        emphasis: { itemStyle: { shadowBlur: 10, shadowColor: 'rgba(0,0,0,0.15)' } },
      }],
    }
  }

  // 象形柱图
  if (type === 'pictorialBar') {
    const maxVal = Math.max(...(cfg.series[0]?.data as number[] ?? [100]))
    return {
      color: colors,
      title: cfg.title ? { text: cfg.title, left: 'center', textStyle: { fontSize: 14, fontWeight: 600, color: '#1e293b' } } : undefined,
      tooltip: { trigger: 'axis' },
      legend: cfg.legend !== false && cfg.series.length > 1 ? { bottom: 8, textStyle: { fontSize: 12 } } : undefined,
      xAxis: {
        type: 'category',
        data: cfg.xAxis ?? (cfg.series[0]?.data as number[] ?? []).map((_, i) => `${i + 1}`),
        axisLine: { lineStyle: { color: '#94a3b8' } },
        axisLabel: { color: '#475569', fontSize: 11 },
      },
      yAxis: {
        type: 'value',
        max: maxVal * 1.2,
        splitLine: { lineStyle: { color: '#e2e8f0' } },
        axisLine: { show: false },
        axisLabel: { color: '#475569', fontSize: 11 },
      },
      grid: { left: 50, right: 20, top: cfg.title ? 40 : 20, bottom: cfg.legend !== false && cfg.series.length > 1 ? 50 : 30 },
      series: cfg.series.map((s, i) => ({
        name: s.name || `系列${i + 1}`,
        type: 'pictorialBar',
        barCategoryGap: '40%',
        symbol: cfg.shape || 'roundRect',
        barWidth: '50%',
        symbolRepeat: false,
        symbolClip: true,
        symbolPosition: 'start',
        symbolSize: ['100%', '100%'],
        data: s.data,
        itemStyle: { color: colors[i % colors.length] },
        emphasis: { itemStyle: { color: colors[(i + 1) % colors.length] } },
      })),
    }
  }

  // 桑基图
  if (type === 'sankey') {
    const nodes = cfg.series[0]?.nodes ?? []
    const links = cfg.series[0]?.links ?? []
    // DAG 循环检测：给出更友好的中文错误提示
    const adj = new Map<string, Set<string>>()
    for (const l of links as Array<{ source: string; target: string; value?: number }>) {
      if (!adj.has(l.source)) adj.set(l.source, new Set())
      adj.get(l.source)!.add(l.target)
    }
    const visited = new Set<string>()
    const stack = new Set<string>()
    const hasCycle = (node: string): boolean => {
      if (stack.has(node)) return true
      if (visited.has(node)) return false
      visited.add(node)
      stack.add(node)
      for (const next of adj.get(node) ?? []) { if (hasCycle(next)) return true }
      stack.delete(node)
      return false
    }
    for (const n of nodes as Array<{ name: string }>) {
      if (hasCycle(n.name)) throw new Error('桑基图数据存在循环（DAG 要求单向流动，不能有 A→B→A 的回流）')
    }
    return {
      color: colors,
      title: cfg.title ? { text: cfg.title, left: 'center', textStyle: { fontSize: 14, fontWeight: 600, color: '#1e293b' } } : undefined,
      tooltip: { trigger: 'item', formatter: (p: unknown) => { const d = p as { dataType?: string; name?: string; data?: { source?: string; target?: string; value?: number } }; return d.dataType === 'edge' ? `${d.data?.source} → ${d.data?.target}: ${d.data?.value}` : `${d.name}` } },
      series: [{
        type: 'sankey',
        top: cfg.title ? 40 : 10,
        bottom: 20,
        left: 30,
        right: 30,
        orient: (cfg.orient as 'horizontal' | 'vertical') || 'horizontal',
        layoutIterations: 32,
        nodeAlign: 'justify',
        nodeWidth: 20,
        nodeGap: 12,
        label: { show: true, fontSize: 12, color: '#1e293b' },
        lineStyle: { color: 'gradient', opacity: 0.4, curveness: 0.5 },
        emphasis: { focus: 'adjacency', lineStyle: { opacity: 0.6 } },
        data: nodes.map((n: { name: string; value?: number }) => ({ name: n.name, value: n.value })),
        links: links.map((l: { source: string; target: string; value?: number }) => ({ source: l.source, target: l.target, value: l.value ?? 0 })),
      }],
    }
  }

  // 树图
  if (type === 'tree') {
    const buildTreeData = (items: unknown[]): Array<{ name: string; value?: number; children?: unknown[] }> => {
      if (!Array.isArray(items)) return []
      return items.map((item) => {
        if (typeof item === 'object' && item !== null) {
          const obj = item as Record<string, unknown>
          return {
            name: String(obj.name ?? ''),
            value: typeof obj.value === 'number' ? obj.value : undefined,
            children: obj.children ? buildTreeData(obj.children as unknown[]) : undefined,
          }
        }
        return { name: String(item), value: 1 }
      })
    }
    return {
      color: colors,
      title: cfg.title ? { text: cfg.title, left: 'center', textStyle: { fontSize: 14, fontWeight: 600, color: '#1e293b' } } : undefined,
      tooltip: { trigger: 'item', formatter: '{b}' },
      series: [{
        type: 'tree',
        top: cfg.title ? 40 : 10,
        bottom: 20,
        left: 60,
        right: 60,
        orient: (cfg.orient as 'horizontal' | 'vertical') || 'horizontal',
        symbol: 'circle',
        symbolSize: 8,
        initialTreeDepth: 3,
        label: { position: 'left', verticalAlign: 'middle', align: 'right', fontSize: 12, color: '#1e293b' },
        leaves: { label: { position: 'right', verticalAlign: 'middle', align: 'left' } },
        expandAndCollapse: true,
        animationDuration: 550,
        animationDurationUpdate: 750,
        emphasis: { focus: 'descendant' },
        data: buildTreeData(cfg.series[0]?.children ?? cfg.series[0]?.data ?? []),
      }],
    }
  }

  // 关系图
  if (type === 'graph') {
    const nodes = cfg.series[0]?.nodes ?? []
    const links = cfg.series[0]?.links ?? []
    return {
      color: colors,
      title: cfg.title ? { text: cfg.title, left: 'center', textStyle: { fontSize: 14, fontWeight: 600, color: '#1e293b' } } : undefined,
      tooltip: { trigger: 'item' },
      legend: cfg.legend !== false && cfg.series.length > 1 ? { bottom: 8, textStyle: { fontSize: 12 } } : undefined,
      series: [{
        type: 'graph',
        top: cfg.title ? 40 : 10,
        bottom: 20,
        layout: (cfg.layout as 'force' | 'circular' | 'none') || 'force',
        roam: cfg.roam !== false,
        draggable: true,
        symbolSize: cfg.symbolSize || 40,
        label: { show: true, fontSize: 11, color: '#fff' },
        edgeLabel: cfg.edgeLabel ? { show: true, fontSize: 10, formatter: (p: unknown) => (p as { data?: { value?: number } }).data?.value ?? '' } : undefined,
        force: cfg.layout !== 'circular' ? { repulsion: 300, edgeLength: [80, 200], gravity: 0.1 } : undefined,
        emphasis: { focus: 'adjacency', lineStyle: { width: 3 } },
        lineStyle: { color: 'source', curveness: 0.2, opacity: 0.6 },
        categories: cfg.series.length > 1 ? cfg.series.map((s, i) => ({ name: s.name || `分类${i + 1}` })) : undefined,
        data: nodes.map((n: { name: string; value?: number; symbolSize?: number }, i: number) => ({
          name: n.name,
          value: n.value,
          symbolSize: n.symbolSize,
          category: cfg.series.length > 1 ? i % cfg.series.length : undefined,
        })),
        links: links.map((l: { source: string; target: string; value?: number }) => ({ source: l.source, target: l.target, value: l.value })),
      }],
    }
  }

  // 柱状图 / 折线图 / 面积图
  const isArea = cfg.type === 'area'
  return {
    color: colors,
    title: cfg.title ? { text: cfg.title, left: 'center', textStyle: { fontSize: 14, fontWeight: 600, color: '#1e293b' } } : undefined,
    tooltip: { trigger: 'axis' },
    legend: cfg.legend !== false && cfg.series.length > 1 ? { bottom: 8, textStyle: { fontSize: 12 } } : undefined,
    xAxis: {
      type: 'category',
      data: cfg.xAxis ?? cfg.series[0]?.data?.map((_, i) => `${i + 1}`),
      axisLine: { lineStyle: { color: '#94a3b8' } },
      axisLabel: { color: '#475569', fontSize: 11 },
    },
    yAxis: {
      type: 'value',
      splitLine: { lineStyle: { color: '#e2e8f0' } },
      axisLine: { show: false },
      axisLabel: { color: '#475569', fontSize: 11 },
    },
    grid: { left: 50, right: 20, top: cfg.title ? 40 : 20, bottom: cfg.legend !== false && cfg.series.length > 1 ? 50 : 30 },
    series: cfg.series.map((s, i) => ({
      name: s.name || `系列${i + 1}`,
      type: type as 'bar' | 'line',
      data: s.data,
      smooth: cfg.smooth !== false && type === 'line',
      stack: cfg.stack ? 'total' : undefined,
      areaStyle: isArea ? { opacity: 0.15 } : undefined,
      itemStyle: type === 'bar' ? { borderRadius: [4, 4, 0, 0] } : undefined,
    })),
  }
}

function ChartBlock({ code }: { code: string }) {
  const chartRef = useRef<HTMLDivElement>(null)
  const codeRef = useRef<HTMLElement>(null)
  const [error, setError] = useState<string>('')
  const [view, setView] = useState<ChartView>('preview')
  const [config, setConfig] = useState<ChartConfig | null>(null)

  // 解析 JSON
  useEffect(() => {
    try {
      const parsed = JSON.parse(code)
      if (!parsed.type || !parsed.series) throw new Error('缺少 type 或 series 字段')
      setConfig(parsed as ChartConfig)
      setError('')
    } catch (e) {
      setError(String(e instanceof Error ? e.message : e))
    }
  }, [code])

  // 渲染图表
  useEffect(() => {
    if (!chartRef.current || !config) return
    const chart = echarts.init(chartRef.current)
    try {
      chart.setOption(buildOption(config))
    } catch (e) {
      setError(String(e instanceof Error ? e.message : e))
    }
    const onResize = () => chart.resize()
    window.addEventListener('resize', onResize)
    return () => {
      window.removeEventListener('resize', onResize)
      chart.dispose()
    }
  }, [config])

  // 代码视图时高亮
  useEffect(() => {
    if (view === 'code' && codeRef.current) {
      try { hljs.highlightElement(codeRef.current) } catch { /* ignore */ }
    }
  }, [view])

  if (error) {
    return (
      <div className="chart-block chart-error-block">
        <div className="chart-toolbar">
          <span className="chart-label">Chart</span>
          <span className="chart-error-label">解析失败</span>
        </div>
        <pre className="chart-error">
          <code>{code}</code>
          <div className="chart-error-msg">{error}</div>
        </pre>
      </div>
    )
  }

  return (
    <div className="chart-block">
      <div className="chart-toolbar">
        <span className="chart-label">Chart</span>
        <div className="chart-view-toggle">
          <button
            className={`chart-view-btn${view === 'preview' ? ' active' : ''}`}
            onClick={() => setView('preview')}
            title="查看图表"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M3 3v18h18"/><path d="m7 16 4-8 4 4 4-8"/></svg>
            <span>图表</span>
          </button>
          <button
            className={`chart-view-btn${view === 'code' ? ' active' : ''}`}
            onClick={() => setView('code')}
            title="查看数据"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>
            <span>数据</span>
          </button>
        </div>
      </div>
      {view === 'preview' ? (
        <div ref={chartRef} className="chart-canvas" />
      ) : (
        <div className="chart-code-view">
          <pre>
            <code ref={codeRef} className="language-json">{code}</code>
          </pre>
        </div>
      )}
    </div>
  )
}

// ── 代码块组件（高亮 + 复制按钮 + 执行按钮） ──────────────────────────

const API_BASE = import.meta.env.VITE_API_URL || `http://${window.location.hostname}:8000`

// 可执行语言映射（highlight.js 语言名 -> 后端语言名）
const RUNNABLE_LANGS: Record<string, string> = {
  python: 'python', py: 'python',
  javascript: 'javascript', js: 'javascript',
  typescript: 'typescript', ts: 'typescript',
  go: 'go',
  rust: 'rust', rs: 'rust',
  java: 'java',
  c: 'c', cpp: 'cpp', 'c++': 'cpp',
  bash: 'bash', sh: 'bash', shell: 'bash',
  ruby: 'ruby', rb: 'ruby',
  php: 'php',
  swift: 'swift',
  kotlin: 'kotlin', kt: 'kotlin',
}

// 缓存可用运行时
let _cachedRuntimes: string[] | null = null
async function fetchRuntimes(): Promise<string[]> {
  if (_cachedRuntimes) return _cachedRuntimes
  try {
    const resp = await fetch(`${API_BASE}/api/runtimes`)
    const json = await resp.json()
    _cachedRuntimes = (json.runtimes || []).map((r: { language: string }) => r.language)
    return _cachedRuntimes!
  } catch {
    return []
  }
}

interface RunResult {
  success: boolean
  stdout: string
  stderr: string
  exit_code: number
  error: string
}

function CodeBlock({
  language,
  code,
}: {
  language: string
  code: string
}) {
  const [copied, setCopied] = useState(false)
  const [running, setRunning] = useState(false)
  const [result, setResult] = useState<RunResult | null>(null)
  const [canRun, setCanRun] = useState(false)
  const codeRef = useRef<HTMLElement>(null)

  // 检测是否可执行
  useEffect(() => {
    const backendLang = RUNNABLE_LANGS[language?.toLowerCase() ?? '']
    if (!backendLang) { setCanRun(false); return }
    fetchRuntimes().then((runtimes) => {
      setCanRun(runtimes.includes(backendLang))
    })
  }, [language])

  // 高亮
  useEffect(() => {
    if (codeRef.current && language && hljs.getLanguage(language)) {
      try {
        hljs.highlightElement(codeRef.current)
      } catch {
        // 高亮失败时保留原始文本
      }
    }
  }, [code, language])

  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(code)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      const ta = document.createElement('textarea')
      ta.value = code
      ta.style.position = 'fixed'
      ta.style.opacity = '0'
      document.body.appendChild(ta)
      ta.select()
      document.execCommand('copy')
      document.body.removeChild(ta)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }, [code])

  const handleRun = useCallback(async () => {
    const backendLang = RUNNABLE_LANGS[language?.toLowerCase() ?? '']
    if (!backendLang) return
    setRunning(true)
    setResult(null)
    try {
      const resp = await fetch(`${API_BASE}/api/run-code`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ language: backendLang, code }),
      })
      const json = await resp.json() as RunResult
      setResult(json)
    } catch (e) {
      setResult({ success: false, stdout: '', stderr: '', exit_code: -1, error: String(e) })
    } finally {
      setRunning(false)
    }
  }, [language, code])

  const langClass = language ? `language-${language}` : ''

  return (
    <div className="code-block-wrapper">
      <div className="code-block-header">
        {language && <span className="code-block-lang">{language}</span>}
        <div className="code-block-actions">
          {canRun && (
            <button
              className={`code-block-run${running ? ' running' : ''}`}
              onClick={handleRun}
              disabled={running}
              title="执行代码"
            >
              {running ? (
                <>
                  <svg className="spin" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg>
                  <span>执行中</span>
                </>
              ) : (
                <>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polygon points="6 3 20 12 6 21 6 3"/></svg>
                  <span>运行</span>
                </>
              )}
            </button>
          )}
          <button
            className="code-block-copy"
            onClick={handleCopy}
            title={copied ? '已复制' : '复制代码'}
          >
            {copied ? (
              <>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
                <span>已复制</span>
              </>
            ) : (
              <>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect width="14" height="14" x="8" y="8" rx="2" ry="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/></svg>
                <span>复制</span>
              </>
            )}
          </button>
        </div>
      </div>
      <pre>
        <code ref={codeRef} className={langClass}>
          {code}
        </code>
      </pre>
      {result && (
        <div className={`code-run-result${result.success ? '' : ' error'}`}>
          <div className="code-run-result-header">
            <span className={`code-run-status${result.success ? ' success' : ' fail'}`}>
              {result.success ? '✓ 执行成功' : `✗ 退出码: ${result.exit_code}`}
            </span>
            <button className="code-run-result-close" onClick={() => setResult(null)}>×</button>
          </div>
          {result.error && <div className="code-run-error">{result.error}</div>}
          {result.stdout && <pre className="code-run-stdout">{result.stdout}</pre>}
          {result.stderr && <pre className="code-run-stderr">{result.stderr}</pre>}
        </div>
      )}
    </div>
  )
}

// ── react-markdown 自定义组件 ──────────────────────────────────
function extractText(node: ReactNode): string {
  if (typeof node === 'string') return node
  if (typeof node === 'number') return String(node)
  if (Array.isArray(node)) return node.map(extractText).join('')
  if (node && typeof node === 'object' && 'props' in node) {
    return extractText((node as { props: { children?: ReactNode } }).props.children)
  }
  return ''
}

const markdownComponents: Components = {
  code({ className, children, ...rest }) {
    const text = extractText(children)
    // 判断是否为代码块（pre 包裹）
    const match = /language-(\w+)/.exec(className || '')
    const lang = match ? match[1] : ''

    // 无语言且无换行 → 行内代码
    if (!lang && !text.includes('\n')) {
      return (
        <code className={className} {...rest}>
          {children}
        </code>
      )
    }

    // Mermaid
    if (lang === 'mermaid') {
      return <MermaidBlock code={text} />
    }

    // ECharts 数据图表
    if (lang === 'chart') {
      return <ChartBlock code={text} />
    }

    // PlantUML 图表
    if (lang === 'plantuml' || lang === 'puml') {
      return <PlantUMLBlock code={text} />
    }

    // D2 图表
    if (lang === 'd2') {
      return <D2Block code={text} />
    }

    // HTML 实时预览
    if (lang === 'html') {
      return <HtmlPreviewBlock code={text} />
    }

    // SVG 实时预览
    if (lang === 'svg') {
      return <SvgPreviewBlock code={text} />
    }

    // 普通代码块
    return <CodeBlock language={lang} code={text} />
  },
  blockquote({ children, ...rest }) {
    const text = extractText(children)
    const match = /^\s*\[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\]/i.exec(text.trim())
    if (match) {
      const type = match[1].toLowerCase() as AdmonitionType
      const body = stripAdmonitionHead(children)
      return (
        <div className={`admonition admonition-${type}`}>
          <div className="admonition-header">
            <span className="admonition-icon">{ADMONITION_ICONS[type]}</span>
            <span className="admonition-title">{ADMONITION_LABELS[type]}</span>
          </div>
          <div className="admonition-body">{body}</div>
        </div>
      )
    }
    return <blockquote {...rest}>{children}</blockquote>
  },
}

// ── 主组件 ─────────────────────────────────────────────────────
interface MarkdownContentProps {
  text: string
  streaming?: boolean
}

/**
 * Markdown 渲染组件：
 * - 代码语法高亮（highlight.js）
 * - 代码块右上角复制按钮
 * - Mermaid 图表渲染
 * - GFM 表格 / 任务列表
 * - 流式光标
 */
export const MarkdownContent = memo(function MarkdownContent({ text, streaming }: MarkdownContentProps) {
  return (
    <div className={`markdown-content${streaming ? ' streaming' : ''}`}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkBreaks, remarkMath]}
        rehypePlugins={[rehypeKatex]}
        components={markdownComponents}
      >
        {text}
      </ReactMarkdown>
      {streaming && <span className="stream-cursor" />}
    </div>
  )
})
