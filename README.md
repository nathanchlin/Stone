# Stone — A 股个人投研辅助平台

> 一个本地化、可配置、可扩展的 A 股投研辅助工具，为 T+1 个人投资者设计。

## ⚠️ 法律声明（必读）

本项目是**个人投研辅助工具**，**不是**：

- ❌ 荐股软件 / 投资顾问服务
- ❌ 自动交易系统
- ❌ 股价预测工具

项目**不做**以下事情：

| 行为 | 法律风险 |
|---|---|
| 提供具体证券投资建议（荐股） | 违反《证券法》第 121 条 |
| 自动接入券商交易系统下单 | 违反《证券法》第 122 条 |
| 预测股价涨跌 | LLM 能力边界外 |

项目**做**以下事情：

| 模块 | 性质 |
|---|---|
| 候选股名单（按用户预设条件筛选） | 合法工具 |
| 多因子评分（按用户预设权重计算） | 合法工具 |
| 仓位计算（按用户预设规则做算术） | 合法工具 |
| 止损/止盈提醒（监控用户预设价格） | 合法工具 |
| 策略历史回测 | 合法工具 |

**用户必须自行决策**：是否买入、买多少、何时卖出。本项目是放大判断力的工具，**不替代用户判断**。

## 项目状态

🚧 **骨架已可运行** — 数据层、选股流水线、4 种报表输出、CLI 骨架、integration/e2e 测试已经落地；当前仍属于本地开发版，尚未做真实全市场数据验证和生产化调优。

详见：[选股子系统设计文档](docs/superpowers/specs/2026-06-14-a-stock-selector-design.md)

## 整体规划

| Phase | 子系统 | 状态 |
|---|---|---|
| 1 | 数据层（akshare 抓取 + parquet 缓存 + 股池维护） | 设计中 |
| 2 | 选股分析（多因子 + YAML 策略 + 4 种格式报表） | 设计中 |
| 3 | 盯盘与信号提醒 | 未启动 |
| 4 | 策略回测 | 未启动 |
| 5 | 持仓管理与分析 | 未启动 |

## 技术栈

- **Python 3.12** + uv（包管理）
- **pandas / numpy / pyarrow**（数据 + 缓存）
- **akshare**（数据源）
- **pydantic / pyyaml**（配置校验）
- **mplfinance / plotly**（K 线图）
- **pytest**（测试，覆盖率 ≥ 80%）

## 使用场景（设计完成后）

```bash
# 每日 16:00 自动跑（launchd 触发）
stone daily

# 手动选股
stone select --strategy band_trend_v1

# 更新数据
stone update
```

## 用户画像

- T+1 个人投资者
- 使用华泰证券涨乐财富通做手动交易
- 波段趋势风格（持仓几天到几周）
- 全市场覆盖（主板 + 创业板 + 科创板 + 北交所）

## 文档

- [选股子系统设计文档](docs/superpowers/specs/2026-06-14-a-stock-selector-design.md)
- [实现与部署说明](docs/superpowers/plans/SETUP.md)

## Quickstart

```bash
# Install
brew install uv
git clone https://github.com/nathanchlin/Stone.git
cd Stone
uv sync --all-extras

# Configure your capital (private — not committed)
cp config/position_rules.example.yaml config/personal/position_rules.yaml
$EDITOR config/personal/position_rules.yaml

# First run: backfill historical data (30-60 min)
uv run python main.py update --backfill 2024-01-01 2026-06-14

# Run selection
uv run python main.py select --strategy band_trend_v1
# -> reports/2026-06-14_band_trend_v1.{xlsx,html,md,json}
```

## Development

```bash
uv run pytest -v                  # run tests
uv run pytest --cov=stone         # coverage report
uv run ruff check .               # lint
uv run mypy stone/                # type check
```

See [SETUP.md](docs/superpowers/plans/SETUP.md) for daily scheduling.

## License

待定（建议 MIT）
