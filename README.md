# SmartValve AI Twin

ValveDNA 单阀状态诊断与 WNTR 管网后果计算组成的双层数字孪生工程平台。

软件版本 `0.4.0`；透明规则模型 `valvedna-rules-0.3.0`。两者刻意分开：安全、审计和
界面升级不冒充算法重新训练。

## 当前定位

这是一个经过真实公开台架、自动测试、安全扫描和正式容器验收的单节点工业工程试点，适合
演示、课题合作和接入一款企业阀门做联合校准。它不是已经通过伟隆产品标定、现场高可用或
安全认证的生产系统。

当前闭环包括：

- S0 可复现阀门/执行器故障注入、ValveDNA 基线比较与透明规则；
- S1 Cranfield 真实机电执行器 180 组分组验证及实测机电动画；
- S1 SKAB 真实水循环异常检测；
- WNTR 1.5 压力驱动管网后果计算；
- FastAPI 版本化接口和受控执行的 Streamlit 工业控制台；
- 完整基线/当前载荷、操作员与相关 ID 的不可变 SHA-256 链式审计；
- PDF 报告、Prometheus 文本指标、真实健康探针和公开数据 SHA-256 校验；
- 依赖哈希锁定、无 shell 的 Chainguard Python 3.14 非 root/只读容器、密钥门禁和 CI 骨架；
- SPDX 2.3 SBOM、原始漏洞报告与逐项 OpenVEX 可达性复核证据。

## 快速启动

### 本地开发

```bash
make install
make data
make lint
make test
make demo
```

控制台：`http://127.0.0.1:8501`
OpenAPI：`http://127.0.0.1:8000/docs`

### 正式单节点容器

```bash
cp .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(48))"
# 把生成值写入 .env 的 SMARTVALVE_API_KEY
make data
docker compose build
docker compose up -d
docker compose ps
```

Compose 仅绑定本机回环地址。远程试点必须另外配置经过评审的 TLS 反向代理或 VPN。详见
[部署说明](docs/deployment.md)。

## 使用流程

1. 在侧栏选择 S0 仿真或 S1 Cranfield 工况。
2. 点击“执行并固化诊断”。仅修改参数不会调用 API 或写入审计库。
3. 查看数据驱动动画、ValveDNA 证据、维护建议和 WNTR 管网影响。
4. 在“三源验证”查看成功指标与最弱工况；该页使用只读样本接口，不新增审计记录。
5. 导出 Markdown、JSON 或正式 PDF，并在“系统与审计”校验哈希链。

## 证据阶梯

| 等级 | 数据源 | 状态 | 能证明 | 不能证明 |
|---|---|---|---|---|
| S0 | 确定性仿真 | 已完成 | 机制、闭环、回归与边界拒识 | 实物准确率 |
| S1 | Cranfield 真实执行器 | 已完成 | 电流—位置迁移与未见负载开发验证 | 水阀/伟隆性能 |
| S1 | SKAB 真实水循环 | 已完成 | 物理水循环过程异常可检测 | 单阀机械根因 |
| S2 | 200 元自有样机 | CSV 接口就绪，硬件待建 | 自有采集链和重复性 | 工业压力等级 |
| S3 | 企业阀门 | 仅候选接口 | 型号标定、Kv/Cv、现场价值 | 未获得数据前不作结论 |

企业 CSV 的来源由操作员声明，因此只能标为 S3 候选，不能自动升级为已验证 S3。

## 评测结果

| 评测 | 参数组合 / 唯一轨迹 | 结果 | 边界 |
|---|---:|---:|---|
| S0 分组回归 | 3,000 / 2,100 | 宏 F1 0.953 | 开发后回归，不是纯净终测 |
| S0 锁定挑战 | 1,500 / 1,050 | 宏 F1 0.874；正常误报 0% | 规则冻结后的仿真挑战 |
| S1 Cranfield | 180 次真实试验 | 未见负载开发 CV 准确率 87.2%，宏 F1 0.874 | 单一公开执行器台架 |
| S1 最弱工况 | 30 次真实试验 | trap / -40 kgf 准确率 33.3% | 域迁移失败被完整披露 |

所谓“拒识 1.0”只覆盖越界供电电压，不是通用 OOD 能力。规则输出的 `confidence` 字段保留
兼容性，但其语义是启发式证据强度，不是校准概率。

## API 示例

```bash
curl -X POST http://127.0.0.1:8000/v1/diagnostics/simulation \
  -H "X-API-Key: $SMARTVALVE_API_KEY" \
  -H "X-Operator-ID: demo-operator" \
  -H 'Content-Type: application/json' \
  -d '{"asset_id":"DEMO-QD-007","fault_type":"stiction","severity":0.75}'
```

主要接口：

```text
GET  /health/live
GET  /health/ready
GET  /metrics
POST /v1/diagnostics/simulation
POST /v1/diagnostics/cranfield
POST /v1/diagnostics/csv
GET  /v1/validation/benchmark?profile=challenge
GET  /v1/validation/cranfield
GET  /v1/validation/cranfield/sample  # 只读回放，不写审计
GET  /v1/validation/skab
GET  /v1/audit/verify
GET  /v1/runs/{id}/report.pdf
```

## 质量命令

```bash
make lint
make test
make security
make benchmark-cranfield
make docker-build
make sbom
make image-scan
```

公开原始数据不进入仓库；`make data` 只允许从 HTTPS 白名单下载并写入 URL、许可、大小与
SHA-256 清单。

镜像扫描保留原始命中，并通过 `security/openvex.json` 对当前镜像和 CPython 组件逐项说明
不可达路径；`make image-scan` 不使用笼统的“忽略所有未修复项”规则。

## 文档

- [确定版项目计划](SmartValve_AI_Twin_Project_Plan.md)
- [0.4.0 验收报告](docs/acceptance_report_0.4.0.md)
- [系统架构](docs/architecture.md)
- [部署与扩展边界](docs/deployment.md)
- [限制与声明政策](docs/limitations.md)
- [实验迭代记录](docs/benchmark_history.md)
- [安全策略](SECURITY.md)

License: Apache-2.0。外部数据仍遵循各自许可，不能因为本仓库使用 Apache-2.0 就改变其许可。
