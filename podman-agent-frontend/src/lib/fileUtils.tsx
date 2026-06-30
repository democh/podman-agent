import type { ReactNode } from 'react'

/* ═══ 文件类型图标与颜色 ═══ */

export interface FileTypeMeta {
  color: string
  label: string
  letter?: string
  category: 'office' | 'code' | 'image' | 'archive' | 'web' | 'text' | 'markdown' | 'unknown'
}

const FILE_TYPE_MAP: Record<string, FileTypeMeta> = {
  pptx: { color: '#D04423', label: 'PPT', letter: 'P', category: 'office' },
  ppt:  { color: '#D04423', label: 'PPT', letter: 'P', category: 'office' },
  pdf:  { color: '#E5302E', label: 'PDF', category: 'office' },
  docx: { color: '#2B579A', label: 'DOC', letter: 'W', category: 'office' },
  doc:  { color: '#2B579A', label: 'DOC', letter: 'W', category: 'office' },
  xlsx: { color: '#217346', label: 'XLS', letter: 'X', category: 'office' },
  xls:  { color: '#217346', label: 'XLS', letter: 'X', category: 'office' },
  zip: { color: '#F59E0B', label: 'ZIP', category: 'archive' },
  gz:  { color: '#F59E0B', label: 'GZ',  category: 'archive' },
  tar: { color: '#F59E0B', label: 'TAR', category: 'archive' },
  '7z': { color: '#F59E0B', label: '7Z', category: 'archive' },
  rar: { color: '#F59E0B', label: 'RAR', category: 'archive' },
  py:   { color: '#3776AB', label: 'PY',   category: 'code' },
  js:   { color: '#D4A017', label: 'JS',   category: 'code' },
  ts:   { color: '#3178C6', label: 'TS',   category: 'code' },
  html: { color: '#E34F26', label: 'HTML', category: 'web' },
  css:  { color: '#1572B6', label: 'CSS',  category: 'code' },
  json: { color: '#5B6370', label: 'JSON', category: 'code' },
  md:   { color: '#083FA1', label: 'MD',   category: 'markdown' },
  png:  { color: '#9333EA', label: 'PNG',  category: 'image' },
  jpg:  { color: '#9333EA', label: 'JPG',  category: 'image' },
  jpeg: { color: '#9333EA', label: 'JPG',  category: 'image' },
  gif:  { color: '#9333EA', label: 'GIF',  category: 'image' },
  svg:  { color: '#FFB13B', label: 'SVG',  category: 'image' },
  txt:  { color: '#6B7280', label: 'TXT',  category: 'text' },
}

export function getFileType(filename: string): FileTypeMeta {
  const ext = (filename.split('.').pop() || '').toLowerCase()
  return FILE_TYPE_MAP[ext] ?? { color: '#6B7280', label: ext.toUpperCase().slice(0, 4), category: 'unknown' }
}

export function formatFileSize(bytes: number): string {
  if (bytes <= 0) return ''
  if (bytes >= 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`
  if (bytes >= 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${bytes} B`
}

/* ═══ 品牌色 SVG 文件图标（与原项目一致）═══ */

/** Office 文档图标：圆角矩形 + 白色大写字母 */
function OfficeSvg({ letter, color }: { letter: string; color: string }): ReactNode {
  return (
    <svg viewBox="0 0 32 32" xmlns="http://www.w3.org/2000/svg">
      <rect width="32" height="32" rx="4" fill={color} />
      <text x="16" y="22" textAnchor="middle" fill="#fff" fontSize="16" fontWeight="700" fontFamily="Arial,sans-serif">{letter}</text>
    </svg>
  )
}

/** 文档标签图标：圆角矩形 + 白色小字标签 */
function DocLabelSvg({ label, color }: { label: string; color: string }): ReactNode {
  return (
    <svg viewBox="0 0 32 32" xmlns="http://www.w3.org/2000/svg">
      <rect width="32" height="32" rx="4" fill={color} />
      <text x="16" y="21" textAnchor="middle" fill="#fff" fontSize="9" fontWeight="700" fontFamily="Arial,sans-serif" letterSpacing="0.5">{label}</text>
    </svg>
  )
}

/** 图片文件图标：圆角矩形 + 山峰折线 + 小圆点 */
function ImageSvg(): ReactNode {
  return (
    <svg viewBox="0 0 32 32" xmlns="http://www.w3.org/2000/svg">
      <rect width="32" height="32" rx="4" fill="#9333EA" />
      <path d="M8 20l5-5 4 4 7-7" stroke="#fff" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx="12" cy="12" r="2" fill="#fff" />
    </svg>
  )
}

/** 压缩包图标：圆角矩形 + 拉链 + 箱子 */
function ArchiveSvg(): ReactNode {
  return (
    <svg viewBox="0 0 32 32" xmlns="http://www.w3.org/2000/svg">
      <rect width="32" height="32" rx="4" fill="#F59E0B" />
      <rect x="14" y="6" width="4" height="3" fill="#fff" rx="1" />
      <rect x="14" y="11" width="4" height="3" fill="#fff" rx="1" />
      <rect x="14" y="16" width="4" height="3" fill="#fff" rx="1" />
      <path d="M11 22h10l-2 4h-6z" fill="#fff" />
    </svg>
  )
}

/** 代码文件图标：圆角矩形 + 尖括号 < > */
function CodeSvg({ color }: { color: string }): ReactNode {
  return (
    <svg viewBox="0 0 32 32" xmlns="http://www.w3.org/2000/svg">
      <rect width="32" height="32" rx="4" fill={color} />
      <path d="M12 11l-5 5 5 5M20 11l5 5-5 5" stroke="#fff" strokeWidth="2.2" fill="none" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

/** Web 文件图标：圆角矩形 + 地球经纬线 */
function GlobeSvg({ color }: { color: string }): ReactNode {
  return (
    <svg viewBox="0 0 32 32" xmlns="http://www.w3.org/2000/svg">
      <rect width="32" height="32" rx="4" fill={color} />
      <circle cx="16" cy="16" r="8" stroke="#fff" strokeWidth="2" fill="none" />
      <path d="M8 16h16M16 8c2.5 2.5 2.5 13 0 16M16 8c-2.5 2.5-2.5 13 0 16" stroke="#fff" strokeWidth="1.5" fill="none" />
    </svg>
  )
}

/** 纯文本图标：圆角矩形 + 横线 */
function TextSvg(): ReactNode {
  return (
    <svg viewBox="0 0 32 32" xmlns="http://www.w3.org/2000/svg">
      <rect width="32" height="32" rx="4" fill="#6B7280" />
      <path d="M9 12h14M9 16h14M9 20h9" stroke="#fff" strokeWidth="2" strokeLinecap="round" />
    </svg>
  )
}

/** Markdown 图标：圆角矩形 + MD 文字 */
function MdSvg({ color }: { color: string }): ReactNode {
  return (
    <svg viewBox="0 0 32 32" xmlns="http://www.w3.org/2000/svg">
      <rect width="32" height="32" rx="4" fill={color} />
      <text x="16" y="21" textAnchor="middle" fill="#fff" fontSize="10" fontWeight="700" fontFamily="Arial,sans-serif">MD</text>
    </svg>
  )
}

/** 通用未知文件图标：圆角矩形 + 问号 */
function UnknownSvg({ color }: { color: string }): ReactNode {
  return (
    <svg viewBox="0 0 32 32" xmlns="http://www.w3.org/2000/svg">
      <rect width="32" height="32" rx="4" fill={color} />
      <text x="16" y="22" textAnchor="middle" fill="#fff" fontSize="14" fontWeight="700" fontFamily="Arial,sans-serif">?</text>
    </svg>
  )
}

/**
 * 根据文件名返回对应的品牌色 SVG 图标 React 节点
 * 与原项目 app.js 中的 FILE_TYPES svg 完全一致
 */
export function getFileIcon(filename: string, size = 40): ReactNode {
  const ft = getFileType(filename)
  let svg: ReactNode
  switch (ft.category) {
    case 'office':
      if (ft.letter) {
        svg = <OfficeSvg letter={ft.letter} color={ft.color} />
      } else {
        svg = <DocLabelSvg label={ft.label} color={ft.color} />
      }
      break
    case 'image':
      svg = <ImageSvg />
      break
    case 'archive':
      svg = <ArchiveSvg />
      break
    case 'code':
      svg = <CodeSvg color={ft.color} />
      break
    case 'web':
      svg = <GlobeSvg color={ft.color} />
      break
    case 'text':
      svg = <TextSvg />
      break
    case 'markdown':
      svg = <MdSvg color={ft.color} />
      break
    default:
      svg = <UnknownSvg color={ft.color} />
      break
  }

  return (
    <div style={{ width: size, height: size, flexShrink: 0 }}>
      {svg}
    </div>
  )
}

/* ═══ 搜索结果解析 ═══ */

export interface SearchResult {
  title: string
  url: string
  snippet: string
}

export interface ParsedSearch {
  query: string
  engine: string
  results: SearchResult[]
}

export function parseSearchOutput(text: string): ParsedSearch {
  const queryMatch = text.match(/^# 搜索结果:\s*(.+)$/m)
  const engineMatch = text.match(/\*搜索引擎:\s*(.+?)\*/m)
  const query = queryMatch?.[1]?.trim() ?? ''
  const engine = engineMatch?.[1]?.trim() ?? ''

  const results: SearchResult[] = []
  const blocks = text.split(/^## \d+\.\s+/m).slice(1)

  for (const block of blocks) {
    const lines = block.split('\n')
    const title = lines[0]?.trim() ?? ''
    let url = ''
    let snippet = ''
    const linkMatch = lines[1]?.match(/\*\*链接:\*\*\s*(.+)/)

    if (linkMatch) {
      url = linkMatch[1].trim()
      snippet = lines.slice(2).join('\n').replace(/^\n+|\n+$/g, '').trim()
    } else {
      snippet = lines.slice(1).join('\n').replace(/^\n+|\n+$/g, '').trim()
    }

    if (title) results.push({ title, url, snippet })
  }

  return { query, engine, results }
}
