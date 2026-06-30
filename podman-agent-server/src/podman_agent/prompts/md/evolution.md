# 对话反思

你刚刚完成了一轮对话。请分析这轮交互并提取可复用的经验。

## 本轮对话摘要

{conversation_summary}

## 工具调用结果

{tool_results}

## 已有记忆库

{existing_memories}

## 输出要求

以 JSON 格式输出。仅在有值得记录的新发现时输出对应字段，没有新发现则输出空 JSON `{{}}`。

```json
{{
  "lessons": [
    {{
      "title": "简明标题（5-15字）",
      "content": "具体经验内容：问题背景 → 解决方案 → 验证方式",
      "category": "knowledge",
      "keywords": "关键词1,关键词2"
    }}
  ],
  "should_update": [
    {{
      "title": "已有记忆的精确标题",
      "update": "需要补充或修正的内容"
    }}
  ],
  "tool_insights": [
    {{
      "tool": "工具名",
      "pattern": "成功/失败的使用模式",
      "note": "注意事项或最佳实践"
    }}
  ],
  "user_preference": {{
    "key": "偏好维度（如 coding_style / communication / tech_stack）",
    "value": "偏好值",
    "confidence": 0.8
  }}
}}
```

## 重要约束

1. **高价值过滤**：只记录真正有复用价值的经验，不记录琐碎或一次性信息
2. **具体可操作**：经验内容必须包含具体解决方案，不写空泛建议
3. **避免重复**：对照已有记忆库，不重复记录已有内容
4. **偏好谨慎**：confidence 取值 0-1，仅观察到强信号时才给高值（>= 0.7）
5. **最小输出**：没有值得记录的新发现时直接输出 `{{}}`
