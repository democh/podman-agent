"""Web 搜索工具：百度/Bing 搜索 + 智能正文提取。

架构设计：
- 搜索层：StealthyFetcher（反爬要求浏览器渲染），支持百度和 Bing
- 正文提取层：httpx 轻量优先（~1s），失败自动降级 StealthyFetcher（~10s）
- 并发层：ThreadPoolExecutor 并行抓取多页正文
- 安全层：全链路停止信号检查
"""
from __future__ import annotations

import json
import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from html.parser import HTMLParser
from typing import Any, Callable
from urllib.parse import quote, urlparse

import httpx
import chardet
from scrapling import StealthyFetcher

from .base import Tool
from .registry import ToolRegistry

logger = logging.getLogger(__name__)


# ── 停止信号（由 Agent 注入）──────────────────────────────────────

_stop_check: Callable[[], bool] | None = None


def set_stop_check(fn: Callable[[], bool]) -> None:
    """注册停止检查回调，供 Agent 在初始化时调用。"""
    global _stop_check
    _stop_check = fn


def _check_stopped() -> None:
    """若已请求停止则抛出异常，中断当前操作。"""
    if _stop_check and _stop_check():
        raise _StoppedError("已手动停止")


class _StoppedError(Exception):
    """停止信号专用异常，区别于普通异常便于上层精确捕获。"""
    pass


# ── httpx 连接池（模块级复用）─────────────────────────────────────

_HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
}

_http_client: httpx.Client | None = None


def _get_http_client() -> httpx.Client:
    """懒初始化并复用 httpx 连接池。"""
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.Client(
            headers=_HTTP_HEADERS,
            timeout=httpx.Timeout(connect=8.0, read=12.0, write=5.0, pool=5.0),
            follow_redirects=True,
            max_redirects=5,
            http2=False,
        )
    return _http_client


def _build_referer(url: str) -> str:
    """根据目标 URL 构建合理的 Referer，避免被反爬拦截。

    策略：
    - 百度域名 → referer 为百度首页
    - 其他域名 → referer 为该站点首页（伪装从首页跳转）
    """
    try:
        parsed = urlparse(url)
        host = parsed.hostname or ""
        if "baidu.com" in host:
            return "https://www.baidu.com/"
        return f"{parsed.scheme}://{host}/"
    except Exception:
        return "https://www.baidu.com/"


# ── StealthyFetcher 配置 ──────────────────────────────────────────

_STEALTHY_KWARGS: dict[str, Any] = {
    "headless": True,
    "locale": "zh-CN",
    "timezone_id": "Asia/Shanghai",
    "real_chrome": True,
    "hide_canvas": True,
    "block_ads": True,
    "timeout": 25_000,
    "google_search": False,
    "extra_headers": {"Referer": "https://www.baidu.com/"},
}


# ── 广告过滤 ──────────────────────────────────────────────────────

_AD_CLASS_KEYWORDS = (
    "ec_ad", "ec_wise_ad", "ec-pc", "tuiguang", "brand",
    "c-result-ad", "ad-icon", "c-span-last",
)
_AD_LABEL_TEXTS = ("广告", "推广", "品牌广告", "商业推广")


def _get_text(element) -> str:
    """获取元素全文本，合并为单行。"""
    raw = element.get_all_text() or ""
    return re.sub(r"\s+", " ", raw).strip()


def _is_ad(item) -> bool:
    """判断搜索结果是否为广告。"""
    for attr in ("data-tuiguang", "data-ads", "data-ad"):
        if item.attrib.get(attr):
            return True
    cls = item.attrib.get("class", "")
    if any(kw in cls for kw in _AD_CLASS_KEYWORDS):
        return True
    item_text = _get_text(item)
    return any(label in item_text for label in _AD_LABEL_TEXTS)


# ── 百度跳转 URL 解析 ────────────────────────────────────────────

def _extract_real_url_from_item(item) -> str:
    """从百度搜索结果 data-tools 属性中提取真实 URL。

    百度在 div.c-container 的 data-tools 属性中存放 JSON：
    {"title": "...", "url": "https://真实地址/...", ...}
    """
    data_tools = item.attrib.get("data-tools", "")
    if not data_tools:
        return ""
    try:
        info = json.loads(data_tools)
        real = info.get("url", "")
        if real and not real.startswith("https://www.baidu.com/link"):
            return real
    except (json.JSONDecodeError, TypeError, AttributeError):
        pass
    return ""


def _resolve_baidu_redirects(urls: list[str]) -> list[str]:
    """批量将百度跳转链接解析为真实 URL（GET 请求并发跟随 302）。

    非百度跳转链接原样返回。
    """
    if not urls:
        return []

    resolved = list(urls)

    # 找出需要解析的索引
    to_resolve = [
        (i, url) for i, url in enumerate(urls)
        if "baidu.com/link" in url or "baidu.com/s?" in url
    ]
    if not to_resolve:
        return resolved

    client = _get_http_client()

    def _resolve_one(idx: int, url: str) -> tuple[int, str]:
        _check_stopped()
        # 百度跳转链接对 HEAD 请求不可靠，必须用 GET 跟随 302
        resp = client.get(
            url,
            follow_redirects=True,
            headers={"Referer": "https://www.baidu.com/"},
            timeout=10.0,
        )
        final = str(resp.url)
        # 若仍是百度跳转链接，尝试从 Location 或 HTML meta 中提取真实 URL
        if "baidu.com/link" in final:
            loc = resp.headers.get("location", "")
            if loc and "baidu.com/link" not in loc:
                final = loc
            else:
                # 从响应体中尝试提取 <meta http-equiv="refresh">
                m = re.search(r'url=([^"]+)', resp.text[:500])
                if m and "baidu.com/link" not in m.group(1):
                    final = m.group(1)
        return idx, final

    workers = min(4, len(to_resolve))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(_resolve_one, i, u): i for i, u in to_resolve}
        for future in as_completed(futures):
            if _stop_check and _stop_check():
                for f in futures:
                    f.cancel()
                break
            try:
                idx, final_url = future.result(timeout=15)
                resolved[idx] = final_url
                logger.info(f"URL 解析: {urls[idx][:60]}... → {final_url[:60]}...")
            except _StoppedError:
                break
            except Exception:
                logger.debug(f"URL 解析失败: {urls[futures[future]][:60]}...")

    return resolved


# ── 百度搜索 ─────────────────────────────────────────────────────

# 时间词模式：年份、相对时间词（LLM 常带入，搜索结果自带时效无需拼接）
# 注意：中文与数字之间无 \b 边界（均为 \w），必须用 (?<!\d)/(?!\d) 替代
_TIME_PATTERNS = [
    re.compile(r'(?<!\d)20\d{2}(?!\d)'),              # 2000-2099 年份
    re.compile(r'(?<!\d)(?:19|21|22)\d{2}(?!\d)'),  # 其他年份范围
    re.compile(r'(?:今年|去年|前年|明年|后年)'),
    re.compile(r'(?:最近|最新|当前|目前|今日|本周|本月)'),
]


def _sanitize_query(query: str) -> str:
    """清洗搜索关键词，剥离年份和相对时间词。

    搜索引擎结果自带时效性，拼接年份反而会限制结果范围、降低召回率。
    """
    cleaned = query
    for pat in _TIME_PATTERNS:
        cleaned = pat.sub('', cleaned)
    # 合并多余空格
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    if cleaned != query:
        logger.info(f"Query 净化: '{query}' → '{cleaned}'")
    return cleaned or query  # 若清洗后为空，返回原始 query


def _build_baidu_search_url(query: str) -> str:
    """构建百度搜索 URL。"""
    return f"https://www.baidu.com/s?wd={quote(query)}"


def _build_bing_search_url(query: str) -> str:
    """构建 Bing 搜索 URL。"""
    return f"https://www.bing.com/search?q={quote(query)}"


def _baidu_page_action(page):
    """等待百度搜索结果加载并检查验证。"""
    _check_stopped()
    try:
        page.wait_for_selector("div.c-container, div.result", timeout=12000)
    except Exception:
        logger.warning("百度搜索结果容器未找到")
        return
    _check_stopped()
    time.sleep(0.3)
    title = page.title() or ""
    if "安全验证" in title or "验证" in title:
        raise Exception("触发百度安全验证")


def _bing_page_action(page):
    """等待 Bing 搜索结果加载并检查验证。"""
    _check_stopped()
    try:
        page.wait_for_selector("li.b_algo", timeout=12000)
    except Exception:
        logger.warning("Bing 搜索结果容器未找到")
        return
    _check_stopped()
    time.sleep(0.3)
    title = page.title() or ""
    if "验证" in title or "captcha" in title.lower():
        raise Exception("触发 Bing 安全验证")


def _search_baidu(query: str, count: int) -> list[dict]:
    """执行百度搜索，返回结果列表。"""
    _check_stopped()
    search_url = _build_baidu_search_url(query)

    resp = StealthyFetcher.fetch(
        search_url,
        page_action=_baidu_page_action,
        network_idle=True,
        **_STEALTHY_KWARGS,
    )

    # 解析搜索结果
    items = resp.css("div.c-container") or resp.css("div.result")
    if not items:
        items = resp.find_all(
            "div", attrs={"class": lambda c: c and ("c-container" in c or "result" in c)}
        )

    results: list[dict] = []
    for item in items:
        if len(results) >= count:
            break
        if _is_ad(item):
            continue

        links = item.find_all("h3")
        if not links:
            continue
        a_tags = links[0].find_all("a")
        if not a_tags:
            continue

        a_tag = a_tags[0]
        title = _get_text(a_tag)
        link = a_tag.attrib.get("href", "")
        if not title or len(title) < 4:
            continue

        # 优先从 data-tools 获取真实 URL，避免百度跳转链接
        real_url = _extract_real_url_from_item(item)
        if not real_url:
            real_url = link  # 保留跳转 URL，后续批量解析

        # 提取摘要
        snippet = _extract_snippet(item, title)
        results.append({"title": title, "url": real_url, "snippet": snippet})

    return results


def _extract_snippet(item, title: str) -> str:
    """从百度搜索结果条目中提取摘要文本。"""
    for sel in (".c-abstract", ".c-row span", ".c-span-last p", "p"):
        snippet_els = item.css(sel) if hasattr(item, "css") else []
        for sel_el in snippet_els:
            text = _get_text(sel_el)
            if text and text != title and len(text) > 8:
                return text
    # 回退：find_all
    for p in item.find_all("p"):
        text = _get_text(p)
        if text and text != title and len(text) > 8:
            return text
    return ""


def _search_bing(query: str, count: int) -> list[dict]:
    """执行 Bing 搜索，返回结果列表。"""
    _check_stopped()
    search_url = _build_bing_search_url(query)

    resp = StealthyFetcher.fetch(
        search_url,
        page_action=_bing_page_action,
        network_idle=True,
        **_STEALTHY_KWARGS,
    )

    # 解析 Bing 搜索结果
    items = resp.css("li.b_algo")
    if not items:
        items = resp.find_all("li", attrs={"class": lambda c: c and "b_algo" in c})

    results: list[dict] = []
    for item in items:
        if len(results) >= count:
            break

        # 提取标题和链接
        h2 = item.css("h2") or item.find_all("h2")
        if not h2:
            continue
        a_tag = h2[0].find_all("a") if hasattr(h2[0], "find_all") else []
        if not a_tag:
            continue

        a = a_tag[0]
        title = _get_text(a)
        link = a.attrib.get("href", "")
        if not title or len(title) < 4 or not link:
            continue

        # 提取摘要
        snippet = ""
        p_els = item.css("p") or item.find_all("p")
        for p in p_els:
            text = _get_text(p)
            if text and len(text) > 20:
                snippet = text
                break

        results.append({"title": title, "url": link, "snippet": snippet})

    return results


# ── 正文提取：httpx 优先 + 浏览器降级 ────────────────────────────

# 需要浏览器渲染的域名模式（SPA / 重度 JS）
_JS_RENDER_DOMAINS = (
    "zhihu.com", "bilibili.com", "weibo.com", "douyin.com",
    "xiaohongshu.com", "toutiao.com",
)

# 重度 JS 站点：需要更长超时（大量图表/实时数据/反爬）
_HEAVY_SITES = (
    "investing.com", "tradingview.com", "bloomberg.com", "reuters.com",
    "wsj.com", "ft.com",
)

# 搜索引擎中间页/跳转页域名（不应作为正文提取目标）
_SEARCH_ENGINE_DOMAINS = (
    "soso.com", "sogou.com", "so.com", "baidu.com/link",
    "google.com/url", "bing.com/ck",
)

# 默认浏览器超时 / 重度站点超时
_BROWSER_TIMEOUT = 20_000
_BROWSER_TIMEOUT_HEAVY = 45_000

# 噪声元素的 class/id 关键词
_NOISE_KEYWORDS = frozenset((
    "comment", "footer", "header", "sidebar", "nav", "menu",
    "ad-", "ads", "share", "recommend", "related", "copyright",
    "breadcrumb", "pagination", "social",
))


class _SimpleHTMLExtractor(HTMLParser):
    """轻量 HTML 正文提取器，基于标签语义权重 + 文本密度。"""

    _CONTENT_TAGS = frozenset(("p", "h1", "h2", "h3", "h4", "h5", "h6", "li", "blockquote", "td"))
    _SKIP_TAGS = frozenset(("script", "style", "noscript", "iframe", "svg", "nav", "footer", "header"))

    def __init__(self):
        super().__init__()
        self.paragraphs: list[str] = []
        self._current_tag = ""
        self._skip_depth = 0
        self._buffer = ""

    def handle_starttag(self, tag, attrs):
        if tag in self._SKIP_TAGS:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        # 检查噪声 class/id
        attr_dict = dict(attrs)
        cls_id = (attr_dict.get("class", "") + " " + attr_dict.get("id", "")).lower()
        if any(kw in cls_id for kw in _NOISE_KEYWORDS):
            self._skip_depth += 1
            return
        if tag in self._CONTENT_TAGS:
            self._current_tag = tag
            self._buffer = ""

    def handle_endtag(self, tag):
        if tag in self._SKIP_TAGS or self._skip_depth:
            if tag in self._SKIP_TAGS:
                self._skip_depth = max(0, self._skip_depth - 1)
            return
        if tag == self._current_tag and self._buffer:
            text = re.sub(r"\s+", " ", self._buffer).strip()
            if len(text) > 15:
                self.paragraphs.append(text)
            self._current_tag = ""
            self._buffer = ""

    def handle_data(self, data):
        if self._skip_depth:
            return
        if self._current_tag:
            self._buffer += data


def _detect_encoding(raw: bytes, content_type: str) -> str:
    """多策略编码检测，优先级：meta charset > HTTP header charset > chardet > utf-8。"""
    # 1. 从 HTML meta 标签检测（取前 4096 bytes 即可）
    head = raw[:4096]
    # <meta charset="UTF-8">
    m = re.search(rb'<meta[^>]+charset=["\']?([^"\';\s>]+)', head, re.IGNORECASE)
    if m:
        return m.group(1).decode('ascii', errors='ignore').strip()
    # <meta http-equiv="Content-Type" content="text/html; charset=xxx">
    m = re.search(rb'<meta[^>]+content=["\'][^"\']*(charset=)([^"\';\s]+)', head, re.IGNORECASE)
    if m:
        return m.group(2).decode('ascii', errors='ignore').strip()

    # 2. 从 HTTP Content-Type header 提取 charset
    ct_match = re.search(r'charset=([^\s;]+)', content_type, re.IGNORECASE)
    if ct_match:
        return ct_match.group(1).strip()

    # 3. chardet 自动检测
    detection = chardet.detect(raw[:8192])
    if detection and detection.get('encoding') and detection.get('confidence', 0) > 0.5:
        enc = detection['encoding']
        # chardet 可能返回 'GB2312' 但实际用 'GBK' 更兼容
        if enc.upper() in ('GB2312', 'GB18030'):
            return 'GBK'
        return enc

    # 4. 智能 fallback：尝试 UTF-8 解码，若失败则用 GBK（中文网站常见）
    try:
        raw[:4096].decode('utf-8')
        return 'utf-8'
    except UnicodeDecodeError:
        return 'GBK'


def _decode_html(raw: bytes, content_type: str) -> str:
    """智能解码 HTML 原始字节为字符串。"""
    encoding = _detect_encoding(raw, content_type)
    # 规范化编码名称
    encoding = encoding.lower().replace('-', '').replace('_', '')
    # 常见别名映射
    _ENCODING_ALIASES = {
        'gbk': 'gbk', 'gb2312': 'gbk', 'gb18030': 'gb18030',
        'utf8': 'utf-8', 'unicode': 'utf-8',
        'big5': 'big5', 'euckr': 'euc-kr', 'eucjp': 'euc-jp',
        'shiftjis': 'shift_jis', 'latin1': 'latin-1',
        'iso88591': 'latin-1', 'ascii': 'ascii',
    }
    normalized = _ENCODING_ALIASES.get(encoding, encoding)
    # 恢复标准名称中的连字符
    if normalized == 'utf8':
        normalized = 'utf-8'

    try:
        return raw.decode(normalized, errors='replace')
    except (UnicodeDecodeError, LookupError):
        # 编码名称无效时 fallback
        try:
            return raw.decode('utf-8', errors='replace')
        except Exception:
            return raw.decode('gbk', errors='replace')


def _clean_text(text: str) -> str:
    """清理解码后的文本，移除乱码/控制字符。"""
    # 移除常见乱码占位符（U+FFFD replacement character）
    text = text.replace('\ufffd', '')
    # 移除控制字符（保留换行/制表）
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
    # 移除连续乱码模式（如连续的?或连续的特殊符号）
    text = re.sub(r'[?？]{3,}', '', text)
    # 压缩多余空白
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def _extract_with_httpx(url: str) -> dict:
    """使用 httpx 快速抓取并提取正文（无 JS 渲染）。"""
    _check_stopped()
    client = _get_http_client()
    resp = client.get(url, headers={"Referer": _build_referer(url)})
    # 使用 httpx 跟随重定向后的最终 URL
    final_url = str(resp.url)

    # 403/429/5xx 等明确错误直接上报，交给上层判断是否降级
    if resp.status_code in (403, 429, 503):
        logger.debug(f"httpx 被拦截 ({final_url}): HTTP {resp.status_code}")
        return {"url": final_url, "content": "", "error": f"HTTP {resp.status_code} 被拦截"}
    resp.raise_for_status()

    content_type = resp.headers.get("content-type", "")
    if "text/html" not in content_type and "application/xhtml" not in content_type:
        return {"url": final_url, "content": "", "error": "非 HTML 页面"}

    # 使用原始字节 + 智能编码检测（避免 httpx 默认 ISO-8859-1 导致中文乱码）
    raw_bytes = resp.content
    if not raw_bytes or len(raw_bytes) < 100:
        return {"url": final_url, "content": "", "error": "页面内容为空"}

    html = _decode_html(raw_bytes, content_type)
    if not html or len(html) < 100:
        return {"url": final_url, "content": "", "error": "页面内容为空"}

    _check_stopped()

    # 尝试提取 <article> 区域（最高优先级）
    article_match = re.search(r"<article[^>]*>(.*?)</article>", html, re.DOTALL | re.IGNORECASE)
    target_html = article_match.group(1) if article_match else html

    extractor = _SimpleHTMLExtractor()
    try:
        extractor.feed(target_html)
    except Exception:
        pass

    content = "\n\n".join(extractor.paragraphs)

    # 若正文太短，尝试从 meta 补充
    if len(content) < 50:
        meta_desc = _extract_meta_description(html)
        if meta_desc:
            content = meta_desc + ("\n\n" + content if content else "")

    # 清理乱码/控制字符
    content = _clean_text(content)

    if content and len(content) > 30:
        if len(content) > 5000:
            content = content[:5000] + "\n...[内容已截断]"
        return {"url": final_url, "content": content, "error": None}

    return {"url": final_url, "content": "", "error": "未提取到有效正文"}


def _extract_meta_description(html: str) -> str:
    """从 meta 标签提取描述信息。"""
    for pattern in (
        r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)',
        r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']+)',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']description["\']',
    ):
        m = re.search(pattern, html, re.IGNORECASE)
        if m and len(m.group(1)) > 20:
            return m.group(1).strip()
    return ""


def _extract_with_browser(url: str, timeout: int = _BROWSER_TIMEOUT) -> dict:
    """使用 StealthyFetcher 抓取页面（处理 JS 渲染场景）。"""
    _check_stopped()
    try:
        resp = StealthyFetcher.fetch(
            url,
            headless=True,
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
            real_chrome=True,
            hide_canvas=True,
            block_ads=True,
            disable_resources=True,
            network_idle=False,  # 不等待网络空闲，加速
            timeout=timeout,
            google_search=False,
            extra_headers={"Referer": _build_referer(url)},
        )

        paragraphs: list[str] = []
        seen: set[str] = set()

        for tag_name in ("p", "h1", "h2", "h3", "h4", "h5", "h6", "blockquote", "li"):
            for el in resp.find_all(tag_name):
                text = _get_text(el)
                if len(text) > 15 and text not in seen:
                    cls_id = (el.attrib.get("class", "") + " " + el.attrib.get("id", "")).lower()
                    if any(kw in cls_id for kw in _NOISE_KEYWORDS):
                        continue
                    seen.add(text)
                    paragraphs.append(text)

        content = "\n\n".join(paragraphs)
        # 清理可能的乱码/控制字符
        content = _clean_text(content)

        if content and len(content) > 30:
            if len(content) > 5000:
                content = content[:5000] + "\n...[内容已截断]"
            return {"url": url, "content": content, "error": None}

        return {"url": url, "content": "", "error": "未找到正文内容"}
    except _StoppedError:
        raise
    except Exception as e:
        return {"url": url, "content": "", "error": str(e)[:200]}


def _needs_browser(url: str) -> bool:
    """判断 URL 是否需要浏览器渲染。"""
    return any(domain in url for domain in _JS_RENDER_DOMAINS)


def _is_heavy_site(url: str) -> bool:
    """判断是否为重度 JS 站点（需要更长超时）。"""
    return any(domain in url for domain in _HEAVY_SITES)


def _extract_page_content(url: str) -> dict:
    """智能正文提取：httpx 优先，失败自动降级浏览器。"""
    _check_stopped()

    # 过滤搜索引擎中间页（不值得提取正文）
    if any(domain in url for domain in _SEARCH_ENGINE_DOMAINS):
        logger.debug(f"跳过搜索引擎中间页: {url[:80]}")
        return {"url": url, "content": "", "error": "搜索引擎中间页，跳过"}

    # 根据站点类型选择浏览器超时
    browser_timeout = _BROWSER_TIMEOUT_HEAVY if _is_heavy_site(url) else _BROWSER_TIMEOUT

    # 已知需要 JS 渲染的域名直接走浏览器
    if _needs_browser(url):
        return _extract_with_browser(url, timeout=browser_timeout)

    # httpx 优先（快 10-20x）
    try:
        result = _extract_with_httpx(url)
        if result.get("content"):
            logger.info(f"httpx 提取成功: {url[:60]}")
            return result
        # 正文为空但非错误（如非 HTML 页面），直接返回不降级
        if result.get("error") and "非 HTML" in result["error"]:
            return result
        logger.debug(f"httpx 未提取到正文 ({url}): {result.get('error')}")
    except _StoppedError:
        raise
    except Exception as e:
        logger.debug(f"httpx 提取失败 ({url}): {e}")

    # 降级浏览器
    logger.info(f"降级浏览器 (timeout={browser_timeout // 1000}s): {url[:60]}")
    return _extract_with_browser(url, timeout=browser_timeout)


def _fetch_pages(urls: list[str], max_workers: int = 4) -> list[dict]:
    """并发抓取多个页面正文，支持停止信号。"""
    if not urls:
        return []

    results: list[dict] = [{"url": u, "content": "", "error": "未执行"} for u in urls]
    n_workers = min(max_workers, len(urls))

    def _worker(idx: int, url: str) -> tuple[int, dict]:
        _check_stopped()
        return idx, _extract_page_content(url)

    with ThreadPoolExecutor(max_workers=n_workers) as executor:
        futures = {executor.submit(_worker, i, url): i for i, url in enumerate(urls)}

        for future in as_completed(futures):
            # 停止时取消剩余任务
            if _stop_check and _stop_check():
                for f in futures:
                    f.cancel()
                break
            try:
                idx, result = future.result(timeout=35)
                results[idx] = result
            except _StoppedError:
                break
            except Exception as e:
                idx = futures[future]
                results[idx] = {"url": urls[idx], "content": "", "error": str(e)[:200]}

    return results


# ── 输出格式化 ────────────────────────────────────────────────────

def _format_markdown(
    query: str, results: list[dict], page_contents: list[dict] | None = None
) -> str:
    """将搜索结果格式化为 Markdown。"""
    lines = [f"# 搜索结果: {query}\n"]

    if not results:
        lines.append("未找到相关结果。")
        return "\n".join(lines)

    lines.append(f"共找到 {len(results)} 条结果\n")

    content_map = {}
    if page_contents:
        content_map = {pc["url"]: pc for pc in page_contents}

    for i, r in enumerate(results, 1):
        lines.append(f"## {i}. {r['title']}")
        lines.append(f"**链接:** {r['url']}")
        if r.get("snippet"):
            lines.append(f"\n{r['snippet']}")

        pc = content_map.get(r["url"])
        if pc and pc.get("content"):
            lines.append("\n**正文摘要:**\n")
            lines.append(pc["content"][:2000])
            if len(pc["content"]) > 2000:
                lines.append("...")
        elif pc and pc.get("error"):
            lines.append(f"\n*抓取失败: {pc['error']}*")

        lines.append("")

    return "\n".join(lines)


# ── Tool 类定义 ───────────────────────────────────────────────────

class WebSearchTool(Tool):
    """联网搜索工具：支持百度和 Bing 搜索 + 可选正文提取。"""

    name = "web_search"
    description = (
        "在互联网上搜索信息。返回搜索结果列表（标题、链接、摘要），"
        "可选同时提取搜索结果页面的正文内容。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "搜索关键词，仅填写搜索主题，禁止在关键词中拼接年份、日期等时间信息",
            },
            "engine": {
                "type": "string",
                "enum": ["baidu", "bing"],
                "description": "搜索引擎，默认 baidu",
            },
            "count": {
                "type": "integer",
                "description": "返回结果数量（默认 10）",
            },
            "fetch": {
                "type": "boolean",
                "description": "同时抓取搜索结果页面正文，默认 false",
            },
            "fetch_count": {
                "type": "integer",
                "description": "抓取前 N 条结果的正文（默认等于 count）",
            },
        },
        "required": ["query"],
    }

    def run(
        self,
        query: str,
        engine: str = "baidu",
        count: int = 10,
        fetch: bool = False,
        fetch_count: int = 0,
    ) -> str:
        # 自动剥离年份/时间词，搜索引擎结果自带时效
        query = _sanitize_query(query)
        try:
            if engine == "bing":
                results = _search_bing(query, count)
            else:
                results = _search_baidu(query, count)
        except _StoppedError:
            return "搜索已停止"
        except Exception as e:
            return f"搜索失败: {e}"

        if not results:
            return f"# 搜索结果: {query}\n\n未找到相关结果。"

        # 可选：批量解析跳转 URL → 真实 URL，再并发抓取正文
        page_contents = None
        if fetch and results:
            n = fetch_count or count
            raw_urls = [r["url"] for r in results[:n]]
            # 百度需要解析跳转链接，Bing 直接返回真实 URL
            if engine == "baidu":
                real_urls = _resolve_baidu_redirects(raw_urls)
            else:
                real_urls = raw_urls
            # 用真实 URL 替换结果中的跳转 URL，方便后续格式化和引用
            for i, r in enumerate(results[:n]):
                r["url"] = real_urls[i]
            page_contents = _fetch_pages(real_urls)

        return _format_markdown(query, results, page_contents)


class FetchPageTool(Tool):
    """网页正文提取工具：给定 URL 列表，提取每个页面的正文内容。"""

    name = "fetch_page"
    description = (
        "提取指定 URL 页面的正文内容。可传入多个 URL 批量提取。"
        "返回每个页面的正文文本。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "urls": {
                "type": "array",
                "items": {"type": "string"},
                "description": "要提取正文的 URL 列表",
            },
        },
        "required": ["urls"],
    }

    def run(self, urls: list[str]) -> str:
        if not urls:
            return "Error: urls 不能为空"

        results = _fetch_pages(urls)
        lines = []
        for r in results:
            lines.append(f"## {r['url']}")
            if r.get("content"):
                lines.append(r["content"][:3000])
                if len(r["content"]) > 3000:
                    lines.append("...")
            elif r.get("error"):
                lines.append(f"*提取失败: {r['error']}*")
            lines.append("")
        return "\n".join(lines)


# ── 注册入口 ──────────────────────────────────────────────────────

def register_web_tools(registry: ToolRegistry) -> None:
    """注册 web_search 和 fetch_page 工具。"""
    registry.register(WebSearchTool())
    registry.register(FetchPageTool())
