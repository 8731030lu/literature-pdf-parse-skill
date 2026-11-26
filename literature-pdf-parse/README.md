# 科研 PDF 文档解析 Skill（阅读01｜文献文档解析）

把科研 PDF 解析为**可复核的结构化结果**：逐字正文、多栏阅读顺序、表格行列、章节层级、公式符号、扫描页 OCR，每一项都能指回原文页码与区块。围绕"提得全 / 排得对 / 拆得清 / 核得回"四个问题。

## 目录结构

```text
literature-pdf-parse/
├── SKILL.md                       # 主 Skill：工作流、输出契约、四个核心规则、自检、最小示例
├── README.md                      # 本文件：用途、依赖、调用、校验、限制
├── VERIFICATION.md                # 本地真实执行记录（命令与观测输出，非平台评测）
├── references/
│   ├── reading-order.md           # 多栏阅读顺序与文字提取（排得对）
│   ├── table-reconstruction.md    # 复杂表格解析（拆得清 · 表格）
│   ├── formula-symbols.md         # 公式与特殊字符转录（拆得清 · 符号保真）
│   ├── ocr-workflow.md            # 扫描版 PDF 与 OCR（提得全 · 扫描件）
│   └── result-schema.md           # result.json 契约与异常处理
├── scripts/
│   └── reading_order.py           # 确定性多栏重排脚本（纯标准库）
├── tests/
│   ├── make_synthetic_pdf.py      # 生成合成双栏 PDF（纯标准库，无第三方依赖）
│   ├── run_e2e.py                 # PDF→pdftotext→切行→重排→真值比对 全链路测试
│   └── expected_order.json        # 上述合成文档的真值阅读顺序
└── examples/
    ├── blocks_demo.json           # 合成文本块夹具（示例，非正式案例）
    └── demo.md                    # 最小调用示例：输入→命令→示意输出（标注为示例）
```

## 用途与适用条件

- **适用**：论文、技术报告、学位论文等版面型 PDF 的结构化解析；需要逐字正文、多栏顺序、表格、公式、图注、脚注、参考文献并回填题目 `output_contract` 时。
- **不适用**：解读图表/公式的科学含义；改写/翻译内容；编辑或生成 PDF；一次性问答。

## 调用方式（Agent 视角）

1. 加载本 Skill（前端 `name`/`description` 触发）。
2. 读 `/input/case.json`（`case_id`、`output_contract`）与 `/input/task.md`，定位真实 PDF。
3. 按 `SKILL.md` §2 的**预算计划**（64 次请求 / 900 秒 / 单响应 16k token）分配调用，再按 §4 工作流执行：判定形态 → 带坐标提取 → 切行聚合 → 版面识别 → 阅读顺序 → 章节/表格/公式 → OCR → 回填与自检。预算过半必须先落一份合法 `partial` 结果。
4. 结果写 `/app/output/result.json`（含 `case_id`、`status`、`result`、`evidence`、`sources`、`uncertainty`、`change_log`、`errors`）。

## 关键输入 / 输出

- **输入**：`/input/case.json`、`/input/task.md`、实际 PDF 文件；可用工具 `pdf-text-tool`（带坐标）、`pdf-render-tool`、`ocr-tool`，兜底 `pdftotext -bbox`、`pdftoppm`。
- **输出**：`/app/output/result.json`（主结果）；正文/表格/公式另有可编辑 `.md`/`.json`/`.csv`；扫描页渲染图作为证据。

## 依赖与版本

| 依赖 | 版本 / 条件 | 说明 |
|---|---|---|
| Python | 3.8+（本包在 3.12.14 上验证） | `scripts/reading_order.py` 仅用标准库 `argparse/json/re/sys/collections`，**无第三方包** |
| PDF 文本提取 | 平台 `pdf-text-tool`（带坐标）；兜底 poppler `pdftotext -bbox`（7.x 验证） | 必须能给出每块的 `x0/y0/x1/y1` |
| 页面渲染 | 平台 `pdf-render-tool`；兜底 `pdftoppm -r 300 -png` | 仅扫描页 OCR 与抽查核对时需要 |
| OCR | 平台 `ocr-tool`，语言 `chi_sim+eng` | 无文字层页面才调用 |
| 网络 | 不需要 | 脚本完全离线；仅提交时用官方 CLI |

安装方式：把本目录放到 Agent 的 skills 目录即可，无需 `pip install`。

## 脚本用法

```bash
# 输入：块 JSON 数组（每块含 page, x0, y0, x1, y1, text）
python3 scripts/reading_order.py --input blocks.json --output ordered.json --y-origin top
# 若提取器为 PDF 原生坐标（y 向上增大）：
python3 scripts/reading_order.py -i blocks.json -o ordered.json --y-origin bottom
# 已知真实页高时显式给出，避免稀疏页把边距带压扁：
python3 scripts/reading_order.py -i blocks.json -o ordered.json --page-height 842
```

输出为同样的块，新增 `column`、`kind`、`near_margin`、`order`：
`kind ∈ {body, header, footer, page_number, spanning, no_coord}`；
`near_margin` 仅作几何提示，**页眉/页脚只在跨页重复时才判定**，避免把稀疏页首行误删。

脚本只做**几何排序**（分栏、栏内自上而下、栏间左→右、页眉页脚/页码识别），不做语义判断；跨页续接等语义判定由 Agent 依 `references/reading-order.md` 处理并核对渲染图。

## 运行测试（可复现）

```bash
# 1) 生成合成双栏 PDF（纯标准库，无需第三方包）
python tests/make_synthetic_pdf.py --out /tmp/synthetic_two_column.pdf
# 2) 走真实链路：pdftotext -bbox -> 切行 -> reading_order.py -> 与真值比对
python tests/run_e2e.py --pdf /tmp/synthetic_two_column.pdf --pdftotext "$(command -v pdftotext)"
# 期望：pages=2 blocks=15 expected=15 / PASS
```

`tests/` 中的文档是**合成样本**，用于验证链路与几何规则，不是任何正式案例；真值 `tests/expected_order.json` 由生成器按构造顺序写出。

## 已验证内容（本机真实执行）

| 用例 | 结果 |
|---|---|
| `python -m py_compile scripts/reading_order.py` | 退出码 0 |
| `--help` | 正常打印用法 |
| `examples/blocks_demo.json`（双栏 + 跨页页眉 + 页码） | L1→L2→L3→R1→R2，`column=0/1`，页眉与页码分离，无 `spanning` 误标 |
| 空数组 `[]` | 输出 `[]`，退出码 0 |
| 无坐标块 | 标 `no_coord`，不崩溃 |
| 稀疏单栏页 | 全部 `body`（仅 `near_margin=true`），不再误判为边注 |
| `--y-origin bottom` | 上下关系正确、顺序稳定 |
| 端到端全链路（`tests/run_e2e.py`） | 真实 PDF → `pdftotext -bbox` → 切行 → 重排 → 真值比对：`pages=2 blocks=15 expected=15`，**PASS** |

## 状态与诚实性

- `status` 四值：`success / partial / insufficient_evidence / failed`。
- 未报告 ≠ 不存在；读不出、模糊、冲突都进 `uncertainty`，不靠猜补齐。
- 不编造数值、引用、DOI、公式、软件状态，也不编造正式案例答案或测试成绩。

## 提交说明（针对 Bohrium Playground 挑战）

- 核心交付物为 `SKILL.md` 及其 `references/`、`scripts/`、`examples/`；平台把 Skill 安装到 `/skills/weekly-skill` 后在固定案例上运行 DeepSeek Harness，与基础 Agent 对照评分。**正式案例与对照由平台提供，参赛者不提交案例答案。**
- 资源约束：≤50 个 UTF-8 文本文件，单文件 ≤500KB，总计 ≤2MB，无符号链接。本包满足（14 个文件、约 70 KB，最大单文件约 16 KB）。
- GitHub 附加分（可选，5 分）：把本目录推到公开 GitHub 仓库，在提交目录根路径放 `GITHUB_URL.txt`（第一行写链接；如需指定文件，第二行写相对路径）。**未提交该项，未伪造链接。**
- 提交用官方 CLI：`playground submit --challenge-id product-arena-08-3027d350 --skill <本目录> --outputs <本目录> --trace <会话日志.jsonl>`。

## 边界与已知限制

- 只解决版面型 PDF 的结构化解析，不扩展到通用 PDF 编辑、语义理解、自动写作。
- `reading_order.py` 只重排"已带坐标"的文本块；不含 PDF 解析、渲染与 OCR 本身。
- 页高缺省时由文本包围盒估算，稀疏页的边距带会偏窄（用 `--page-height` 或依赖 `near_margin` 提示）。
- 单页只有极少块、或栏间无稳定空白时，分栏判定可能退化为单栏；此类情况应在 `uncertainty` 标注并人工核对渲染图。
- OCR 与公式/表格重建的置信度依赖工具能力，低置信处须标注而非硬猜。
