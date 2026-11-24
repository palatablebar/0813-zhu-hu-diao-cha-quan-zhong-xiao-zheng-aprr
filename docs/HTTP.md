# 阶段接口

`POST /api/stages/<stage>` 接收 `multipart/form-data`。字段 `sample=dirty`、`sample=clean`、`sample=moved`、`sample=moveconflict`、`sample=movemissing`、`sample=movereplay` 或 `file=<CSV>` 之一。阶段为 `intake`、`prepare`、`calculate`、`policy`、`balance`。预览不入库。

`POST /api/runs` 接收同样的输入，执行全批并返回运行报告。`GET /api/runs` 返回最近 50 批。`GET /api/runs/<id>` 查询一批、当前复核状态与 `attempts` 发布尝试记录。

`PATCH /api/runs/<id>` 接收 `revision`、`status` 和 `note`。状态使用 `APPROVED` 或 `HELD`。冲突返回 409，客户端读取新版本后重试。签发被挡时返回 409 `UNRESOLVED_ISSUES`，响应带 `records`（相关记录键）与 `details.blockers`（逐项原因）；批次状态与报告保持不变，失败尝试记入 `attempts`。

`GET /api/runs/<id>/evidence` 下载内含运行清单、行号隔离、逐层迁户台账、业务证据、发布尝试和复核信息的 JSON。
