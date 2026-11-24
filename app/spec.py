COLUMNS = ("stratum", "households", "responded", "target")
KINDS = ("wave", "census")
PROJECT = {
    "name": "住户调查权重校正",
    "actor": "抽样调查数据员",
    "stages": [
        ("intake", "样例采信"),
        ("prepare", "分层编排"),
        ("calculate", "权重调整"),
        ("policy", "覆盖检查"),
        ("balance", "运行对账"),
    ],
    "chart": "覆盖户数",
}
