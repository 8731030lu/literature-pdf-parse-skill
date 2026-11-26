# 本地验证记录（真实执行，非正式评测）

> 本文件只记录**本机实际执行的命令与观测到的输出**，用于让复核者重跑。
> 不含任何正式案例答案、平台评分或对照结果；正式评测由平台在固定案例上运行。

## 环境

| 项 | 值 |
|---|---|
| 操作系统 | Windows 10.0.26200 x64 |
| Shell | PowerShell 7（pwsh） |
| Python | 3.12.14（`python --version`） |
| 第三方包 | 无（脚本仅用 `argparse/json/re/sys/collections`） |

## 1. 语法与入口

```bash
python -c "import ast; ast.parse(open('scripts/reading_order.py',encoding='utf-8').read())"
# 观测: AST OK

python scripts/reading_order.py --help
# 观测: 正常打印 usage 与 5 个选项（--input/--output/--y-origin/--margin-ratio/--page-height）
```

## 2. 示例夹具（双栏 + 跨页页眉 + 页码）

```bash
python scripts/reading_order.py -i examples/blocks_demo.json
```

观测（`order:column:kind`，按页分组）：

```text
p1  1:0:body  2:0:body  3:0:body  4:1:body  5:1:body  6:-1:header  7:1:page_number
p2  1:0:body  2:1:body  3:-1:header  4:1:page_number
```

判定：左栏三段读完再读右栏两段（非 L1→R1→L2 交错）；跨栏页眉与页码从正文流分离；无 `spanning` 误标。

## 3. 边界与失败模式

| 用例 | 命令要点 | 观测 |
|---|---|---|
| 空数组 | `echo "[]" \| python scripts/reading_order.py` | 输出 `[]`，退出码 0 |
| 非数组 JSON | `echo '{"a":1}'` | stderr `input must be a JSON array of blocks`，退出码 2 |
| 非法 JSON | `echo '{not json'` | stderr `input is not valid JSON: ...`，退出码 2 |
| 文件不存在 | `-i C:\no\such\file.json` | stderr `input file not found: ...`，退出码 2 |
| 输出不可写 | `-o Z:\nope\out.json` | stderr 警告并降级写 stdout，不崩溃 |
| 无坐标块 | `[{"page":1,"text":"only text"}]` | `kind=no_coord`，退出码 0 |
| 稀疏单栏页 | 两个全宽块 | 均 `body`（`near_margin=true`），不再误判边注 |
| bottom-origin | `--y-origin bottom`（y 向上增大） | 上下顺序正确、输出稳定 |
| 真实页高 | `--page-height 842` | 页眉/正文分离符合预期 |

## 4. 回归中发现并修复的三个缺陷

1. **跨栏页眉导致分栏失效**：整行宽块参与区间合并，把左右栏连成一段。
   修复：`column_bands()` 排除宽度 >60% 页宽的块。
2. **沟槽带被当作栏区间**：栏号错位为 0/1/2、普通栏内文本误标 `spanning`。
   修复：直接用合并后的文本带作为栏区间；`spans_columns()` 加 1pt 容差。
3. **稀疏页边距块被误判 `margin_note`**（可能误删正文）。
   修复：`header/footer` 仅在“跨页重复 + 位于边距带”时判定；其余保留 `body` 并附 `near_margin`。
   另新增 `--page-height`。

## 5. 包完整性

```text
files = 10 (含本文件 11)   total ≈ 55 KB   max file ≈ 12.5 KB
symlinks = none
SKILL.md frontmatter: name: literature-pdf-parse / description 存在
```

## 6. 端到端验证（真实 PDF 全链路）

目的：不只验证几何函数，而是验证"PDF → 坐标 → 切行 → 重排 → 真值比对"整条链路。

```bash
# 1) 生成合成双栏 PDF（无第三方依赖，纯标准库写 PDF 语法）
python tests/make_synthetic_pdf.py --out /tmp/synthetic_two_column.pdf
# 观测: wrote .../synthetic_two_column.pdf (1881 bytes)

# 2) 走真实解析链路并比对真值
python tests/run_e2e.py --pdf /tmp/synthetic_two_column.pdf --pdftotext <poppler>/pdftotext
```

观测：

```text
pages=2  blocks=15  expected=15
PASS: reading order matches ground truth
   1 p1 L1 left column first line alpha beta
   2 p1 L2 left column second line gamma
   3 p1 L3 left column third line delta epsilon
   4 p1 L4 left column next paragraph zeta
   5 p1 L5 left column next paragraph eta
   6 p1 R1 right column first line theta
   7 p1 R2 right column second line iota
   8 p1 R3 right column next paragraph kappa
   9 p1 Synthetic Two-Column Test Document
  10 p1 1
  11 p2 L1 page two left column lambda
  12 p2 L2 page two left column mu
  13 p2 R1 page two right column nu
  14 p2 Synthetic Two-Column Test Document
  15 p2 2
exit=0
```

**首次运行失败并修正**：首轮为 `blocks=11 expected=15`，左栏与右栏同一基线的行被并成一句（`L1 ... R1 ...`）。
根因是按 y 聚行时未按水平间距切段——这正是"串栏"的典型成因。`tests/run_e2e.py` 加入"相邻词间隙 > 8 pt 即另起一块"后通过；
该规则同时写入 `SKILL.md` §4 第 3 步与 `references/reading-order.md`。

环境：poppler `pdftotext`（`poppler-7070842eb60b3459` 运行时自带），PDF 由 `tests/make_synthetic_pdf.py` 生成，**合成文档，非正式案例**。

## 7. 未做与无法在本机完成的部分

- 未运行 PDF 渲染、OCR、表格重建与公式转录（需平台 `pdf-render-tool`/`ocr-tool` 与真实 PDF）。
- 未在任何正式案例上运行，未产生也不提交正式案例结果。
- 未取得任何平台评分；评分状态以平台查询为准。
