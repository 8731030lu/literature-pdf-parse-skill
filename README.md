# literature-pdf-parse

科研 PDF 文档解析 Skill：把论文/技术报告 PDF 转成**可复核的结构化结果**，每一项都能指回原文页码与区块。

面向 Bohrium Playground 挑战「阅读01｜文献文档解析」（`product-arena-08-3027d350`）提交的作品。

## 这个仓库解决什么问题

把一份 PDF 变成"可继续处理的结构"而不是"看起来像全文的文本"，落点是四个硬指标：

- **提得全**：正文、图表题注、脚注、参考文献逐字提取，不丢段，页眉页脚不混进正文。
- **排得对**：双栏/多栏、跨栏、跨页按原版面顺序输出，不串栏、不错行。
- **拆得清**：章节层级、表格行列与单元格归属、公式上下标与希腊字母还原为结构。
- **核得回**：每段文字/表格/公式都能定位到页码与区块，读不出的如实标注。

## 仓库结构

```text
literature-pdf-parse/
├── SKILL.md                  # 主 Skill：预算计划、输出契约、工作流、异常矩阵、自检
├── README.md                 # 使用说明：依赖、调用、测试、限制
├── VERIFICATION.md           # 本机真实执行记录（命令与观测输出）
├── references/
│   ├── reading-order.md      # 多栏阅读顺序与文字提取
│   ├── table-reconstruction.md
│   ├── formula-symbols.md
│   ├── ocr-workflow.md
│   └── result-schema.md
├── scripts/
│   └── reading_order.py      # 确定性多栏重排（纯标准库）
├── tests/
│   ├── make_synthetic_pdf.py # 生成合成双栏 PDF（纯标准库）
│   ├── run_e2e.py            # PDF→pdftotext→切行→重排→真值比对
│   └── expected_order.json
└── examples/
    ├── blocks_demo.json
    └── demo.md               # 最小调用示例（标注为示例，非正式案例）
```

## 快速开始

```bash
# 1) 重排一组带坐标的文本块
python3 literature-pdf-parse/scripts/reading_order.py \
  --input blocks.json --output ordered.json --y-origin top

# 2) 跑端到端自测（需要 poppler 的 pdftotext）
python3 literature-pdf-parse/tests/make_synthetic_pdf.py --out /tmp/syn.pdf
python3 literature-pdf-parse/tests/run_e2e.py --pdf /tmp/syn.pdf --pdftotext pdftotext
# 期望：pages=2 blocks=15 expected=15 / PASS
```

依赖：Python 3.8+（脚本仅用标准库），poppler `pdftotext`（仅端到端测试需要）。无需 `pip install`。

## 关键设计

1. **预算优先**：评测环境每案例 64 次模型请求 / 900 秒 / 单响应 16k token，Skill 给出 P0–P5 分阶段请求配额，并要求预算过半先落一份合法的 `partial` 结果。
2. **契约逐键镜像**：把 `case.json` 的 `output_contract` 当模板，键名/层级照抄，缺值写 `null`/`[]` 或 `not_reported`，不删键、不改名。
3. **先切行再排栏**：按 y 聚行后必须按水平间距切段，否则两栏同一基线的行会被拼成一句——这是"串栏"最常见的成因。
4. **分栏排除全宽块**：跨栏页眉会把左右栏连成一段、使双栏退化为单栏。
5. **诚实状态机**：`success / partial / insufficient_evidence / failed`，缺材料不靠猜补齐。

## 验证

见 [VERIFICATION.md](literature-pdf-parse/VERIFICATION.md)。要点：三个脚本 AST 解析通过；几何用例与边界用例（空输入、无坐标、稀疏单栏、bottom-origin、缺文件、坏 JSON、输出不可写）均通过；端到端链路 `pages=2 blocks=15 expected=15` PASS。

开发过程中修掉三个真实缺陷：跨栏页眉致分栏失效、沟槽带被当成栏区间、稀疏页边距块被误判为边注。

## 适用范围与限制

- 适用于版面型 PDF 的结构化解析；不解读图表/公式的科学含义，不做改写、翻译或 PDF 生成。
- `reading_order.py` 只重排已带坐标的文本块，不含 PDF 解析、渲染与 OCR 本体。
- 页高缺省时由文本包围盒估算，稀疏页边距带会偏窄（用 `--page-height`）。
- 扫描页 OCR 与公式/表格重建的精度受工具能力限制，低置信处标注而非硬猜。

## 说明

`tests/` 与 `examples/` 中的文档均为**合成样本**，用于验证链路与几何规则，不是任何正式测试案例，也不含正式案例答案。
