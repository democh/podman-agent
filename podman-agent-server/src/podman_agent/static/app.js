const $ = (id) => document.getElementById(id)
const messagesEl = $('messages')
const inputEl = $('input')
const sendBtn = $('send-btn')
const sendBtnText = $('send-btn-text')
const resetBtn = $('reset-btn')
const statusDot = $('status-dot')
const statusText = $('status-text')
const modelBadge = $('model-badge')
const toolsBadge = $('tools-badge')
const skillsBadge = $('skills-badge')
let emptyState = $('empty-state')
const sidebar = $('sidebar')
const sidebarContent = $('sidebar-content')
const scrollBtn = $('scroll-btn')

let ws = null,
  busy = false,
  currentTab = 'skills'
let currentMsg = null,
  currentBubble = null,
  currentReasoning = null,
  currentContentEl = null
let totalTokens = 0,
  skillsData = [],
  hasScrolledUp = false
let pendingSearchBlock = null // tracks tool-block awaiting search result
let currentPlanBody = null     // tracks plan-block body for dynamic step updates
let currentPlanStepEls = []    // step icon elements for live progress

/* ═══ Lucide Icons ═══ */
let _iconTimer = null
function _lucideIcon(name, w, h) {
  w = w || 16; h = h || w
  const icon = lucide && lucide.icons && lucide.icons[name]
  if (!icon) return ''
  return icon[1].replace(/width="[^"]*"/, `width="${w}"`).replace(/height="[^"]*"/, `height="${h}"`)
}
function refreshIcons() {
  clearTimeout(_iconTimer)
  _iconTimer = setTimeout(() => lucide && lucide.createIcons(), 30)
}

/* ═══ Markdown ═══ */
function renderMarkdown(text) {
  if (typeof marked !== 'undefined') {
    return marked.parse(text, { breaks: true, gfm: true })
  }
  // Fallback: basic regex parser (marked 未加载时)
  let h = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
  h = h.replace(
    /```(\w*)\n?([\s\S]*?)```/g,
    (m, l, c) => `<pre><code>${c.trim()}</code></pre>`,
  )
  h = h.replace(/`([^`]+)`/g, '<code>$1</code>')
  h = h.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
  h = h.replace(/^### (.+)$/gm, '<h3>$1</h3>')
  h = h.replace(/^## (.+)$/gm, '<h2>$1</h2>')
  h = h.replace(/^# (.+)$/gm, '<h1>$1</h1>')
  h = h.replace(/^[-*] (.+)$/gm, '<li>$1</li>')
  h = h.replace(/(<li>.*<\/li>\n?)+/g, (m) => `<ul>${m}</ul>`)
  h = h.replace(/^\d+\. (.+)$/gm, '<li>$1</li>')
  h = h.replace(/\n\n/g, '</p><p>')
  h = h.replace(/\n/g, '<br>')
  h = `<p>${h}</p>`
  h = h.replace(/<p>\s*<\/p>/g, '')
  h = h.replace(/<p>\s*<br>/g, '<p>')
  h = h.replace(/<br>\s*<\/p>/g, '</p>')
  return h
}
function escapeHtml(t) {
  const d = document.createElement('div')
  d.textContent = t
  return d.innerHTML
}

/* ═══ File Card SVG Icons (module-level, avoid re-creation) ═══ */
function _officeSvg(letter, color) {
  return '<svg viewBox="0 0 32 32" xmlns="http://www.w3.org/2000/svg"><rect width="32" height="32" rx="4" fill="' + color + '"/><text x="16" y="22" text-anchor="middle" fill="#fff" font-size="16" font-weight="700" font-family="Arial,sans-serif">' + letter + '</text></svg>'
}
function _docSvg(label, color) {
  return '<svg viewBox="0 0 32 32" xmlns="http://www.w3.org/2000/svg"><rect width="32" height="32" rx="4" fill="' + color + '"/><text x="16" y="21" text-anchor="middle" fill="#fff" font-size="9" font-weight="700" font-family="Arial,sans-serif" letter-spacing="0.5">' + label + '</text></svg>'
}
const _imgSvg = '<svg viewBox="0 0 32 32" xmlns="http://www.w3.org/2000/svg"><rect width="32" height="32" rx="4" fill="#9333EA"/><path d="M8 20l5-5 4 4 7-7" stroke="#fff" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"/><circle cx="12" cy="12" r="2" fill="#fff"/></svg>'
const _zipSvg = '<svg viewBox="0 0 32 32" xmlns="http://www.w3.org/2000/svg"><rect width="32" height="32" rx="4" fill="#F59E0B"/><rect x="14" y="6" width="4" height="3" fill="#fff" rx="1"/><rect x="14" y="11" width="4" height="3" fill="#fff" rx="1"/><rect x="14" y="16" width="4" height="3" fill="#fff" rx="1"/><path d="M11 22h10l-2 4h-6z" fill="#fff"/></svg>'
function _codeSvg(color) {
  return '<svg viewBox="0 0 32 32" xmlns="http://www.w3.org/2000/svg"><rect width="32" height="32" rx="4" fill="' + color + '"/><path d="M12 11l-5 5 5 5M20 11l5 5-5 5" stroke="#fff" stroke-width="2.2" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>'
}
function _globeSvg(color) {
  return '<svg viewBox="0 0 32 32" xmlns="http://www.w3.org/2000/svg"><rect width="32" height="32" rx="4" fill="' + color + '"/><circle cx="16" cy="16" r="8" stroke="#fff" stroke-width="2" fill="none"/><path d="M8 16h16M16 8c2.5 2.5 2.5 13 0 16M16 8c-2.5 2.5-2.5 13 0 16" stroke="#fff" stroke-width="1.5" fill="none"/></svg>'
}
const _txtSvg = '<svg viewBox="0 0 32 32" xmlns="http://www.w3.org/2000/svg"><rect width="32" height="32" rx="4" fill="#6B7280"/><path d="M9 12h14M9 16h14M9 20h9" stroke="#fff" stroke-width="2" stroke-linecap="round"/></svg>'
function _mdSvg(color) {
  return '<svg viewBox="0 0 32 32" xmlns="http://www.w3.org/2000/svg"><rect width="32" height="32" rx="4" fill="' + color + '"/><text x="16" y="21" text-anchor="middle" fill="#fff" font-size="10" font-weight="700" font-family="Arial,sans-serif">MD</text></svg>'
}
const FILE_TYPES = {
  pptx: { svg: _officeSvg('P', '#D04423'), color: '#D04423', label: 'PPT' },
  ppt:  { svg: _officeSvg('P', '#D04423'), color: '#D04423', label: 'PPT' },
  pdf:  { svg: _docSvg('PDF', '#E5302E'),  color: '#E5302E', label: 'PDF' },
  docx: { svg: _officeSvg('W', '#2B579A'), color: '#2B579A', label: 'DOC' },
  doc:  { svg: _officeSvg('W', '#2B579A'), color: '#2B579A', label: 'DOC' },
  xlsx: { svg: _officeSvg('X', '#217346'), color: '#217346', label: 'XLS' },
  xls:  { svg: _officeSvg('X', '#217346'), color: '#217346', label: 'XLS' },
  zip: { svg: _zipSvg, color: '#F59E0B', label: 'ZIP' },
  gz:  { svg: _zipSvg, color: '#F59E0B', label: 'GZ' },
  tar: { svg: _zipSvg, color: '#F59E0B', label: 'TAR' },
  '7z': { svg: _zipSvg, color: '#F59E0B', label: '7Z' },
  rar: { svg: _zipSvg, color: '#F59E0B', label: 'RAR' },
  py:   { svg: _codeSvg('#3776AB'),  color: '#3776AB', label: 'PY' },
  js:   { svg: _codeSvg('#D4A017'),  color: '#D4A017', label: 'JS' },
  ts:   { svg: _codeSvg('#3178C6'),  color: '#3178C6', label: 'TS' },
  html: { svg: _globeSvg('#E34F26'), color: '#E34F26', label: 'HTML' },
  css:  { svg: _codeSvg('#1572B6'),  color: '#1572B6', label: 'CSS' },
  json: { svg: _codeSvg('#5B6370'),  color: '#5B6370', label: 'JSON' },
  md:   { svg: _mdSvg('#083FA1'),    color: '#083FA1', label: 'MD' },
  png:  { svg: _imgSvg, color: '#9333EA', label: 'PNG' },
  jpg:  { svg: _imgSvg, color: '#9333EA', label: 'JPG' },
  jpeg: { svg: _imgSvg, color: '#9333EA', label: 'JPG' },
  gif:  { svg: _imgSvg, color: '#9333EA', label: 'GIF' },
  svg:  { svg: _imgSvg, color: '#FFB13B', label: 'SVG' },
  txt:  { svg: _txtSvg, color: '#6B7280', label: 'TXT' },
}

/* ═══ Toast ═══ */
function toast(msg, type = '') {
  const t = document.createElement('div')
  t.className = 'toast ' + type
  t.textContent = msg
  $('toast-container').appendChild(t)
  setTimeout(() => {
    t.style.opacity = '0'
    t.style.transform = 'translateX(20px)'
    t.style.transition = '0.2s'
    setTimeout(() => t.remove(), 200)
  }, 3000)
}

/* ═══ Status ═══ */
function setStatus(s, t) {
  statusDot.className = 'status-dot ' + s
  statusText.textContent = t
}
function setBusy(b) {
  busy = b
  if (b) {
    sendBtn.disabled = false
    sendBtn.classList.add('btn-stop-mode')
    sendBtn.querySelector('svg').outerHTML = _lucideIcon('square', 14, 14)
    sendBtnText.textContent = '停止'
    sendBtn.onclick = stopAgent
  } else {
    sendBtn.disabled = !ws || ws.readyState !== WebSocket.OPEN
    sendBtn.classList.remove('btn-stop-mode')
    sendBtn.querySelector('svg').outerHTML = _lucideIcon('send-horizontal', 14, 14)
    sendBtnText.textContent = '发送'
    sendBtn.onclick = sendMessage
  }
  resetBtn.disabled = b
  inputEl.disabled = b
  setStatus(b ? 'busy' : 'connected', b ? '思考中' : '已连接')
  const loadingEl = $('loading-indicator')
  if (loadingEl) {
    loadingEl.classList.toggle('visible', b)
  }
  if (b) scrollToBottom()
}

/* ═══ Sidebar ═══ */
function toggleSidebar() {
  const wasCollapsed = sidebar.classList.contains('collapsed')
  sidebar.classList.toggle('collapsed')
  if (wasCollapsed) renderSidebar()
}
function switchTab(tab) {
  currentTab = tab
  $('sidebar-title').textContent =
    tab === 'skills' ? '技能管理' : '记忆库'
  document
    .querySelectorAll('.sidebar-tab')
    .forEach((t) => t.classList.toggle('active', t.dataset.tab === tab))
  renderSidebar()
}
function renderSidebar() {
  if (currentTab === 'skills') renderSkills()
  else renderMemory()
}
function renderSkills() {
  if (!skillsData.length) {
    sidebarContent.innerHTML =
      '<div style="text-align:center;color:hsl(var(--muted-foreground));font-size:13px;padding:20px 8px;">暂无技能<br><span style="font-size:11px">在 skills/ 目录创建 .md 文件</span></div>'
    return
  }
  sidebarContent.innerHTML = skillsData
    .map(
      (s) => `
          <div class="skill-card">
            <div class="skill-card-top">
              <div style="flex:1;min-width:0">
                <div class="skill-name">${escapeHtml(s.name)}</div>
                <div class="skill-desc">${escapeHtml(s.description || '')}</div>
              </div>
              <label class="toggle">
                <input type="checkbox" ${s.enabled ? 'checked' : ''} onchange="toggleSkill('${s.name}', this.checked)">
                <span class="toggle-slider"></span>
              </label>
            </div>
            ${s.triggers && s.triggers.length ? `<div class="skill-triggers">${s.triggers.map((t) => `<span class="skill-trigger">${escapeHtml(t)}</span>`).join('')}</div>` : ''}
          </div>
        `,
    )
    .join('')
}
function renderMemory(isRetry, retryCount) {
  if (!isRetry) retryCount = 0
  sidebarContent.innerHTML =
    '<div style="text-align:center;padding:16px 8px;color:hsl(var(--muted-foreground));font-size:13px;">记忆列表加载中...</div>'
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: 'memory_list' }))
  } else {
    // WebSocket 未连接，指数退避重试（1s → 2s → 4s → 8s，最多 5 次）
    if (retryCount < 5) {
      const delay = Math.min(1000 * Math.pow(2, retryCount), 8000)
      setTimeout(() => renderMemory(true, retryCount + 1), delay)
    } else {
      sidebarContent.innerHTML =
        '<div style="text-align:center;padding:16px 8px;color:hsl(var(--muted-foreground));font-size:13px;">连接失败，请刷新页面重试</div>'
    }
  }
}
function toggleSkill(name, enabled) {
  if (!ws || ws.readyState !== WebSocket.OPEN) return
  ws.send(
    JSON.stringify({
      type: enabled ? 'skill_enable' : 'skill_disable',
      name,
    }),
  )
}

/* ═══ Messages ═══ */
function hideEmpty() {
  if (emptyState) emptyState.style.display = 'none'
}
function addUserMsg(text) {
  hideEmpty()
  const d = document.createElement('div')
  d.className = 'msg user'
  d.innerHTML = `<div class="msg-label">你</div><div class="msg-bubble">${renderMarkdown(text)}</div>`
  messagesEl.appendChild(d)
  scrollToBottom()
}
function startAgentMsg() {
  hideEmpty()
  const d = document.createElement('div')
  d.className = 'msg agent'
  d.innerHTML = `<div class="msg-label">Agent</div><div class="msg-bubble"></div>`
  messagesEl.appendChild(d)
  currentMsg = d
  currentBubble = d.querySelector('.msg-bubble')
  currentReasoning = null
  currentContentEl = null
}
function ensureReasoning() {
  if (!currentReasoning) {
    const b = document.createElement('div')
    b.className = 'reasoning-block'
    b.innerHTML = '<div class="reasoning-label">推理过程</div>'
    currentBubble.insertBefore(b, currentBubble.firstChild)
    currentReasoning = b
  }
  return currentReasoning
}
function addToolBlock(name, args) {
  const b = document.createElement('div')
  b.className = 'tool-block'
  const a = typeof args === 'object' ? JSON.stringify(args) : String(args)
  const as = a.length > 80 ? a.substring(0, 80) + '…' : a
  b.innerHTML = `<div class="tool-header"><span class="tool-icon">${_lucideIcon('settings', 14, 14)}</span><span class="tool-name">${escapeHtml(name)}</span><span class="tool-args">${escapeHtml(as)}</span><span class="tool-chevron">${_lucideIcon('chevron-right', 12, 12)}</span></div><div class="tool-body"></div>`
  b.querySelector('.tool-header').onclick = () =>
    b.classList.toggle('expanded')
  // Detect web search tool call (support both old run_shell + search.py and new web_search tool)
  const argsStr =
    typeof args === 'object' ? args.command || '' : String(args)
  if ((name === 'run_shell' && argsStr.includes('search.py')) || name === 'web_search') {
    b.dataset.searchPending = '1'
    pendingSearchBlock = b
  }
  currentBubble.appendChild(b)
}
/* ═══ Search Results Card ═══ */
function parseSearchOutput(text) {
  // Parse: # 搜索结果: query
  //        *搜索引擎: engine*
  //        共找到 N 条结果
  //        ## 1. title
  //        **链接:** url
  //        snippet
  const queryMatch = text.match(/^# 搜索结果:\s*(.+)$/m)
  const engineMatch = text.match(/\*搜索引擎:\s*(.+?)\*/m)
  const query = queryMatch ? queryMatch[1].trim() : ''
  const engine = engineMatch ? engineMatch[1].trim() : ''
  const results = []
  // Split by ## N.
  const blocks = text.split(/^## \d+\.\s+/m).slice(1)
  for (const block of blocks) {
    const lines = block.split('\n')
    const title = lines[0] ? lines[0].trim() : ''
    let url = ''
    let snippet = ''
    const linkMatch = lines[1]
      ? lines[1].match(/\*\*链接:\*\*\s*(.+)/)
      : null
    if (linkMatch) {
      url = linkMatch[1].trim()
      snippet = lines
        .slice(2)
        .join('\n')
        .replace(/^\n+|\n+$/g, '')
        .trim()
    } else {
      snippet = lines
        .slice(1)
        .join('\n')
        .replace(/^\n+|\n+$/g, '')
        .trim()
    }
    if (title) results.push({ title, url, snippet })
  }
  return { query, engine, results }
}

function renderSearchCard(parsed) {
  const card = document.createElement('div')
  card.className = 'search-card'
  // Header
  const searchIcon = _lucideIcon('search', 14, 14).replace('<svg', '<svg class="search-card-icon"').replace('stroke="currentColor"', 'stroke="hsl(210,100%,45%)"')
  const engineLabel = parsed.engine
    ? `<span class="search-card-engine">${escapeHtml(parsed.engine)}</span>`
    : ''
  const countLabel = parsed.results.length
    ? `<span class="search-card-count">${parsed.results.length} 条结果</span>`
    : ''
  const toggleSvg = _lucideIcon('chevron-down', 14, 14).replace('<svg', '<svg class="search-card-toggle-icon"')
  let headerHtml = `<div class="search-card-header" style="cursor:pointer;user-select:none;">${searchIcon}<span class="search-card-query">${escapeHtml(parsed.query || '搜索结果')}</span>${engineLabel}${countLabel}<span class="search-card-toggle">${toggleSvg}</span></div>`
  card.innerHTML = headerHtml
  // Results container
  const resultsContainer = document.createElement('div')
  resultsContainer.className = 'search-card-results'
  // Results
  for (const r of parsed.results) {
    const item = document.createElement('div')
    item.className = 'search-result-item'
    // Extract domain from URL
    let domain = ''
    try {
      const u = new URL(r.url)
      domain = u.hostname
    } catch {
      domain = r.url.slice(0, 40)
    }
    const linkSvg = _lucideIcon('link-2', 10, 10)
    const titleHtml = r.url
      ? `<a href="${escapeHtml(r.url)}" target="_blank" rel="noopener">${escapeHtml(r.title)}</a>`
      : escapeHtml(r.title)
    let itemHtml = `<div class="search-result-title">${titleHtml}</div>`
    itemHtml += `<div class="search-result-url">${linkSvg}${escapeHtml(domain)}</div>`
    if (r.snippet) {
      itemHtml += `<div class="search-result-snippet">${escapeHtml(r.snippet)}</div>`
    }
    item.innerHTML = itemHtml
    // Expand/collapse for long snippets
    if (r.snippet && r.snippet.length > 150) {
      const toggle = document.createElement('div')
      toggle.className = 'search-result-toggle'
      toggle.textContent = '展开全文 ▾'
      toggle.onclick = () => {
        item.classList.toggle('expanded')
        toggle.textContent = item.classList.contains('expanded')
          ? '收起 ▴'
          : '展开全文 ▾'
      }
      item.appendChild(toggle)
    }
    resultsContainer.appendChild(item)
  }
  if (!parsed.results.length) {
    const empty = document.createElement('div')
    empty.style.cssText =
      'padding:16px;text-align:center;color:hsl(var(--muted-foreground));font-size:13px;'
    empty.textContent = '未找到相关结果'
    resultsContainer.appendChild(empty)
  }
  card.appendChild(resultsContainer)
  // Header click to toggle collapse
  const header = card.querySelector('.search-card-header')
  const toggleIcon = card.querySelector('.search-card-toggle-icon')
  header.onclick = () => {
    const collapsed = resultsContainer.classList.toggle('collapsed')
    toggleIcon.style.transform = collapsed ? 'rotate(-90deg)' : ''
  }
  return card
}

function handleSearchResult(text) {
  const parsed = parseSearchOutput(text)
  if (parsed.results.length > 0 || parsed.query) {
    const card = renderSearchCard(parsed)
    currentBubble.appendChild(card)
    if (!hasScrolledUp) scrollToBottom()
    return true
  }
  return false
}
function addFileCard(filename, path, size, description) {
  if (!currentMsg) startAgentMsg()
  const typing = currentBubble.querySelector('.typing')
  if (typing) typing.remove()
  const sizeStr =
    size > 0
      ? size >= 1024 * 1024
        ? (size / 1024 / 1024).toFixed(1) + ' MB'
        : size >= 1024
          ? (size / 1024).toFixed(1) + ' KB'
          : size + ' B'
      : ''
  const ext = (filename.split('.').pop() || '').toLowerCase()
  const ft = FILE_TYPES[ext] || {
    svg: _txtSvg,
    color: '#6B7280',
    label: ext.toUpperCase().slice(0, 4),
  }
  const dlIcon = _lucideIcon('download', 14, 14)
  const card = document.createElement('div')
  card.className = 'file-card'
  card.innerHTML =
    '<div class="file-card-icon">' +
    ft.svg +
    '</div>' +
    '<div class="file-card-info">' +
    '<div class="file-card-name">' +
    escapeHtml(filename) +
    '<span class="file-card-badge" style="background:' +
    ft.color +
    '">' +
    ft.label +
    '</span>' +
    '</div>' +
    '<div class="file-card-meta">' +
    (sizeStr ? sizeStr : '') +
    (description
      ? (sizeStr ? ' · ' : '') + escapeHtml(description)
      : '') +
    '</div></div>' +
    '<a class="file-card-download" href="/api/download?path=' +
    encodeURIComponent(path) +
    '" download="' +
    escapeHtml(filename) +
    '">' +
    dlIcon +
    '下载</a>'
  currentBubble.appendChild(card)
  if (!hasScrolledUp) scrollToBottom()
}
function addMeta(text, cls) {
  const d = document.createElement('div')
  d.className = 'meta-line ' + (cls || '')
  d.textContent = text
  currentBubble.appendChild(d)
}
function addPlanBlock(steps) {
  const b = document.createElement('div')
  b.className = 'plan-block expanded'
  const chevron = _lucideIcon('chevron-right', 12, 12)
  const header = document.createElement('div')
  header.className = 'plan-block-header'
  header.innerHTML = `<span class="plan-icon">${_lucideIcon('list-checks', 16, 16)}</span><span>执行计划 (${steps.length} 步)</span><span class="plan-chevron">${chevron}</span>`
  header.onclick = () => b.classList.toggle('expanded')
  const body = document.createElement('div')
  body.className = 'plan-block-body'
  currentPlanStepEls = []
  steps.forEach((s, i) => {
    const step = document.createElement('div')
    step.className = 'plan-step'
    const icon = i === 0 ? '🔄' : '⬜'
    const iconEl = document.createElement('span')
    iconEl.className = 'plan-step-icon'
    iconEl.textContent = icon
    const textEl = document.createElement('span')
    textEl.className = 'plan-step-text'
    textEl.textContent = s
    step.appendChild(iconEl)
    step.appendChild(textEl)
    body.appendChild(step)
    currentPlanStepEls.push(iconEl)
  })
  currentPlanBody = body
  b.appendChild(header)
  b.appendChild(body)
  currentBubble.appendChild(b)
  if (!hasScrolledUp) scrollToBottom()
}
function updatePlanProgress(result) {
  if (!currentPlanStepEls.length) return
  // 找到当前 🔄 步骤
  let idx = currentPlanStepEls.findIndex(el => el.textContent === '🔄')
  if (idx < 0) return
  if (result === 'DONE') {
    currentPlanStepEls[idx].textContent = '✅'
    if (idx + 1 < currentPlanStepEls.length) {
      currentPlanStepEls[idx + 1].textContent = '🔄'
    }
  } else if (result === 'REPLAN') {
    currentPlanStepEls[idx].textContent = '🔀'
  }
}
function addReflectionMeta(result, detail) {
  const d = document.createElement('div')
  d.className = 'reflection-meta'
  const cls = result.toLowerCase()
  const label = result === 'DONE' ? '完成' : result === 'RETRY' ? '重试' : result === 'REPLAN' ? '重规划' : result
  const preview = detail ? (detail.length > 80 ? detail.substring(0, 80) + '…' : detail) : ''
  d.innerHTML = `<span class="result-badge ${cls}">${label}</span><span>${escapeHtml(preview)}</span>`
  currentBubble.appendChild(d)
}
function addLatsMeta(pick, total, chosen) {
  const d = document.createElement('div')
  d.className = 'lats-meta'
  d.innerHTML = `<span class="lats-badge">LATS</span><span>候选 ${pick}/${total} → ${escapeHtml(chosen || '')}</span>`
  currentBubble.appendChild(d)
}
function scrollToBottom() {
  messagesEl.scrollTop = messagesEl.scrollHeight
  hasScrolledUp = false
  scrollBtn.classList.remove('visible')
}
messagesEl.addEventListener('scroll', () => {
  const atBottom =
    messagesEl.scrollHeight -
      messagesEl.scrollTop -
      messagesEl.clientHeight <
    50
  hasScrolledUp = !atBottom
  scrollBtn.classList.toggle(
    'visible',
    hasScrolledUp &&
      messagesEl.scrollHeight > messagesEl.clientHeight + 100,
  )
})

/* ═══ WebSocket Events ═══ */
function handleEvent(ev) {
  try {
  switch (ev.type) {
    case 'info':
      modelBadge.textContent = ev.model || '—'
      toolsBadge.textContent = (ev.tools || []).length + ' tools'
      if (ev.skills) {
        skillsData = ev.skills
        renderSkills()
        const active = ev.skills.filter((s) => s.enabled).length
        skillsBadge.style.display = 'inline-flex'
        skillsBadge.innerHTML = `<span class="dot" style="background:hsl(var(--success))"></span>${active}/${ev.skills.length} skills`
      }
      if (ev.total_tokens !== undefined) {
        totalTokens = ev.total_tokens
      }
      setBusy(false)
      // 页面加载后自动请求最近对话历史
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'conversation_recent', days: 2 }))
      }
      break

    case 'reasoning_delta':
      if (!currentMsg) startAgentMsg()
      ensureReasoning()
      currentReasoning.appendChild(document.createTextNode(ev.content))
      if (!hasScrolledUp) scrollToBottom()
      break

    case 'content_delta':
      if (!currentMsg) startAgentMsg()
      // 移除 typing loading 动画
      const typing = currentBubble.querySelector('.typing')
      if (typing) typing.remove()
      if (!currentContentEl) {
        currentContentEl = document.createElement('div')
        currentContentEl.className = 'agent-content'
        currentBubble.appendChild(currentContentEl)
      }
      currentContentEl.appendChild(document.createTextNode(ev.content))
      if (!hasScrolledUp) scrollToBottom()
      break

    case 'stream_end':
      break

    case 'reasoning':
      if (!currentMsg) startAgentMsg()
      ensureReasoning()
      const p =
        ev.content.length > 300
          ? ev.content.substring(0, 300) + '…'
          : ev.content
      currentReasoning.appendChild(document.createTextNode(p))
      break

    case 'usage':
      totalTokens = ev.total_tokens
      if (currentMsg)
        addMeta(
          `tokens: prompt=${ev.prompt_tokens} completion=${ev.completion_tokens} total=${ev.total_tokens}`,
        )
      break

    case 'warning':
      if (currentMsg) addMeta('⚠ ' + ev.content, 'warn')
      break

    case 'tool_call':
      if (!currentMsg) startAgentMsg()
      // 移除 typing loading 动画
      const typingTc = currentBubble.querySelector('.typing')
      if (typingTc) typingTc.remove()
      addToolBlock(ev.name, ev.args)
      currentContentEl = null
      refreshIcons()
      if (!hasScrolledUp) scrollToBottom()
      break

    case 'tool_result':
      const blocks = currentBubble
        ? currentBubble.querySelectorAll('.tool-block')
        : []
      if (blocks.length > 0) {
        const lb = blocks[blocks.length - 1]
        const body = lb.querySelector('.tool-body')
        const err = ev.result && ev.result.startsWith('Error:')
        // Check if this is a pending search tool block
        if (lb.dataset.searchPending && !err && ev.result) {
          const rendered = handleSearchResult(ev.result)
          if (rendered) {
            delete lb.dataset.searchPending
            pendingSearchBlock = null
            // Still populate body for expand view
            body.innerHTML = `<span class="tool-result-ok">${escapeHtml(ev.result)}</span>`
            break
          }
        }
        body.innerHTML = `<span class="${err ? 'tool-result-err' : 'tool-result-ok'}">${escapeHtml(ev.result)}</span>`
        if (err)
          lb.querySelector('.tool-icon').style.color =
            'hsl(var(--destructive))'
      }
      if (!hasScrolledUp) scrollToBottom()
      break

    case 'separator':
      // 工具调用块已提供视觉分隔，不需要额外分隔线
      break
    case 'file_ready':
      addFileCard(ev.filename, ev.path, ev.size, ev.description)
      refreshIcons()
      break
    case 'context_compressed':
      addMeta(`[上下文已压缩，保留 ${ev.kept} 条]`, 'warn')
      break

    case 'plan_created':
      if (!currentMsg) startAgentMsg()
      addPlanBlock(ev.steps || [])
      refreshIcons()
      break

    case 'reflection':
      if (currentMsg) {
        addReflectionMeta(ev.result, ev.detail)
        updatePlanProgress(ev.result)
      }
      refreshIcons()
      break

    case 'lats_pick':
      if (currentMsg) addLatsMeta(ev.pick, ev.total, ev.chosen)
      break

    case 'done':
      if (currentBubble) {
        // 移除残留的 typing loading 动画
        currentBubble
          .querySelectorAll('.typing')
          .forEach((t) => t.remove())
        currentBubble.querySelectorAll('.agent-content').forEach((ce) => {
          ce.innerHTML = renderMarkdown(ce.textContent)
        })
      }
      currentMsg = null
      currentBubble = null
      currentReasoning = null
      currentContentEl = null
      currentPlanBody = null
      currentPlanStepEls = []
      setBusy(false)
      refreshIcons()
      break

    case 'error':
      if (!currentBubble) startAgentMsg()
      addMeta('✗ ' + ev.content, 'error')
      setBusy(false)
      break

    case 'reset_ok':
      messagesEl.innerHTML = ''
      const es = document.createElement('div')
      es.className = 'empty-state'
      es.id = 'empty-state'
      es.innerHTML =
        `<div class="empty-icon">${_lucideIcon('bot', 48, 48)}</div><div class="empty-title">Podman Agent</div><div class="empty-desc">对话已重置</div>`
      messagesEl.appendChild(es)
      emptyState = es
      refreshIcons()
      currentMsg = null
      currentBubble = null
      currentReasoning = null
      currentContentEl = null
      break

    case 'skill_list':
      skillsData = ev.skills || []
      renderSkills()
      break

    case 'skill_updated':
      toast(
        ev.result || '操作完成',
        ev.result && ev.result.includes('Error') ? 'error' : 'success',
      )
      // Refresh skill list
      if (ws && ws.readyState === WebSocket.OPEN)
        ws.send(JSON.stringify({ type: 'skill_list' }))
      break

    case 'memory_list_result':
      if (ev.result && ev.result.includes('(记忆库为空)')) {
        sidebarContent.innerHTML =
          '<div style="text-align:center;color:hsl(var(--muted-foreground));font-size:13px;padding:20px 8px;">记忆库为空<br><span style="font-size:11px">对话中让 Agent 记住信息</span></div>'
      } else {
        const lines = (ev.result || '')
          .split('\n')
          .filter((l) => l.trim())
        sidebarContent.innerHTML = lines
          .map((line) => {
            const m = line.match(
              /^\s*-\s*\[(\w+)\]\s*(.+?)\s*\(keywords:\s*(.*?),\s*updated:\s*(.*?)\)\s*$/,
            )
            if (m) {
              return `<div class="memory-card"><div class="mem-title">${escapeHtml(m[2])}</div><div class="mem-meta">[${m[1]}] ${m[3]} · ${m[4]}</div></div>`
            }
            return `<div class="memory-card"><div class="mem-title">${escapeHtml(line)}</div></div>`
          })
          .join('')
      }
      break

    case 'conversation_history':
      renderConversationHistory(ev.result || '')
      break
  }
  } catch (err) {
    console.error('[handleEvent] unhandled error:', ev.type, err)
  }
}

/* ═══ Conversation History ═══ */
function renderConversationHistory(text) {
  if (!text || text.includes('(无对话历史)')) return
  // 统一换行符：CRLF → LF
  text = text.replace(/\r\n/g, '\n')
  // 按日期分隔符拆分（---\ntitle: 或 date: 开头的是 day 分隔符）
  const dayBlocks = text
    .split(/^---\n(?=title:|date:)/m)
    .filter((s) => s.trim())
  for (const block of dayBlocks) {
    // 跳过 frontmatter（date: ...）
    const lines = block.split('\n')
    let dateStr = ''
    let bodyStart = 0
    for (let i = 0; i < lines.length; i++) {
      if (lines[i].startsWith('date:')) {
        dateStr = lines[i].replace('date:', '').trim()
      }
      if (lines[i].startsWith('---') && i > 0) {
        bodyStart = i + 1
        break
      }
      if (lines[i].startsWith('## ')) {
        bodyStart = i
        break
      }
    }
    const body = lines.slice(bodyStart).join('\n')
    // 按 ## HH:MM:SS 拆分每轮对话
    const turns = body.split(/^## (\d{2}:\d{2}:\d{2})/m)
    for (let i = 1; i < turns.length; i += 2) {
      const time = turns[i]
      const content = turns[i + 1] || ''
      // 提取用户输入
      const userMatch = content.match(
        /\*\*用户:\*\*\n\n([\s\S]*?)(?=\*\*工具调用|\*\*助手|$)/,
      )
      if (userMatch) {
        addUserMsg(userMatch[1].trim())
      }
      // 提取所有助手回复（turn 分隔符 --- 后跟时间戳标题或文件结尾）
      const agentRe = new RegExp(
        '\\*\\*助手:\\*\\*\\n\\n([\\s\\S]*?)(?=\\n\\n---\\n\\n## \\d{2}:\\d{2}:\\d{2}|\\n\\n---\\n\\s*$)',
        'g',
      )
      const agentMatches = [...content.matchAll(agentRe)]
      for (const agentMatch of agentMatches) {
        let agentText = agentMatch[1].trim()
        // 提取文件标记
        const filePattern = new RegExp(
          '<!--file path="([^"]*)" desc="([^"]*)"-->',
          'g',
        )
        const files = []
        let fMatch
        while ((fMatch = filePattern.exec(agentText)) !== null) {
          files.push({ path: fMatch[1], desc: fMatch[2] })
        }
        // 清除文件标记
        agentText = agentText.replace(filePattern, '').trim()
        // 提取搜索结果标记
        const searchPattern = /<!--search\s+([A-Za-z0-9+/=]+)-->/g
        const searches = []
        let sMatch
        while ((sMatch = searchPattern.exec(agentText)) !== null) {
          try {
            const decoded = decodeURIComponent(escape(atob(sMatch[1])))
            searches.push(decoded)
          } catch (e) {
            // base64 解码失败，跳过
          }
        }
        // 清除搜索标记
        agentText = agentText.replace(searchPattern, '').trim()
        const d = document.createElement('div')
        d.className = 'msg agent'
        d.innerHTML = `<div class="msg-label">Agent</div><div class="msg-bubble">${renderMarkdown(agentText)}</div>`
        messagesEl.appendChild(d)
        const savedMsg = currentMsg
        const savedBubble = currentBubble
        currentMsg = d
        currentBubble = d.querySelector('.msg-bubble')
        // 还原文件卡片
        if (files.length) {
          for (const f of files) {
            addFileCard(f.path.split(/[\\/]/).pop(), f.path, 0, f.desc)
          }
        }
        // 还原搜索卡片
        if (searches.length) {
          for (const s of searches) {
            handleSearchResult(s)
          }
        }
        currentMsg = savedMsg
        currentBubble = savedBubble
      }
    }
  }
  // 如果有历史消息，隐藏空状态
  if (messagesEl.querySelector('.msg')) {
    hideEmpty()
  }
  refreshIcons()
  scrollToBottom()
}
/* ═══ WebSocket ═══ */
function connect() {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws'
  ws = new WebSocket(`${proto}://${location.host}/ws/chat`)
  ws.onopen = () => {
    setStatus('connected', '已连接')
    setBusy(busy)
    inputEl.focus()
  }
  ws.onmessage = (e) => {
    try {
      handleEvent(JSON.parse(e.data))
    } catch (err) {
      console.error(err)
    }
  }
  ws.onerror = () => setStatus('error', '连接错误')
  ws.onclose = () => {
    setStatus('', '已断开')
    sendBtn.disabled = true
    setTimeout(() => {
      if (!ws || ws.readyState === WebSocket.CLOSED) {
        setStatus('', '重连中…')
        connect()
      }
    }, 2000)
  }
}

/* ═══ Send ═══ */
function sendMessage() {
  const text = inputEl.value.trim()
  if (!text || !ws || ws.readyState !== WebSocket.OPEN || busy) return
  addUserMsg(text)
  startAgentMsg()
  const t = document.createElement('div')
  t.className = 'typing'
  t.innerHTML = '<span></span><span></span><span></span>'
  currentBubble.appendChild(t)
  scrollToBottom()
  ws.send(JSON.stringify({ type: 'message', content: text }))
  inputEl.value = ''
  autoResize()
  setBusy(true)
}
function stopAgent() {
  if (!ws || ws.readyState !== WebSocket.OPEN) return
  ws.send(JSON.stringify({ type: 'stop' }))
  sendBtn.disabled = true
}
function resetChat() {
  if (!ws || ws.readyState !== WebSocket.OPEN || busy) return
  ws.send(JSON.stringify({ type: 'reset' }))
}

/* ═══ Input ═══ */
function autoResize() {
  inputEl.style.height = 'auto'
  inputEl.style.height = Math.min(inputEl.scrollHeight, 200) + 'px'
}
inputEl.addEventListener('input', autoResize)
inputEl.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    sendMessage()
  }
})
sendBtn.onclick = sendMessage

/* ═══ Init ═══ */
sidebar.classList.add('collapsed') // Start collapsed
connect()
