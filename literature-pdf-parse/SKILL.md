---
name: literature-pdf-parse
description: >
  把科研 PDF 解析为可复核的结构化结果：逐字正文、多栏阅读顺序、表格行列、章节层级、公式符号与扫描页 OCR，
  每一项都能指回原文页码与区块。Use when: 需要从论文/技术报告 PDF 稳定抽取正文、图注、脚注、参考文献、
  表格、公式并按题目的 output_contract 回填时使用。NOT for: 解读图表或公式的科学含义、改写/翻译内容、
  编辑或生成 PDF、一次性问答（这些不需要本 Skill 的解析流程）。
version: 2.0.0
---

# 科研 PDF 文档解析（结构可复核）

## 1. 用途与四个硬指标

把一份科研 PDF 变成**可复核、可继续处理**的结构化结果，而不是"看起来像全文"的一段文本。

- **提得全**：正文、图注、表题、脚注、参考文献逐字提取，不漏行、不丢段、不把页眉页脚混进正文。
- **排得对**：双栏/多栏、跨栏、跨页内容按原版面顺序输出，不串栏、不错行、不把相邻段落拼成一句。
- **拆得清**：章节层级、表格行列与单元格归属、公式上下标与希腊字母还原成结构。
- **核得回**：每段文字、每张表格、每个公式都能指回原文页码与区块；读不出的部分如实标注，不靠猜补齐。

适用范围：科研论文、技术报告、学位论文等**版面型 PDF** 的结构化解析。
不适用：解读图表/公式的科学含义；内容改写、翻译、润色；PDF 生成或编辑；无材料的空谈。

## 2. 运行预算与分阶段交付（先读这一节）

评测环境对每个案例给出硬预算：**64 次模型请求、900 秒、单响应 16384 token**。文档解析最容易在此失手——一份 20 页论文若"每页一次模型请求"，预算立刻耗尽，最终产物为空。因此：

**两条铁律**

1. **确定性工作交给脚本，不交给模型。** 分栏、排序、页眉页脚判定、行/块聚合、表格线检测都由 `scripts/` 完成，模型只做判定不了的语义归位与逐字校对。
2. **中途必须留下合法产物。** 预算过半（约第 32 次请求或第 450 秒）时，无论进度如何，先写一份 `status: partial` 的完整 `result.json`；此后每次改进都在其上覆盖，保证任何时刻被截断都有可评的东西。

**分阶段预算参考（单案例）**

| 阶段 | 动作 | 建议请求数 | 产出 |
|---|---|---|---|
| P0 侦察 | 读 `case.json` + `task.md`，`pdfinfo`，抽前 3 页字符数 | 1–2 | 形态判定（文字层/扫描件/加密）与页数 |
| P1 批量提取 | `pdf-text-tool withPosition` 或 `pdftotext -bbox`，**按 5–10 页一批** | 2–4 | 块坐标 JSON |
| P2 结构重建 | 跑 `scripts/reading_order.py`，聚类标题/图表/公式块 | 1–3 | 有序正文 + 块分类 |
| P3 表格与公式 | 仅对已检出区域处理 | 3–8 | `tables/*.md`、`formulas.json` |
| P4 扫描页 OCR | 仅无文字层页；渲染 300 dpi 后识别 | 每页 ≤2 | OCR 文本 + 原图定位 |
| P5 回填与自检 | 逐键回填 `output_contract`，写 `coverage.md` | 2–4 | `result.json` |

**禁止**：对同一文件重复读取；为每一页单独发起模型请求；为"再确认一次"重跑已成功的抽取；在正文尚未落盘时先做表格美化。

**降级顺序**（预算不足时按此舍弃，先保正文再保图表）：正文与 `output_contract` 必需字段 → 章节层级 → 图注/脚注/参考文献 → 表格 → 公式 → 扫描页 OCR。舍弃项写入 `degradations` 并说明原因，不得静默省略。

## 3. 输出契约（先看再动手）

1. 进入任务后**先读 `/input/case.json` 和 `/input/task.md`**，取 `case_id`、任务要求与 `output_contract`。
   - 不凭标签猜内容：以 `/input` 下真实文件为准，字段名以 `case.json` 实际键名为准。
2. **逐键镜像 `output_contract`**：把它当作待填模板，键名、层级、类型一律照抄，只填值。
   - 缺值写 `null`（标量）或 `[]`（列表），**不删键、不改名、不合并**；
   - 确实无此项时在该键旁记 `{"status": "not_reported", "reason": "..."}`，而不是让键消失；
   - 题目额外要求的字段可以加，但镜像键不得缺席。
3. 写 `/app/output/result.json`，至少包含：

| 键 | 内容 |
|---|---|
| `case_id` | 原样来自 `case.json` |
| `status` | `success / partial / insufficient_evidence / failed`（见 §7） |
| `result` | 按 `output_contract` 镜像回填 |
| `evidence` | 逐条 `{locator, quote, target}`（见 §6） |
| `sources` | 实际读取的文件路径、工具名与关键参数 |
| `uncertainty` | 读不出、模糊、冲突项 |
| `change_log` | 取舍与修正记录（含跨页合并、栏序调整） |
| `errors` / `degradations` | 失败项与降级项 |
| `run_meta` | 实测 `wall_time_s`、工具调用次数、页数、OCR 页数（**实测值，不估算**） |

4. 中间产物放 `/app/work`；可交付产物放 `/app/output`，正文/表格/公式都要有可编辑文本形态（`.md` / `.json` / `.csv`）。

## 4. 解析工作流

### 第 0 步：发现输入（P0）
- 扫描 `/input`，识别 `case.json`、`task.md` 与 PDF（不假设固定文件名/键名）。
- 文本按 `utf-8-sig` 读取并容错；坏 JSON、BOM、坏编码降级处理，不崩溃。

### 第 1 步：判定 PDF 形态（P0）
- 取页数、页尺寸、字体与 embedded 标志；抽前 3 页，**统计每页字符数**：
  - 有稳定文字层 → 第 2–7 步；
  - 文字层近乎空 → 扫描件，走第 8 步；
  - 无法打开 → 记录 `failed` 与原因（可能加密），不硬猜。
- 加密 PDF：试空密码一次即止；失败如实报 `failed`。

### 第 2 步：带坐标提取（P1，禁止用纯文本替代）
- 用 `pdf-text-tool` 的 **withPosition 模式**（或 `pdftotext -bbox`）取词/行级文本与包围盒 `(x0,y0,x1,y1)`、字号。
- 无坐标的纯文本**不能**作为最终正文：多栏顺序、表格归属、页眉页脚都无法从纯文本判定。
- 兜底链路：`pdf-text-tool` → `pdftotext -bbox` → 渲染+OCR；每级降级记入 `degradations`。

### 第 3 步：行/块聚合（P2，最易出错的一步）
- 先按 y 聚行（行内 y 中心差 ≤ 字号的 30%），**再按水平间距切段**：相邻词间隙显著大于词间空格（经验阈值 ≈ 2 倍字宽，或绝对 8 pt）时另起一块。
- 不做这步切分，左右两栏**同一基线**的行会被拼成一句（"左栏首行 + 右栏首行"），这是"串栏"最常见的成因，也是纯文本抽取最难自查的错误。
- 段落合并：同一栏内行距一致且上一行未以句末标点结束，视为同段。

### 第 4 步：版面结构识别（P2）
- **页眉/页脚**：位于顶/底边距带且**跨页重复**的文本（页码、刊名、作者缩写），标 `header/footer` 并从正文剔除（另存证据）。
- **分栏**：对**栏宽级**块（排除全宽块）的 x 区间合并，找跨页稳定的垂直沟槽，据此定栏数与栏边界（见 `references/reading-order.md`）。
- **区块分类**：`body | heading | caption | table | formula | header | footer | footnote | reference`，写入块元数据。

### 第 5 步：重建阅读顺序（P2）
- 单栏按 y 再按 x；多栏先分栏、栏内自上而下、再"左栏→右栏"拼接；跨页段落按续接规则合并。
- 用 `scripts/reading_order.py` 做确定性重排，只人工核对异常项。
- 分栏判定必须**排除全宽块**（页眉、跨栏大图）：整行宽块会把左右栏连成一段，使双栏退化为单栏。
- 已知真实页高时传 `--page-height`；仅凭文本包围盒估算会在稀疏页把边距带压扁。
- `header/footer` 只在**跨页重复**时判定；`near_margin` 只是提示，不得据此删正文。
- 自检：双栏页若输出中左右栏句子交替出现（L1→R1→L2），即为分栏或切行失败，回到第 3、4 步。

### 第 6 步：章节层级、表格、公式（P3）
- **层级**：按字号/加粗/编号（`1.`、`1.1`、`2.3.4`、罗马数字、字母序）识别，保留多级编号与页码；识别不出就标 `hierarchy_uncertain`，不硬编。
- **表格**：作为独立结构输出 Markdown/HTML/JSON，行列与单元格归属正确（含合并单元格、多层表头、跨页续表），规则见 `references/table-reconstruction.md`；数值转录不得改动。图片型表格走渲染+OCR 并标 `low_confidence`。
- **公式**：按结构元素识别，保留上下标、希腊字母与特殊符号（∂ ∫ Σ √ ± × → ≤ ≥ α β γ …），用 LaTeX 或 Unicode 一致转录，保留公式编号与定位；规则见 `references/formula-symbols.md`。

### 第 7 步：扫描页 OCR（P4，仅无文字层页）
- `pdf-render-tool`（或 `pdftoppm -r 300 -png`）渲染；灰度/二值化/去倾斜后 `ocr-tool` 识别，语言提示 `chi_sim+eng`；规则见 `references/ocr-workflow.md`。
- **后处理校验**：数字、单位、公式符号、希腊字母逐一与渲染图比对；低置信处标 `low_confidence` 并保留原图定位，不硬猜。
- 只为真正无文字层的页付 OCR 成本；混排文档按页判定，不要整本 OCR。

### 第 8 步：回填与自检（P5）
- 逐键回填 `output_contract`，每字段带 `locator + quote`。
- 写 `result.json` → 跑 §8 自检 → 写 `coverage.md` → 有余量再优化。

## 5. 四个核心规则的落地要点

### 5.1 提得全
- 图注、表题、脚注、参考文献、致谢、附录都算正文的一部分：单独归类但不丢弃。
- 页眉页脚、页码**分离**到证据字段，不混进正文，也不把正文误当页眉删掉。
- 抽查：`页数 × 每页期望字符量` 与提取总量比对；显著偏少要回头找漏段。

### 5.2 排得对
- 多栏必须先分栏再排序；图/表按版面位置插入正文流，跨栏大图/大表不拆进单栏。
- 先切行再排栏（§4 第 3 步）；只按 y 聚行会把两栏拼成一句。
- 跨页续接：上页末句未完、下页首句无句首大写/无编号的，按续接合并并记 `change_log`。

### 5.3 拆得清
- 章节层级、表格行列、公式符号都要还原为**可继续处理**的结构，不是平铺文本。
- 合并单元格用 `rowspan/colspan` 或显式标注；多层表头保留层级。

### 5.4 核得回
- 每个结论/数值/表格/公式至少一条证据：`{locator: "第3页 · 左栏 · 段落2", quote: "原文逐字片段", target: "..."}`。
- 读不出/模糊/冲突处如实标注，不靠上下文猜补齐。

## 6. 证据与溯源（硬要求）

- `locator` 统一格式：`第N页 · 栏位 · 区块`（如 `第3页 · 左栏 · 段落2`、`第5页 · 表格1 · 第2行第3列`）；能拿 bbox 就附 `bbox: [x0,y0,x1,y1]` 与 `method: text_layer|ocr|render`。
- `quote` 必须**逐字**（≥12 字符为宜），不是转述；拿不到逐字写 `quote_unavailable` 并说明原因。
- 证据可写进 `result.json` 的 `evidence`，也可另落 `/app/output/evidence_map.json` 或 `evidence_cards.jsonl`。
- 冲突不隐藏：同一指标两处不一致，两处都记录并标 `source_conflict`；未报告写 `not_reported`，**≠不存在**。

## 7. 状态与异常（诚实优先）

| 状态 | 使用条件 |
|---|---|
| `success` | 全部 `output_contract` 字段回填且有证据，无缺块 |
| `partial` | 主要字段完成但有缺块/低置信项，`uncertainty` 与 `degradations` 列清 |
| `insufficient_evidence` | 材料缺失/读不出，无法给出可信结果 |
| `failed` | 文件损坏、加密不可解、工具全部失败 |

**异常处置矩阵**

| 情况 | 检测 | 处置 | 状态影响 |
|---|---|---|---|
| 加密 PDF | 打开报错/需口令 | 试空密码一次，失败即停 | `failed`，写明加密 |
| 无文字层 | 每页字符数≈0 | 转 OCR；仍失败则保留渲染图 | `partial` |
| 乱码字体（cid/未映射） | 抽取含大量 `\ufffd`/无意义字符 | 标记 `garbled_font`，改走渲染+OCR | `partial` |
| 图片型表格 | 无文字层且无框线坐标 | 渲染+OCR，标 `low_confidence` | `partial` |
| 页码错乱/缺页 | 页序与标注不符 | 以物理页序为准，记录映射 | 记 `change_log` |
| 旋转页 | 页面 `/Rotate` ≠ 0 | 按可视化方向归一后再排序 | 记 `change_log` |
| 半栏/通栏混排 | 各页栏数不一致 | **按页**分别判定，记录每页栏数 | 记 `uncertainty` |

- **不得编造**：缺失软件状态、数值、引用、DOI 一律不造；写 `pending_human` 或对应状态。
- 重复运行结果应一致：固定顺序、无随机；OCR 不确定性记入 `uncertainty`。

## 8. 自检与覆盖报告（交付前逐项过）

**8.1 结果自检**

- [ ] `case_id` 来自输入且未改；`status` 是四个合法值之一。
- [ ] `output_contract` 全部键已镜像回填，无删键/改名；缺值显式 `null`/`[]` 或 `not_reported`。
- [ ] 每个关键结论/数值/表格/公式都有 `locator + quote`。
- [ ] 页眉页脚已从正文分离；双栏顺序抽查一段与渲染图一致（无 L1→R1→L2 交替）。
- [ ] 表格行列与单元格归属抽查正确；公式上下标/希腊字母抽查正确。
- [ ] 未报告、读不出、冲突项都在 `uncertainty`/`errors`/`degradations` 说明。
- [ ] `run_meta` 为实测值（耗时、调用次数、页数），不含估算。

**8.2 覆盖报告 `coverage.md`**

在 `/app/output/coverage.md` 写一张与实际产物对应的对照表，让复核者无需读全文即可定位证据。**只写已核实的项**，未做的写 `pending` 并说明原因：

```markdown
| 评分项 | 本案例证据 | 状态 |
|---|---|---|
| 任务完成度 | result.json：contract 键 6/6 已回填 | ok |
| 结果正确性 | 抽查 3 处 locator+quote 与渲染图一致（第1页左栏、第3页表格1、第5页公式2） | ok |
| 结果完整性 | 标题/作者/摘要/章节/图表题注/公式/参考文献 7 类齐备；无附录 | ok |
| 结果可核验性 | evidence 42 条，均含 page+bbox+method | ok |
| 质量增益 | 相对纯文本抽取：修正 2 处串栏、1 处跨页续表合并（见 change_log） | ok |
| 效率增益 | 实测 6 分 40 秒 / 21 次请求（run_meta） | ok |
| 异常与降级 | 第 7 页无文字层，OCR 置信 0.62，已标 low_confidence | 见 uncertainty |
```

## 9. 最小调用示例（示例，非正式案例）

输入：`/input/case.json` 声明 `case_id: demo-1`、`output_contract: {title, authors, abstract, tables, formulas}`；`/input/paper.pdf` 为一份两栏论文（第 3 页含一张表格）。

调用：加载本 Skill 后按 §4 工作流执行，产出：

```json
{
  "case_id": "demo-1",
  "status": "success",
  "result": {
    "title": "Enhanced Ion Transport in Solid Electrolytes",
    "authors": "A. B. Chen; C. D. Li",
    "abstract": "We report ... (逐字)",
    "tables": ["/app/output/tables/table_1.md"],
    "formulas": ["/app/output/formulas.json"]
  },
  "evidence": [
    {"locator": "第1页 · 右栏 · 段落1", "quote": "Enhanced Ion Transport in Solid Electrolytes", "target": "title", "method": "text_layer"},
    {"locator": "第3页 · 表格1 · 第2行第3列", "quote": "0.92", "target": "tables[0]", "method": "text_layer"}
  ],
  "sources": ["/input/paper.pdf", "pdf-text-tool(withPosition)"],
  "uncertainty": [],
  "change_log": ["第2-3页表格跨页，已按续表合并"],
  "errors": [],
  "degradations": [],
  "run_meta": {"wall_time_s": 0, "tool_calls": 0, "pages": 0, "ocr_pages": 0}
}
```

（`run_meta` 中的 0 为占位，实际填写**实测值**；示意输出不得冒充正式案例结果。）

**脚本级与端到端示例**：`examples/demo.md` 给出合成两页双栏夹具 → `scripts/reading_order.py` → 示意输出；`tests/run_e2e.py` 用**真实 PDF** 走完 `pdftotext -bbox → 行切分 → 重排 → 与真值比对` 全链路（生成器 `tests/make_synthetic_pdf.py`，合成文档，非正式案例）。

## 10. 边界

- 一个 Skill 只解决"版面型 PDF 的结构化解析"；不扩展到通用 PDF 编辑、语义理解、自动写作。
- 没有真实材料时输出 `insufficient_evidence` 并列缺口，不用示例填充。
- 关键数值/公式在使用前须与原始页面再次核对；解析产物是"提取证据"，不是"已验证事实"。
