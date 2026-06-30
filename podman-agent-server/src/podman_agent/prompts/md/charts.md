# 数据图表输出指南（Chart 代码块）

当用户要求数据可视化时，在你的**文本回复中**直接输出一个 `chart` 语言的 Markdown 代码块，前端会自动渲染为交互式图表。

**重要：`chart` 不是工具，不要通过工具调用它！它只是 Markdown 代码块的语言标识。**

## 基础用法

```chart
{
  "type": "bar",
  "title": "图表标题",
  "xAxis": ["A", "B", "C"],
  "series": [
    { "name": "系列1", "data": [10, 20, 30] }
  ]
}
```

## 支持的 17 种图表类型

| type | 名称 | 适用场景 |
|------|------|----------|
| bar | 柱状图 | 分类对比、季度营收 |
| line | 折线图 | 趋势变化、时间序列 |
| area | 面积图 | 趋势累积、填充效果 |
| pie | 饼图 | 占比分布、份额分析 |
| scatter | 散点图 | 相关性分析、分布特征 |
| radar | 雷达图 | 多维能力评估、综合对比 |
| funnel | 漏斗图 | 转化率、销售漏斗 |
| gauge | 仪表盘 | KPI、完成率、进度指标 |
| treemap | 矩形树图 | 层级占比、磁盘空间分析 |
| sunburst | 旭日图 | 多层级层级数据、组织架构 |
| heatmap | 热力图 | 时间分布、相关性矩阵 |
| candlestick | K线图 | 股票、金融数据 |
| boxplot | 箱线图 | 统计分布、异常值检测 |
| pictorialBar | 象形柱图 | 创意数据展示、信息图 |
| sankey | 桑基图 | 流量分析、能量流动 |
| tree | 树图 | 层级结构、组织树 |
| graph | 关系图 | 网络关系、知识图谱 |

## 特殊数据格式

**漏斗图 / 仪表盘**：
```chart
{ "type": "funnel", "title": "销售转化", "xAxis": ["访问", "咨询", "下单", "付款"], "series": [{ "data": [1000, 800, 500, 300] }] }
```
```chart
{ "type": "gauge", "title": "完成率", "series": [{ "name": "进度", "data": [72.5] }], "max": 100, "unit": "%" }
```

**矩形树图 / 旭日图**（层级数据用 children）：
```chart
{
  "type": "treemap",
  "title": "磁盘占用",
  "series": [{ "children": [
    { "name": "文档", "value": 30, "children": [{ "name": "PDF", "value": 15 }, { "name": "Word", "value": 15 }] },
    { "name": "图片", "value": 50 },
    { "name": "视频", "value": 20 }
  ]}]
}
```

**热力图**（data 格式 `[x索引, y索引, 值]`）：
```chart
{
  "type": "heatmap",
  "title": "各时段活跃度",
  "xAxis": ["周一", "周二", "周三", "周四", "周五"],
  "yAxis": ["上午", "下午", "晚上"],
  "series": [{ "data": [[0,0,30],[1,0,45],[2,0,60],[0,1,50],[1,1,70],[2,1,80],[0,2,20],[1,2,40],[2,2,55]] }]
}
```

**K线图**（data 格式 `[开盘, 收盘, 最低, 最高]`）：
```chart
{
  "type": "candlestick",
  "title": "股价走势",
  "xAxis": ["周一", "周二", "周三", "周四", "周五"],
  "series": [{ "data": [[20,30,18,35],[30,25,22,33],[25,32,24,36],[32,28,26,34],[28,35,27,38]] }]
}
```

**箱线图**（data 格式 `[最小值, Q1, 中位数, Q3, 最大值]`）：
```chart
{
  "type": "boxplot",
  "title": "成绩分布",
  "xAxis": ["数学", "语文", "英语"],
  "series": [{ "data": [[50,65,75,85,98],[45,60,72,82,95],[55,70,78,88,96]] }]
}
```

**象形柱图**：
```chart
{
  "type": "pictorialBar",
  "title": "水果销量",
  "xAxis": ["苹果", "香蕉", "橙子", "葡萄"],
  "series": [{ "name": "销量", "data": [120, 200, 150, 80] }]
}
```

**桑基图**（nodes + links，**注意：数据必须是有向无环图 DAG，不能有循环回流**）：
```chart
{
  "type": "sankey",
  "title": "用户流量分析",
  "series": [{
    "nodes": [{"name": "搜索引擎"}, {"name": "社交媒体"}, {"name": "邮件营销"}, {"name": "产品页"}, {"name": "博客"}, {"name": "注册页"}, {"name": "购物车"}, {"name": "结算"}, {"name": "支付成功"}, {"name": "流失"}],
    "links": [{"source": "搜索引擎", "target": "产品页", "value": 200}, {"source": "搜索引擎", "target": "博客", "value": 150}, {"source": "社交媒体", "target": "产品页", "value": 90}, {"source": "社交媒体", "target": "博客", "value": 60}, {"source": "邮件营销", "target": "产品页", "value": 40}, {"source": "博客", "target": "注册页", "value": 80}, {"source": "产品页", "target": "注册页", "value": 180}, {"source": "产品页", "target": "购物车", "value": 160}, {"source": "产品页", "target": "流失", "value": 110}, {"source": "注册页", "target": "购物车", "value": 130}, {"source": "注册页", "target": "流失", "value": 50}, {"source": "购物车", "target": "结算", "value": 200}, {"source": "购物车", "target": "流失", "value": 90}, {"source": "结算", "target": "支付成功", "value": 170}, {"source": "结算", "target": "流失", "value": 30}]
  }]
}
```
> ⚠️ 桑基图不支持回流（如 A→B→A），所有节点必须按单向流动排列。

**树图**（层级数据用 children）：
```chart
{
  "type": "tree",
  "title": "组织架构",
  "series": [{ "children": [
    { "name": "CEO", "children": [
      { "name": "技术部", "children": [{"name": "前端"}, {"name": "后端"}, {"name": "运维"}] },
      { "name": "市场部", "children": [{"name": "品牌"}, {"name": "运营"}] },
      { "name": "财务部" }
    ]}
  ]}]
}
```

**关系图**（nodes + links，支持 force/circular 布局）：
```chart
{
  "type": "graph",
  "title": "技术栈关系",
  "layout": "force",
  "series": [{
    "nodes": [{"name": "React", "symbolSize": 60}, {"name": "Vue", "symbolSize": 50}, {"name": "TypeScript", "symbolSize": 55}, {"name": "JavaScript", "symbolSize": 45}, {"name": "Node.js", "symbolSize": 40}],
    "links": [{"source": "React", "target": "TypeScript"}, {"source": "Vue", "target": "TypeScript"}, {"source": "React", "target": "JavaScript"}, {"source": "Vue", "target": "JavaScript"}, {"source": "TypeScript", "target": "JavaScript"}, {"source": "Node.js", "target": "JavaScript"}]
  }]
}
```

## 可选字段
- `"legend": false` — 隐藏图例
- `"smooth": true` — 折线平滑
- `"stack": true` — 堆叠（柱状图/折线图）
- `"min": 0, "max": 100` — 数值范围（仪表盘/热力图）
- `"unit": "%"` — 单位（仪表盘）
- `"orient": "vertical"` — 方向（桑基图/树图）
- `"shape": "circle"` — 象形柱图符号形状（circle/rect/roundRect/triangle/diamond/pin/arrow）
- `"layout": "circular"` — 关系图布局（force/circular/none）
- `"roam": false` — 禁用关系图拖拽缩放
- `"edgeLabel": true` — 显示关系图边标签
- `"symbolSize": 50` — 关系图节点大小
