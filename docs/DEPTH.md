# 住户调查权重校正规则登记

- 规模：中型

## 功能模块

| 模块 | 动作 | 接口 | 核心文件 | 测试 |
|---|---|---|---|---|
| M1 样例采信 | 预览并定位坏行 | `POST /api/stages/intake` | `app/intake/service.py` | `tests/test_intake.py` |
| M2 分层编排 | 检查领域约束、生成迁户前后台账 | `POST /api/stages/prepare` | `app/modules/prepare.py` | `tests/test_prepare.py`、`tests/test_moves.py` |
| M3 权重调整 | 查看业务计算结果 | `POST /api/stages/calculate` | `app/modules/calculate.py` | `tests/test_calculate.py` |
| M4 覆盖检查 | 查看签收判定 | `POST /api/stages/policy` | `app/modules/policy.py` | `tests/test_policy.py` |
| M5 运行对账 | 对照输入、采信、隔离行与逐层台账 | `POST /api/stages/balance` | `app/modules/reconcile.py` | `tests/test_reconcile.py` |
| M6 批次复核 | 执行批次并签发或暂缓 | `POST /api/runs、PATCH /api/runs/<id>` | `app/review/service.py` | `tests/test_review.py` |
| M7 证据交付 | 下载复核清单 | `GET /api/runs/<id>/evidence` | `app/evidence/render.py` | `tests/test_evidence.py` |

## 输入陷阱

| 编号 | 规则 | 处理 | 测试 |
|---|---|---|---|
| TRAP-02 | 去除 BOM | `app/intake/reader.py` | `tests/test_intake.py::test_bom_preserves_identifier` |
| TRAP-03 | 按逻辑记录读取引号内换行 | `app/intake/reader.py` | `tests/test_intake.py::test_quoted_newline_is_one_logical_record` |
| TRAP-04 | 重复表头计入忽略行 | `app/intake/service.py` | `tests/test_intake.py::test_repeated_header_is_counted` |
| TRAP-05 | 异常列数隔离 | `app/intake/schema.py` | `tests/test_intake.py::test_extra_column_is_isolated` |
| TRAP-06 | 归一化全角数字和千分位 | `app/intake/numeric.py` | `tests/test_intake.py::test_full_width_and_grouping_are_canonical` |
| TRAP-07 | 空值行隔离 | `app/intake/numeric.py` | `tests/test_intake.py::test_sentinel_keeps_row_out_of_total` |
| TRAP-08 | 记录键保留前导零 | `app/intake/schema.py` | `tests/test_intake.py::test_bom_preserves_identifier` |
| TRAP-14 | 冲突版本都进入隔离 | `app/intake/resolve.py` | `tests/test_intake.py::test_duplicate_conflict_removes_both_copies` |
| TRAP-16 | 引号未闭合时拒收文件 | `app/intake/reader.py` | `tests/test_intake.py::test_unclosed_quote_invalidates_source` |
| TRAP-18 | 区分空文件、全空白和仅表头 | `app/intake/reader.py` | `tests/test_intake.py::test_empty_states_have_distinct_causes` |
| TRAP-26 | 拒绝旧版本复核 | `app/review/store.py` | `tests/test_review.py::test_review_optimistic_lock` |

## 领域反例

同一抽样层按批次合计入样和回应户数。精确有理数计算无应答调整，保留分子分母；分层总体与普查框核验。

### 迁户口径

- 每个回应户在任一层只计一次；迁出按净额从原层减、在新层加。
- 每层权重总和必须等于该层最新普查目标（`balance.strata[].balanced`）。总量相等但逐层此消彼长仍算差异（`STRATUM_MISMATCH`）。
- 原层 `wave` 应答记录不删除，台账保留 `before`/`moved_out`/`moved_in`/`after` 与记录键，供追责与回读。
- 按（业务组, 分层）逐层回读，同号分层不跨组合并。

挡住签发的情形都会写入 `balance.blockers`，并在 `PATCH` 失败时以 `records` 返回记录键：

| 码 | 含义 | 依据 |
|---|---|---|
| `MOVE_CONFLICT` | 同一原层同一批迁出户被指向不同新层，或迁户行指向自身/零户 | `tests/test_moves.py` |
| `MOVE_TARGET_MISSING` | 迁入层或参与层缺 `census` 目标 | `tests/test_moves.py` |
| `MOVE_REPLAY` | 同一迁户内容换记录键再次到达，或已按迁后口径报数的层再次迁出 | `tests/test_moves.py` |
| `MOVE_OVERDRAW` | 迁出量超过原层在册/回应户数 | `tests/test_moves.py` |
| `STRATUM_MISMATCH` / `MISMATCH` | 逐层权重总和与目标不符 | `tests/test_policy.py` |
| `NO_RESPONDENTS` / `EXCESS_RESPONSE` / `FRAME_*` | 既有分层约束 | `tests/test_prepare.py` |

### 发布失败

`APPROVED` 被挡时抛 `UNRESOLVED_ISSUES`，响应带 `records` 与 `details.blockers`。批次本身的 `status`、`revision`、`report`、`note` 不变；失败尝试写入 `attempts`（`outcome=BLOCKED`）并随证据导出。之后仍可暂缓或修正来源后重跑。重跑同字节不会重复挪户（同一 `run_id`）。

逐组预期结论见 `tests/test_policy.py`，计算过程证据见 `tests/test_calculate.py`，迁户流程见 `tests/test_moves.py`。
