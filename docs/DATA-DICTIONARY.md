# 字段与业务定义

输入编码 UTF-8，允许 BOM。首行必须匹配样例列顺序。记录键和业务组保留原始字符串。`kind` 允许 wave, census, move。说明列 `note` 可以跨行，限制 200 字。

业务字段按 `stratum`、`households`、`responded`、`target` 排列。数字接受非负整数、全角数字和完整千分位。空串、短横线、N/A、NULL 与未知为缺值。无关字段用 0 占位。

同一抽样层按批次合计入样和回应户数。精确有理数计算无应答调整，保留分子分母；分层总体与普查框核验。

## 迁户更正（kind=move）

住户从原抽样层迁往新层时追加 `move` 行：

| 列 | 含义 |
|---|---|
| `stratum` | 迁出前的原层 |
| `target` | 迁入的新层（沿用普查目标列） |
| `households` | 迁出户数 |
| `responded` | 其中在原层已回应的户数 |

原层 `wave` 应答记录不删除，只在台账里记为迁出，留作追责。迁户按净额搬运：回应户从原层减、在新层加，每个回应户在任一层只计一次。原层与新层都必须有 `census` 目标行。

逐层台账 `prep.ledger` 与 `measure.strata` 给出迁户前后的户数、回应户数与权重，以及涉及的 `wave`/`census`/`move` 记录键。`balance.strata` 按（业务组, 分层）逐层回读，同号分层不跨组合并。

`incoming.csv` 包含四个业务组，第二组提供不同边界，第三组触发业务拒收，第四组需要核对。另含重复表头、冲突记录、重复回放与错误列数。`ready.csv` 含可以签发的两个组。`moved.csv` 为可签发的迁户样例；`move_conflict.csv`、`move_missing_target.csv`、`move_replay.csv` 分别触发迁户冲突、缺目标层与重复挪户阻断。
