# result.json 契约与异常处理

## 1. result.json 最小结构

```json
{
  "case_id": "来自 /input/case.json，原样，不得改",
  "status": "success | partial | insufficient_evidence | failed",
  "result": {
    "……按 output_contract 原样回填全部键，缺值 null/[]……"
  },
  "evidence": [
    {"locator": "第3页 · 左栏 · 段落2", "quote": "原文逐字片段", "target": "result.<字段>"}
  ],
  "sources": ["/input/paper.pdf"],
  "uncertainty": [
    {"locator": "第5页 · 表格1", "item": "第2行第3列数值", "reason": "低置信度 OCR"}
  ],
  "change_log": ["第2-3页表格跨页，已按续表合并"],
  "errors": [],
  "degradations": [],
  "runtime": {"started_at": "...", "finished_at": "...", "tools_used": ["pdf-text-tool", "ocr-tool"]}
}
```

## 2. 字段规则

- `case_id`：从 `case.json` 原样复制；没有就写 `null` 并在 `errors` 说明，不自行生成。
- `status`：只用四个合法值之一，含义见 `SKILL.md` §6。
- `result`：**原样回填** `output_contract` 的全部键：
  - 不改名、不删未知键、不合并字段；
  - 单值字段缺值给 `null`，列表字段缺值给 `[]`；
  - 数值保留原精度与单位，不四舍五入、不换算（除非题目要求且记录换算）。
- `evidence`：每条 `{locator, quote, target}`；`quote` 逐字，拿不到写 `quote_unavailable` + 原因。
- `uncertainty`：读不出、模糊、`source_conflict`、`low_confidence`、`not_reported` 都放这里并给理由。
- `change_log`：合并续表、跨页续接、OCR 更正、页眉页脚剔除等**所有改变原文/结构的动作**都要记。
- `errors` / `degradations`：失败项与降级项分开；`degradations` 用于"有结果但不完整/降级"。

## 3. 状态码判定顺序

1. 有未处理的致命错误（文件损坏、加密不可解、工具全失败）→ `failed`。
2. 材料缺失或完全读不出 → `insufficient_evidence`。
3. 主要字段完成但存在缺块/低置信项 → `partial`（此时 `uncertainty`/`degradations` 必须非空）。
4. 全部完成且有证据 → `success`。

## 4. 异常处理表

| 场景 | 应对 |
|---|---|
| 空输入目录 | 退出码 0，写 `insufficient_evidence`，列出缺失材料，不抛异常 |
| 坏 JSON / 坏编码 / BOM | 按 `utf-8-sig` 容错读取；仍失败记入 `errors`，继续处理其余材料 |
| 加密 PDF | 试空密码/常见公开密码一次即止；失败报 `failed`，不伪造内容 |
| 无文字层扫描件 | 走 OCR（`references/ocr-workflow.md`），低置信处标注 |
| 图片型表格 | 渲染 + OCR + 表格重建，`low_confidence` 标注 |
| 乱码/缺字体（无 ToUnicode） | 记录 `degradations`，用渲染图比对；无法恢复的字符标 `unreadable`，不猜 |
| 页码错乱 | 按实际文件顺序处理，`change_log` 记录页码与物理页不符之处 |
| 跨页续表/续段 | 按 `references/table-reconstruction.md` §5、`reading-order.md` §6 合并并记录 |
| 重复运行 | 同一输入两次运行结果一致（固定随机种子、确定性布局） |
| 单文件超限 | 设 2MB 上限，超限跳过并记 `degradations` |

## 5. 诚实性红线

- 不编造缺失的软件状态、数值、引用、DOI、公式、结论。
- "未报告"（`not_reported`）≠ "不存在"（`absent`）；二者分开标注。
- 关键数值/公式在使用前与原始页面再次核对；解析产物是"提取证据"，不是"已验证事实"。
