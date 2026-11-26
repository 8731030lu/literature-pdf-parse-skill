# 最小调用示例（示例，非正式案例）

> 本目录仅为**接口示意**：夹具是合成的两页双栏文本块，不是任何正式测试案例，输出也不得当作正式案例答案或成绩。
> 正式案例由平台提供并在平台上运行，参赛者不提交案例答案。

## 1. 输入

`examples/blocks_demo.json`：11 个文本块，覆盖第 1–2 页，含跨页重复页眉与页码，左右两栏各若干段。
坐标采用 **top-origin**（`y0` 为上边、`y1` 为下边），单位为 pt。

```json
[
  {"page": 1, "x0": 50, "y0": 30,  "x1": 530, "y1": 42,  "text": "Journal of Demo Studies, Vol. 1"},
  {"page": 1, "x0": 50, "y0": 120, "x1": 280, "y1": 132, "text": "Left column, paragraph one, line one."},
  {"page": 1, "x0": 300, "y0": 120, "x1": 530, "y1": 132, "text": "Right column, paragraph one."}
]
```

（上面只摘录 3 条，完整文件见同目录 `blocks_demo.json`。）

## 2. 调用

```bash
python3 scripts/reading_order.py \
  --input examples/blocks_demo.json \
  --output /app/work/blocks_demo.ordered.json \
  --y-origin top
```

若提取器给出真实页高（常见于 PDF 工具），建议显式传入，避免稀疏页把边距带压扁：

```bash
python3 scripts/reading_order.py -i examples/blocks_demo.json -o /app/work/out.json --page-height 842
```

## 3. 示意输出（在本机实际运行得到，仅此夹具成立）

第 1 页：

| order | column | kind | text |
|---|---|---|---|
| 1 | 0 | body | Left column, paragraph one, line one. |
| 2 | 0 | body | Left column, paragraph one, line two. |
| 3 | 0 | body | Left column, paragraph two. |
| 4 | 1 | body | Right column, paragraph one. |
| 5 | 1 | body | Right column, paragraph two. |
| 6 | — | header | Journal of Demo Studies, Vol. 1 |
| 7 | 1 | page_number | 1 |

第 2 页：`body`（左栏）→ `body`（右栏）→ `header` → `page_number`，顺序同上。

## 4. 这个示例说明了什么

- **先左栏读完再读右栏**：输出的 body 序列是 L1→L2→L3→R1→R2，不是按 y 交错的 L1→R1→L2。
  跨栏页眉（整行宽）已被排除在分栏判定之外——这是双栏论文退化成单栏的最常见原因。
- **页眉与正文分离**：页眉靠"跨页重复 + 位于边距带"判定，作为 `header` 输出在正文之后，供调用方剔除；正文流中不再出现页眉。
- **页码单列**：`page_number` 由正则识别，不混入正文。
- **栏号正确**：两栏分别为 `column=0`、`column=1`；跨栏块才标 `spanning`，普通栏内文本不会误标。

## 5. 这个示例**不**说明什么

- 不含 PDF 渲染、OCR、表格重建与公式转录；这些是 `SKILL.md` 第 6–8 步与其他 references 的内容。
- 坐标系与页高来自夹具，真实 PDF 需先由 `pdf-text-tool`（或 `pdftotext -bbox`）给出坐标；若为 PDF 原生坐标请改用 `--y-origin bottom`。
- 输出未经人工逐字校对，仅用于确认接口与几何规则；正式案例以平台运行结果为准。
