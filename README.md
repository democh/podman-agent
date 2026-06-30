# Podman Agent

> 多范式融合的专业级 AI Agent，支持 ReAct / Plan-Execute-Reflect / LATS / ReWOO 等多种范式智能调度，具备意图识别、文档解析、图表可视化、网页搜索等全栈能力。

## ✨ 核心特性

### 🧠 多范式融合架构

系统根据任务复杂度自动选择最优范式组合，无需手动切换：

| 模式 | 触发条件 | 说明 |
|------|----------|------|
| **ReAct** | 简单任务（默认） | 思考-行动-观察循环，快速响应 |
| **Plan-Execute-Reflect** | 复杂任务 | 自动拆解为步骤列表，逐步执行并反思验证 |
| **LATS** | 高可靠需求 | 生成多个候选方案，评估选优后执行 |
| **ReWOO** | 多工具并行 | 检测无依赖的工具调用，自动并行执行 |
| **Self-Verification** | 关键操作后 | 自动验证 write_file/edit_file 是否生效 |
| **Episodic Memory** | 任务开始时 | 查询历史经验，引导当前执行 |

### 🎯 通用意图识别系统

采用**注册表驱动**的两层架构，自动识别用户真实意图并动态加载对应能力指南：

```
用户输入 → 关键词预筛（<1ms）→ 高置信度直接命中 → 加载 Guide
                    ↓ 低置信度
               LLM 批量确认（4s 超时）→ 加载 Guide
```

**当前已注册意图：**

| 意图 | 说明 | 命中时行为 |
|------|------|-----------|
| `chart` | 数据图表/可视化需求 | 加载完整图表指南（charts.md） |
| `search` | 互联网搜索需求 | 注入搜索工具优先使用提示 |
| `document` | 文档解析/处理需求 | 注入文档处理关注提示 |

**性能优化：**
- 多关键词命中（≥2）时视为高置信度，直接跳过 LLM 确认（0ms 延迟）
- LLM 确认设置 4 秒严格超时，超时自动回退
- 意图检测与记忆检索并行执行，减少总延迟

**扩展方式：** 在 `INTENT_REGISTRY` 中追加一条 `IntentDef` 即可，无需修改检测逻辑。

### 🛡️ 安全控制

- **HITL 人机协同**：高风险操作（Shell/文件写入）触发用户确认
- **Shell 黑名单**：禁止 `rm -rf /`、`mkfs`、fork bomb 等危险命令
- **循环检测**：滑动窗口检测重复工具调用，防止死循环
- **Token 预算**：上下文超长时自动裁剪，防止溢出
- **安全护栏**：定期注入约束提醒，防止 Agent 偏离任务

### 📄 文档处理

- **文件上传**：支持 Office（Word/Excel/PPT）、PDF、文本文件
- **自动解析**：上传文档自动转换为 Markdown，直接与大模型交互
- **对话集成**：解析后的内容自动附加到消息上下文
- **限制**：最多 10 个文件，每个 ≤ 10MB

### 🌐 网页搜索

- **双引擎支持**：百度（中文内容）+ Bing（英文/国际内容）
- **智能降级**：httpx 快速抓取优先，失败自动降级浏览器渲染
- **正文提取**：readability-lxml 算法，精准提取正文内容
- **反爬对抗**：自动伪装 Referer、User-Agent，支持百度跳转链接解析

### 🎨 Markdown 扩展渲染

- **数学公式**：KaTeX 渲染 `$...$` 和 `$$...$$`
- **Admonition**：`> [!NOTE]` / `[!WARNING]` 等提示块
- **图表**：Mermaid、PlantUML、D2、ECharts（17 种图表类型）
- **代码预览**：HTML/SVG 实时预览，代码块可执行
- **代码高亮**：highlight.js 支持 15+ 语言

### 💾 记忆系统

- **结构化记忆**：跨会话持久化知识笔记（Markdown 文件存储）
- **对话日志**：自动记录每轮对话，支持按日期检索
- **经验引导**：任务开始自动查询相关历史经验
- **工具**：memory_list / memory_read / memory_write / memory_search / memory_update / memory_delete

### 🔄 自进化系统

- **对话后反思**：总结经验教训，记录成功/失败方案
- **工具模式学习**：记录成功方案，下次类似任务自动推荐
- **Prompt 自适应**：根据执行效果动态调整提示词
- **用户画像**：建模用户偏好，个性化响应
- **定期深度分析**：后台定时执行深度模式分析

### 📊 Prompt 模块化体系

所有 Prompt 以独立 Markdown 文件管理，按需加载，减少 token 消耗：

| 文件 | 用途 | 加载时机 |
|------|------|----------|
| `system.md` | 核心系统提示词 | 始终加载 |
| `memory.md` | 记忆系统使用指南 | 始终加载 |
| `skills.md` | 技能系统指南 | 始终加载 |
| `tools.md` | 工具使用指南 | 始终加载 |
| `guardrails.md` | 安全护栏约束 | 定期注入 |
| `planning.md` | 任务规划模板 | Plan 模式激活时 |
| `reflection.md` | 步骤反思模板 | 每步执行后 |
| `evaluation.md` | 候选评估模板 | LATS 激活时 |
| `charts.md` | 图表使用指南 | 意图识别命中 chart 时 |
| `intent.md` | 意图分类模板 | 意图检测时 |
| `evolution.md` | 自进化分析模板 | 定期深度分析时 |

---

## 📁 项目结构

```
podman-agent/
├── podman-agent-frontend/     # 前端 React 应用
│   ├── src/
│   │   ├── components/
│   │   │   ├── chat/           # 聊天组件
│   │   │   │   ├── ChatArea.tsx
│   │   │   │   ├── InputArea.tsx
│   │   │   │   ├── MessageBubble.tsx
│   │   │   │   ├── MarkdownContent.tsx  # Markdown 渲染 + ECharts + Mermaid
│   │   │   │   ├── FileUpload.tsx       # 文件上传组件
│   │   │   │   └── ...
│   │   │   ├── settings/       # 设置面板（实时配置）
│   │   │   ├── sidebar/        # 侧边栏（对话列表）
│   │   │   └── topbar/         # 顶部栏
│   │   ├── hooks/              # React Hooks
│   │   │   ├── useAgent.ts     # Agent 交互逻辑
│   │   │   ├── useWebSocket.ts # WebSocket 连接管理
│   │   │   └── ...
│   │   └── lib/                # 工具库
│   └── package.json
│
├── podman-agent-server/       # 后端 Python 服务
│   └── src/podman_agent/
│       ├── agent/              # Agent 核心
│       │   ├── agent.py        # 主循环（多范式融合 + 意图识别）
│       │   ├── planner.py      # Plan-Execute-Reflect
│       │   └── lats.py         # LATS 候选搜索
│       ├── tool/               # 工具集
│       │   ├── registry.py     # 工具注册表
│       │   ├── shell.py        # Shell 执行（HITL + 黑名单）
│       │   ├── filesystem.py   # 文件操作（Self-Verification）
│       │   ├── web_search.py   # 网页搜索（百度/Bing + 反爬）
│       │   ├── code_runner.py  # 代码执行（12 种语言）
│       │   └── search.py       # 文件搜索
│       ├── prompts/            # Prompt 模板体系
│       │   ├── md/             # Markdown 模板文件（11 个）
│       │   ├── builder.py      # Prompt 构建器
│       │   └── intent_detector.py  # 通用意图识别器
│       ├── memory/             # 记忆系统（MD 文件存储）
│       ├── skill/              # 技能管理器
│       ├── evolution/          # 自进化系统
│       ├── web/                # FastAPI + WebSocket 服务
│       ├── core/               # LLM 客户端
│       └── config/             # 配置管理（.env 驱动）
│
└── workspace/                  # 工作空间（运行时生成）
    ├── download/               # 上传文件存储
    ├── skills/                 # 技能定义
    └── memories/               # 记忆存储
```

---

## 🚀 快速开始

### 环境要求

- Python 3.10+
- Node.js 18+
- uv（Python 包管理）

### 后端启动

```bash
cd podman-agent-server

# 安装依赖
uv sync

# 配置环境变量
cp .env.example .env
# 编辑 .env，填写 LLM_API_KEY

# 启动服务
uv run podman-agent --web
```

### 前端启动

```bash
cd podman-agent-frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

访问 http://localhost:5173 即可使用。

---

## ⚙️ 配置说明

所有配置通过 `.env` 环境变量管理，也可通过前端 Settings 面板实时修改。

### LLM 连接

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `LLM_API_KEY` | API 密钥（必填） | - |
| `LLM_BASE_URL` | API 地址 | `https://api.deepseek.com/v1` |
| `LLM_MODEL` | 模型名称 | `deepseek-v4-flash` |
| `MAX_ITERATIONS` | 单轮最大迭代步数 | `20` |
| `TEMPERATURE` | 生成温度 | `0.2` |
| `TOP_P` | 核采样概率 | 不设置 |
| `MAX_TOKENS` | 单次生成最大 token 数 | 不设置 |
| `STREAM` | 流式输出 | `true` |
| `ENABLE_THINKING` | 思考模式 | `false` |

### Agent 行为

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `CONTEXT_TOKEN_THRESHOLD` | 上下文 token 阈值 | `850000` |
| `KEEP_RECENT` | 裁剪时保留消息数 | `20` |
| `LOOP_WINDOW` | 循环检测窗口 | `4` |
| `GUARDRAILS_INTERVAL` | 安全护栏间隔（轮） | `5` |

### 范式控制

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `ENABLE_PLANNING` | 启用任务规划 | `true` |
| `ENABLE_REFLECTION` | 启用步骤反思 | `true` |
| `MAX_RETRIES_PER_STEP` | 每步最大重试次数 | `2` |
| `ENABLE_LATS` | 启用 LATS 候选搜索 | `false` |
| `LATS_CANDIDATES` | 候选方案数量 | `3` |

### 安全策略

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `ALLOW_SHELL` | 允许 Shell 执行 | `true` |
| `SHELL_BLACKLIST` | 命令黑名单 | `rm -rf /,rm -rf ~,...` |

### Human-in-the-Loop

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `HITL_MODE` | 确认模式 | `risky` |
| `HITL_TOOLS` | 需确认的工具 | `run_shell,write_file,edit_file` |

| 模式 | 说明 |
|------|------|
| `all` | 所有工具调用均需确认 |
| `risky` | 仅高危工具需确认（推荐） |
| `none` | 直接放行，不弹确认 |

### 自进化系统

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `ENABLE_EVOLUTION` | 启用自进化 | `true` |
| `EVOLUTION_REFLECT_MIN_TOOLS` | 触发反思的最小工具调用数 | `2` |
| `EVOLUTION_ANALYSIS_INTERVAL` | 后台深度分析间隔（小时） | `24` |

---

## 🛠️ 工具集

| 工具 | 说明 |
|------|------|
| `read_file` | 读取文件全文（支持并行读取多文件） |
| `write_file` | 写入完整文件（自动验证） |
| `edit_file` | 精确替换文本片段（自动验证） |
| `list_dir` | 列出目录结构 |
| `glob` | 按模式查找文件 |
| `grep` | 搜索文件内容（正则） |
| `run_shell` | 执行 Shell 命令（60s 超时） |
| `run_code` | 执行代码片段（12 种语言） |
| `web_search` | 互联网搜索（百度/Bing，支持正文提取） |
| `fetch_page` | 提取网页正文（httpx + 浏览器降级） |
| `share_file` | 向用户分享文件 |
| `todo` | 管理任务清单 |
| `memory_*` | 记忆系统（list/read/write/search/update/delete） |

---

## 📊 图表支持

支持 17 种 ECharts 图表类型，使用 `chart` 语言代码块：

| 类型 | 名称 | 适用场景 |
|------|------|----------|
| `bar` | 柱状图 | 分类对比 |
| `line` | 折线图 | 趋势变化 |
| `area` | 面积图 | 趋势累积 |
| `pie` | 饼图 | 占比分布 |
| `scatter` | 散点图 | 相关性分析 |
| `radar` | 雷达图 | 多维评估 |
| `funnel` | 漏斗图 | 转化率 |
| `gauge` | 仪表盘 | KPI 指标 |
| `treemap` | 矩形树图 | 层级占比 |
| `sunburst` | 旭日图 | 多层级数据 |
| `heatmap` | 热力图 | 时间分布 |
| `candlestick` | K线图 | 金融数据 |
| `boxplot` | 箱线图 | 统计分布 |
| `pictorialBar` | 象形柱图 | 创意展示 |
| `sankey` | 桑基图 | 流量分析（DAG 约束） |
| `tree` | 树图 | 层级结构 |
| `graph` | 关系图 | 网络关系 |

示例：
````markdown
```chart
{
  "type": "bar",
  "title": "季度营收",
  "xAxis": ["Q1", "Q2", "Q3", "Q4"],
  "series": [{ "name": "营收", "data": [100, 150, 120, 180] }]
}
```
````

---

## 📝 快捷键

| 快捷键 | 功能 |
|--------|------|
| `Ctrl/Cmd + N` | 新对话 |
| `Ctrl/Cmd + K` | 停止 Agent |
| `Ctrl/Cmd + I` | 聚焦输入框 |

---

## 🔧 技术栈

### 前端

- React 19 + TypeScript
- Vite 8
- Tailwind CSS 4
- react-markdown + remark/rehype 插件
- highlight.js（代码高亮）
- Mermaid（流程图）
- ECharts（数据图表，按需导入）
- KaTeX（数学公式）
- PlantUML / D2（架构图）

### 后端

- Python 3.10+
- FastAPI + WebSocket
- OpenAI SDK（兼容所有 OpenAI 接口）
- scrapling + patchright（网页抓取与反爬）
- readability-lxml（正文提取）
- python-docx / openpyxl / python-pptx（Office 解析）
- PyPDF2（PDF 解析）
- python-multipart（文件上传）

---

## 📄 License

MIT

---

## 🙏 致谢

本项目灵感来源于多种 Agent 范式的学术研究，感谢 ReAct、LATS、ReWOO 等论文的贡献。
