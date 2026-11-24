# 住户调查权重校正

抽样调查数据员可在工作台上传来源 CSV，对照规则判断差异，签发合格批次或记录暂缓意见。

按分层应答率做无应答权重调整并核对人口覆盖。迁户更正按最新分层口径重算权重，保留迁户前后的逐层户数与权重台账；原层应答记录留作追责。

## 启动

```sh
docker compose up --build -d --wait
```

打开 <http://localhost:18307>。页面预览带异常样例。选中阶段查看计算证据，选择可签发样例并执行批次，然后提交复核意见。

## 核验

```sh
docker compose exec -T app pytest -q
```

[输入字段](docs/DATA-DICTIONARY.md) · [阶段接口](docs/HTTP.md) · [操作步骤](docs/OPERATIONS.md) · [规则与测试](docs/DEPTH.md)
