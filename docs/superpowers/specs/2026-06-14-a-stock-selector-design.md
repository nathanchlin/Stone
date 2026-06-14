# A 股个人投研辅助平台 — 选股子系统设计文档

| 字段 | 值 |
|---|---|
| 文档日期 | 2026-06-14 |
| 项目代号 | `stone` |
| 当前阶段 | Brainstorming → Design（待用户审查） |
| 子系统范围 | 选股分析（首版 Phase 1+2）+ 共享数据层（地基） |
| 后续子系统 | 盯盘提醒 / 策略回测 / 持仓管理（各自走完整 brainstorming 流程） |

---

## 0. 关键决策摘要

| 维度 | 决策 |
|---|---|
| 项目定位 | **个人投研辅助工具**（非荐股软件、非自动交易） |
| 用户投资风格 | 波段趋势（持仓几天到几周） |
| 选股逻辑 | 综合多因子（技术面 + 基本面过滤 + 资金 + 题材） |
| 市场范围 | 全市场（主板 + 创业板 + 科创板 + 北交所，约 5000+ 只） |
| 运行时机 | 收盘后批量（每日 16:00 launchd 触发） |
| 策略配置 | YAML 可配置（pydantic 校验） |
| 打分方式 | 加权平均（按股票自身历史分位归一化） |
| 输出 | Top 30 候选股 × 4 种格式（Excel/HTML+K线/Markdown/JSON） |
| 数据源 | akshare（首版，免费）+ tushare pro（可选升级） |
| 技术栈 | Python 3.12 + uv + pandas + pyarrow + pydantic |
| 测试 | TDD 强制，覆盖率 ≥ 80% |

---

## 1. 项目定位与合规边界（必读）

### 1.1 项目目标

为 T+1 个人投资者（华泰证券涨乐财富通用户）提供一个 **本地化、可配置、可扩展** 的 A 股投研辅助平台。系统生成 **候选股名单 + 评分 + 入选理由 + 仓位计算结果**，**用户自行决策** 是否买入、买多少、何时卖出。

### 1.2 法律边界（红线，无商量余地）

| 行为 | 法律风险 | 本项目是否做 |
|---|---|---|
| 提供具体证券投资建议（荐股） | 违反《证券法》第 121 条 + 《证券投资顾问业务暂行规定》 | **不做** |
| 提供具体资金分配建议 | 投顾业务延伸违规 | **不做**（仅做用户预设规则的算术） |
| 自动接入券商交易系统下单 | 违反《证券法》第 122 条，涨乐财富通无开放 API | **不做** |
| 预测股价涨跌 | LLM 能力边界外，号称能做的均为骗局 | **不做** |

### 1.3 本项目合法做的事

| 模块 | 性质 |
|---|---|
| 候选股名单（按用户预设条件筛选） | 合法工具 |
| 多因子评分（按用户预设权重计算） | 合法工具 |
| 仓位计算（按用户预设规则做算术） | 合法工具 |
| 止损/止盈提醒（监控用户预设的价格触发） | 合法工具 |
| 策略历史回测（验证策略在历史数据上的表现） | 合法工具 |

### 1.4 不在首版范围内

- 盯盘与实时信号推送（Phase 3 子系统）
- 策略回测引擎（Phase 4 子系统）
- 持仓管理与盈亏分析（Phase 5 子系统）
- 任何形式的自动下单

---

## 2. 需求摘要（Brainstorming 收集）

通过 7 轮澄清问题收集的需求：

| # | 维度 | 用户选择 |
|---|---|---|
| 1 | 投资风格 | 波段趋势 |
| 2 | 选股逻辑 | 综合多因子 |
| 3 | 市场范围 | 全市场（含科创板、北交所） |
| 4 | 运行时机 | 收盘后批量扫描 |
| 5 | 策略可配置性 | YAML 可配置 |
| 6 | 打分方式 | 加权平均（推荐） |
| 7 | 输出形式 | Excel + HTML+K线 + Markdown + JSON（全选） |
| 7b | 名单数量 | Top 30 |
| - | 仓位计算 | 加 position_sizing 子模块（按预设规则做算术） |

---

## 3. 架构总览

### 3.1 分层与依赖（单向，从下到上）

```
┌─────────────────────────────────────────────────────────┐
│  CLI / Jupyter 入口                                     │
│  main.py · notebooks/                                   │
└────────────────────────┬────────────────────────────────┘
                         │ 调用
┌────────────────────────▼────────────────────────────────┐
│  选股流水线 (selector/engine.py)                        │
│  load_config → fetch_data → compute_factors → score →   │
│  filter → rank → constraint_solve → position_size → emit│
└────────────────────────┬────────────────────────────────┘
                         │ 使用
┌────────────────────────┼────────────────┬───────────────┐
│  selector/             │  reporters/    │  config/      │
│  · factors/ (因子库)    │  · Excel       │  · YAML 策略  │
│  · strategy.py (YAML)  │  · HTML+K线    │  · 股池规则    │
│  · scoring.py (加权)   │  · Markdown    │  · 仓位规则    │
│  · position_sizing.py  │  · JSON        │               │
│  · constraints.py      │                │               │
└────────────────────────┴────────────────┴───────────────┘
                         │ 依赖
┌────────────────────────▼────────────────────────────────┐
│  数据层 (data/) — 后续 3 个子系统共用的地基              │
│  · fetchers/akshare_fetcher.py  (抓取 + 限速 + 重试)    │
│  · cache/parquet_store.py        (按 date×code 分区)    │
│  · universe.py                   (全市场股池 + ST过滤)  │
│  · incremental.py                (T 日增量更新)         │
│  · quality.py                    (数据完整性自检)       │
└─────────────────────────────────────────────────────────┘
```

### 3.2 核心设计原则

1. **单向依赖**：上层只调用下层，不反向；selector 不感知 reporters
2. **数据层是地基**：盯盘/回测/持仓子系统后续都从 `data/` 取数，接口必须先稳定
3. **因子是「数据 → 标量分」的纯函数**：无副作用、可测试、可组合
4. **配置即数据**：YAML 描述策略，代码只解析不硬编码
5. **仓位计算是算术工具，不是建议**：用户预设规则，项目做计算

### 3.3 文件清单（首版）

```
stone/
├── data/
│   ├── __init__.py
│   ├── fetchers/
│   │   ├── __init__.py
│   │   ├── base.py              # 抽象接口（Protocol）
│   │   ├── akshare_fetcher.py   # 实现
│   │   ├── _rate_limiter.py     # 令牌桶限速
│   │   └── _retry.py            # tenacity 装饰器
│   ├── cache/
│   │   ├── __init__.py
│   │   └── parquet_store.py     # parquet 读写
│   ├── universe.py              # 股池维护 + 规则过滤
│   ├── incremental.py           # 每日增量更新
│   └── quality.py               # 数据质量检查
├── selector/
│   ├── __init__.py
│   ├── factors/
│   │   ├── __init__.py          # 注册表 REGISTRY
│   │   ├── base.py              # Factor 抽象基类 + FactorContext
│   │   ├── normalize.py         # 归一化（自身历史分位）
│   │   ├── technical.py         # 10 个技术因子
│   │   ├── fundamental.py       # 3 个基本面因子
│   │   ├── moneyflow.py         # 2 个资金面因子
│   │   └── theme.py             # 1 个题材因子
│   ├── strategy.py              # YAML 解析 + pydantic 校验
│   ├── scoring.py               # 加权打分引擎
│   ├── constraints.py           # 行业分散约束
│   ├── position_sizing.py       # 仓位计算（按规则算术）
│   └── engine.py                # 主流水线
├── reporters/
│   ├── __init__.py
│   ├── excel.py                 # openpyxl + xlsxwriter
│   ├── html.py                  # jinja2 + mplfinance
│   ├── markdown.py
│   ├── json_reporter.py
│   └── charts.py                # K 线图生成
├── config/
│   ├── strategies/
│   │   ├── band_trend_v1.yaml          # 默认策略
│   │   ├── breakout_strong.yaml        # 激进突破
│   │   └── value_with_catalyst.yaml    # 保守价值
│   ├── universe_rules.yaml             # 股池过滤规则
│   ├── position_rules.example.yaml     # 仓位规则模板（入库）
│   └── personal/                       # 个人配置（gitignore）
│       └── position_rules.yaml         # 你的真实资金配置
├── notebooks/
│   └── 01_factor_explore.ipynb
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── e2e/
│   ├── fixtures/
│   └── helpers/
├── data_cache/                  # parquet 缓存（gitignore）
├── reports/                     # 输出报表（gitignore）
├── logs/                        # 运行日志（gitignore）
├── docs/
│   └── superpowers/specs/       # 设计文档
├── pyproject.toml
├── .gitignore
├── .python-version
└── README.md
```

### 3.4 依赖清单（pyproject.toml）

| 类别 | 包 | 用途 |
|---|---|---|
| 数据 | akshare | 行情/财务/资金流 |
| 数据 | pandas / numpy | 矢量化计算 |
| 缓存 | pyarrow | parquet 读写 |
| 配置 | pyyaml / pydantic | YAML 解析 + schema 校验 |
| 指标 | pandas-ta | 技术指标（纯 Python，无 C 依赖） |
| 指标 | ta-lib（可选） | 高性能指标，需 `brew install ta-lib` |
| 可视化 | mplfinance / plotly | K 线图 |
| 报表 | openpyxl / xlsxwriter / jinja2 | Excel / HTML 模板 |
| 网络 | tenacity / tqdm | 重试 / 进度条 |
| 开发 | pytest / pytest-cov | 测试 + 覆盖率 |
| 开发 | ruff / mypy | lint + 类型检查 |
| 开发 | ipykernel / jupyter | notebook |

---

## 4. 数据层

### 4.1 Fetcher 接口（`data/fetchers/base.py`）

抽象基类（Protocol），未来切换数据源只需新增实现：

```python
class DataFetcher(Protocol):
    def list_universe(self, date: date) -> pd.DataFrame:
        """返回当日全市场股票清单 (code, name, board, list_date, is_st, delisted)"""

    def get_daily_kline(
        self, code: str, start: date, end: date, adjust: str = "qfq"
    ) -> pd.DataFrame:
        """返回单只股票的日 OHLCV，前复权。列：date, open, high, low, close, volume, amount"""

    def get_daily_kline_batch(
        self, codes: list[str], start: date, end: date, adjust: str = "qfq"
    ) -> dict[str, pd.DataFrame]:
        """批量抓取（akshare 无原生批量，循环实现）"""

    def get_basic_financial(self, code: str) -> pd.DataFrame:
        """PE/PB/ROE/营收增长/资产负债率 等基本面字段"""

    def get_money_flow(self, code: str, days: int = 30) -> pd.DataFrame:
        """主力资金净流入、北向持仓变化"""

    def get_industry_mapping(self) -> dict[str, str]:
        """股票代码 → 申万行业"""
```

### 4.2 akshare 实现要点

- **限速**：令牌桶 ≤ 3 req/s（akshare 风控阈值，避免被东方财富封 IP）
- **重试**：`tenacity.retry`（指数退避，3 次），重试条件：`ConnectionError / TimeoutError / JSONDecodeError`
- **进度**：`tqdm` 显示进度，5000 只约 30-40 分钟
- **失败收集**：异常股票记入 `data_cache/_failed_codes.json`，不中断流水线

### 4.3 缓存分区策略（`data/cache/parquet_store.py`）

**关键决策：按「日期」分区**（不按股票）

| 方案 | 增量更新 | 选股扫描读取 | 选择 |
|---|---|---|---|
| **按日期** `cache/kline/date=2026-06-13/data.parquet` | 每日追加一个文件 | 一次读完当日全市场 | ✅ |
| 按股票 `cache/kline/code=000001/data.parquet` | 遍历 5000 文件 | 全市场扫描慢 | ❌ |

```
data_cache/
├── kline/
│   ├── date=2024-01-02/data.parquet    # 当日全市场 OHLCV
│   ├── date=2024-01-03/data.parquet
│   └── ...
├── financial/
│   └── date=2026-06-13/data.parquet    # 季度更新
├── moneyflow/
│   └── date=2026-06-13/data.parquet
└── universe/
    └── date=2026-06-13/data.parquet
```

**接口**：

```python
class ParquetStore:
    def write_kline(self, date: date, df: pd.DataFrame) -> None: ...
    def read_kline(self, date: date) -> pd.DataFrame: ...
    def read_kline_range(self, start: date, end: date) -> pd.DataFrame: ...
    def list_cached_dates(self, kind: str) -> list[date]: ...
    def get_missing_dates(self, kind: str, expected: list[date]) -> list[date]: ...
```

### 4.4 增量更新（`data/incremental.py`）

每日收盘后跑：

```python
def update_daily(target_date: date) -> UpdateReport:
    """
    1. 抓取当日 universe（含新上市/退市/ST 状态变更）
    2. 对比 cache，找出 missing_dates（用交易日历跳过停牌日）
    3. 对每个 missing_date:
       a. 抓取该日全部股票的 kline/financial/moneyflow
       b. 写入 parquet
       c. 失败的日期记入 failed_dates.json
    4. 返回 UpdateReport（成功N天、失败M天、跳过K天）
    """
```

- **交易日历**：用 `ak.tool_trade_date_hist_sina()` 获取历年交易日
- **容错**：单日失败不中断，提供 `python main.py update --retry-failed` 重试

### 4.5 股池维护（`data/universe.py`）

```python
def get_active_universe(date: date, rules: UniverseRules) -> list[str]:
    """
    剔除 ST/*ST、上市<60日、当日停牌、退市风险股
    可选：剔除北交所、最小市值过滤
    """
```

**UniverseRules YAML**：

```yaml
# config/universe_rules.yaml
exclude_st: true
exclude_new_listing_days: 60
exclude_paused: true
exclude_delisting_risk: true
exclude_beijing_exchange: false    # 全市场保留
min_market_cap: 5_000_000_000     # 可选：剔除 < 50 亿的小盘股
```

### 4.6 数据质量检查（`data/quality.py`）

每次抓取后跑：

```python
def assert_kline_quality(df: pd.DataFrame, expected_date: date):
    assert len(df) > 0, "空数据"
    assert df["low"].le(df["high"]).all(), "low > high"
    assert df["low"].le(df[["open", "close"]]).min().all(), "low > min(open,close)"
    assert df[["open", "high", "low", "close"]].notna().all().all(), "关键字段有 NaN"
    assert (df["volume"] >= 0).all(), "volume < 0"
```

触发任一异常 → 该日数据进 `_quarantine/` 隔离目录，等手动修复。

### 4.7 容量估算

- 5000 只 × 1 日 kline ≈ 320 KB/日
- 5 年历史 ≈ 1200 个交易日 ≈ 400 MB（parquet 压缩后约 80-100 MB）
- 加财务 + 资金流 ≈ 再加 50 MB
- **总计**：5 年数据本地约 **~150 MB**

---

## 5. 因子库

### 5.1 抽象基类（`selector/factors/base.py`）

```python
class Factor(ABC):
    """
    输入：单只股票的 FactorContext（OHLCV + 财务 + 资金流）
    输出：原始值，由框架归一化为 0-100 标量分
    无副作用、可测试、可参数化
    """

    name: str                      # 唯一标识，YAML 引用
    category: FactorCategory       # technical/fundamental/moneyflow/theme
    higher_is_better: bool = True

    @abstractmethod
    def compute(self, ctx: FactorContext) -> float: ...

    @abstractmethod
    def get_params(self) -> dict: ...

class FactorContext:
    """传给因子的上下文，避免长参数列表"""
    code: str
    name: str
    industry: str
    today: date
    kline: pd.DataFrame            # OHLCV, ≥250 日
    financial: pd.DataFrame        # 最近 4 季度财报
    moneyflow: pd.DataFrame        # 30 日资金流
```

### 5.2 归一化策略（`selector/factors/normalize.py`）

**关键决策：在「该股自身历史」上做分位归一化，不做横截面归一化**

理由：「该股 PE 处于 1 年最低 10%」比「PE 处于全市场最低 10%」更有意义，避免当日极端值影响。

```python
class Normalizer:
    def normalize(self, raw_value: float, history: pd.Series) -> float:
        """返回 raw_value 在最近 N 日历史中的分位（0-100）"""
```

### 5.3 内置因子清单（首版 16 个）

#### 技术面（10 个，打分型）

| 因子名 | 含义 | 参数 |
|---|---|---|
| `ma_bullish_alignment` | 5/10/20/60 均线多头排列 | periods: [5,10,20,60] |
| `ma5_above_ma20` | 5 日线在 20 日线上方 | — |
| `price_above_ma60` | 收盘价在 60 日线上方 | — |
| `breakout_20d_high` | 突破 20 日新高 | window: 20 |
| `macd_golden_cross` | MACD 金叉且在零轴上方 | lookback: 5 |
| `kdj_golden_cross` | KDJ 金叉 | lookback: 3 |
| `rsi_in_healthy_zone` | RSI 在 40-70 | range: [40, 70] |
| `volume_ratio` | 量比 = 今日量 / 5日均量 | avg_window: 5 |
| `turnover_rate` | 换手率合理（1%-10%） | range: [1, 10] |
| `distance_to_52w_high` | 距 52 周高点的距离 | threshold: -0.15 |

#### 基本面（3 个，**过滤型** — 低于阈值直接淘汰）

| 因子名 | 含义 | 阈值 |
|---|---|---|
| `pe_in_industry_percentile` | PE 在同行业中分位 | ≤ 0.7 |
| `roe_above_15` | ROE > 15% | 4 季度滚动 |
| `revenue_growth_positive` | 营收同比正增长 | 最近 2 季度 |

#### 资金面（2 个，打分型）

| 因子名 | 含义 |
|---|---|
| `main_money_inflow_5d` | 主力资金 5 日累计净流入 |
| `northbound_inflow_20d` | 北向 20 日净买入 |

#### 题材面（1 个）

| 因子名 | 含义 |
|---|---|
| `industry_momentum_5d` | 所属行业 5 日涨幅在全行业的分位 |

### 5.4 注册机制

```python
@register_factor
class MaBullishAlignment(Factor):
    name = "ma_bullish_alignment"
    category = FactorCategory.TECHNICAL

    def __init__(self, periods: list[int] = (5, 10, 20, 60)):
        self.periods = periods
    ...

REGISTRY: dict[str, type[Factor]] = {}
```

新增因子工作流：
1. 在对应分类文件加 `@register_factor` 类
2. 写单元测试
3. YAML 策略里引用 name
4. 完成（不需要改 scoring / engine / strategy loader）

### 5.5 性能预算

- 5000 只 × 16 因子 = 80000 次 compute 调用
- 每次约 1-5 ms（pandas 矢量化）
- **总耗时 1-3 分钟**（每日一次，可接受）
- 未来慢可上 `ProcessPoolExecutor(workers=4)` 并行

---

## 6. YAML Schema

### 6.1 完整策略示例

```yaml
# config/strategies/band_trend_v1.yaml
meta:
  name: "波段趋势 v1"
  version: "1.0.0"
  description: "均线多头 + MACD 金叉 + 量能放大 + 基本面过滤"
  created_at: 2026-06-14

universe:
  rules_file: config/universe_rules.yaml
  history_days: 250

# 第一层：硬过滤（任一不过即剔除）
filters:
  - factor: roe_above_15
    criterion: "value >= 1.0"
  - factor: revenue_growth_positive
    criterion: "value >= 1.0"
  - factor: pe_in_industry_percentile
    criterion: "value <= 0.7"
  - factor: turnover_rate
    criterion: "value >= 1.0"

# 第二层：加权打分
scoring:
  method: weighted_average
  factors:
    - factor: ma_bullish_alignment
      weight: 0.20
      params: { periods: [5, 10, 20, 60] }
    - factor: breakout_20d_high
      weight: 0.15
    - factor: macd_golden_cross
      weight: 0.15
    - factor: kdj_golden_cross
      weight: 0.10
    - factor: rsi_in_healthy_zone
      weight: 0.05
      params: { range: [40, 70] }
    - factor: volume_ratio
      weight: 0.15
      params: { avg_window: 5 }
    - factor: distance_to_52w_high
      weight: 0.05
    - factor: main_money_inflow_5d
      weight: 0.10
    - factor: northbound_inflow_20d
      weight: 0.05
  # 权重总和必须 = 1.0（schema 强制校验）

# 第三层：输出控制
output:
  top_n: 30
  min_score: 60
  sort_by: score
  sort_desc: true

# 第四层：板块分散约束
constraints:
  max_per_industry: 5
  max_per_theme: 3
```

### 6.2 pydantic 校验（`selector/strategy.py`）

```python
class Meta(BaseModel):
    name: str
    version: str
    description: str = ""
    created_at: date

class FilterRule(BaseModel):
    factor: str
    params: dict = {}
    criterion: str

    @field_validator("factor")
    def must_exist_in_registry(cls, v): ...

    @field_validator("criterion")
    def must_be_safe_expr(cls, v): ...

class ScoringFactor(BaseModel):
    factor: str
    weight: float = Field(ge=0, le=1)
    params: dict = {}

class Scoring(BaseModel):
    method: Literal["weighted_average"] = "weighted_average"
    factors: list[ScoringFactor]

    @model_validator(mode="after")
    def weights_must_sum_to_one(self):
        total = sum(f.weight for f in self.factors)
        assert abs(total - 1.0) < 0.001, f"权重总和必须 = 1.0，当前 = {total}"
        return self

class Strategy(BaseModel):
    meta: Meta
    universe: UniverseConfig
    filters: list[FilterRule] = []
    scoring: Scoring
    output: OutputConfig
    constraints: Constraints = Constraints()
```

### 6.3 安全表达式（防注入）

criterion 是字符串，**不用 `eval()`**，用 `ast.parse` + 白名单节点：

```python
ALLOWED_NODES = (
    ast.Compare, ast.BoolOp, ast.Name, ast.Constant,
    ast.And, ast.Or,
    ast.GtE, ast.LtE, ast.Gt, ast.Lt, ast.Eq,
)

def safe_eval_criterion(expr: str, value: float) -> bool:
    tree = ast.parse(expr, mode="eval")
    for node in ast.walk(tree):
        if not isinstance(node, ALLOWED_NODES):
            raise ValueError(f"非法表达式: {expr}")
    return eval(compile(tree, "<strategy>", "eval"),
                {"__builtins__": {}}, {"value": value})
```

### 6.4 默认交付策略（3 套）

| 文件 | 适用场景 | 风格 |
|---|---|---|
| `band_trend_v1.yaml` | 主力策略 | 趋势 + 量能 |
| `breakout_strong.yaml` | 强势突破，更激进 | 高量比 + 突破 + 主力流入 |
| `value_with_catalyst.yaml` | 价值股等催化，更保守 | 低 PE + 高 ROE + 北向入场 |

### 6.5 多策略与版本管理

- `config/strategies/` 目录可放任意多个 YAML
- CLI 选择：`python main.py select --strategy band_trend_v1`
- 批量跑：`python main.py select --all-strategies`
- `meta.version` 用于追踪；选股结果文件名带版本号

---

## 7. 打分引擎与流水线

### 7.1 打分引擎（`selector/scoring.py`）

```python
class ScoringEngine:
    def __init__(self, scoring_config: Scoring, history_window: int = 250):
        self.factors = [
            (REGISTRY[f.factor](**f.params), f.weight)
            for f in scoring_config.factors
        ]

    def score_one(self, ctx: FactorContext) -> StockScore:
        raw_values, normalized_values = {}, {}
        for factor, weight in self.factors:
            try:
                raw = factor.compute(ctx)
                norm = self._normalize(raw, ctx, factor)
                raw_values[factor.name] = raw
                normalized_values[factor.name] = norm
            except FactorError:
                raw_values[factor.name] = None
                normalized_values[factor.name] = 0.0
                # 单因子失败：0 分但不中断

        final = sum(normalized_values[f.name] * w for f, w in self.factors)
        return StockScore(code=ctx.code, ..., score=final)
```

### 7.2 选股流水线（`selector/engine.py`）

```python
class SelectionEngine:
    def __init__(self, strategy, store, fetcher):
        self.strategy = strategy
        self.store = store
        self.fetcher = fetcher
        self.scorer = ScoringEngine(strategy.scoring)
        self.filters = self._build_filters(strategy.filters)
        self.constraint_solver = ConstraintSolver(strategy.constraints)
        self.position_sizer = PositionSizer(...)  # 可选

    def run(self, target_date: date) -> SelectionResult:
        # ① 加载股池
        universe = self._load_universe(target_date)
        # ② 并行计算因子 + 评分
        scores = self._compute_scores_parallel(universe, target_date)
        # ③ 应用硬过滤
        passed = [s for s in scores if self._passes_all_filters(s)]
        # ④ 排序
        ranked = sorted(passed, key=lambda s: s.score, reverse=True)
        # ⑤ min_score 阈值
        above_threshold = [s for s in ranked if s.score >= self.strategy.output.min_score]
        # ⑥ 行业分散约束
        constrained = self.constraint_solver.apply(above_threshold)
        # ⑦ Top N
        top_n = constrained[: self.strategy.output.top_n]
        # ⑧ 仓位计算（可选）
        if self.position_sizer:
            top_n = self.position_sizer.allocate(top_n)
        return SelectionResult(...)
```

### 7.3 数据流

```
python main.py select --strategy band_trend_v1 --date 2026-06-14
  ↓
① load_strategy(YAML) → Strategy（pydantic 校验通过）
  ↓
② _load_universe → ParquetStore.read("universe") + rules 过滤 → 4800 只
  ↓
③ _compute_scores_parallel (ProcessPoolExecutor, 4 workers, tqdm 进度)
   每 worker 独立 store + scorer，单股 10s 超时
   → 4800 个 StockScore，耗时约 2-3 分钟
  ↓
④ _passes_all_filters → 通过 3500 只
⑤ sort by score desc
⑥ score >= 60 → 80 只
⑦ constraint_solver (max_per_industry=5) → 40 只
⑧ final[:30] → Top 30
  ↓
reporters.render_all() → reports/2026-06-14_band_trend_v1.{xlsx,html,md,json}
```

### 7.4 并行化

```python
def _compute_scores_parallel(self, universe, target_date):
    workers = min(4, os.cpu_count() - 1)
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(_score_single_stock, code, target_date, self.strategy): code
            for code in universe
        }
        scores, failed = [], []
        for future in tqdm(as_completed(futures), total=len(universe), desc="打分中"):
            try:
                result = future.result(timeout=10)
                if result: scores.append(result)
            except TimeoutError:
                failed.append((futures[future], "timeout"))
            except Exception as e:
                failed.append((futures[future], str(e)))
    return scores, failed
```

### 7.5 ConstraintSolver（行业分散）

```python
class ConstraintSolver:
    """贪心算法应用行业/题材分散约束"""
    def apply(self, ranked: list[StockScore]) -> list[StockScore]:
        count = defaultdict(int)
        result = []
        for stock in ranked:  # 已按 score 降序
            if count[stock.industry] < self.config.max_per_industry:
                result.append(stock)
                count[stock.industry] += 1
        return result
```

> **设计权衡**：用贪心而非 ILP——Top 30 规模小，贪心接近最优且实现简单。

### 7.6 容错策略

| 失败类型 | 处理 |
|---|---|
| 单只股票缺数据 | 跳过 + 记入 `failed_codes` |
| 单个因子异常 | 该因子 0 分，其他因子正常算 |
| 单股超时（10s） | 杀进程，记入 failed |
| akshare 限流 | 退避重试（fetcher 层） |
| parquet 损坏 | 数据质量检查拦截，进 `_quarantine/` |

---

## 8. 仓位计算模块（`selector/position_sizing.py`）

### 8.1 法律性质再次明确

**这是「按用户预设规则做算术」的工具，不是「投资建议」**。用户必须先在 YAML 定义规则，项目只做计算。

### 8.2 仓位规则 YAML

```yaml
# config/personal/position_rules.yaml  （gitignore，不入库）
total_capital: 100000
max_total_position: 0.80
max_per_stock: 0.10

allocation_method: score_weighted   # equal_weight / score_weighted / risk_parity / fixed_amount

round_to: 100
min_position: 5000

stop_loss_pct: 0.08                 # 跌 8% 触发观察（仅提醒）
take_profit_pct: 0.20               # 涨 20% 触发观察
```

模板入库为 `config/position_rules.example.yaml`，用户复制到 `config/personal/` 改自己的金额。

### 8.3 计算逻辑（纯算术）

```python
class PositionSizer:
    def allocate(self, picks: list[PickRecord], rules: PositionRules) -> list[PositionPlan]:
        """
        - equal_weight: 总仓位 / N
        - score_weighted: score^1.5 加权
        - risk_parity: 1/σ 加权（σ = 60 日波动率）
        """
```

### 8.4 报表新增列

| 排名 | 代码 | 名称 | 评分 | 建议金额 | 建议股数 | 占总资金 | 止损价(≈) | 止盈价(≈) |
|---|---|---|---|---|---|---|---|---|
| 1 | 600519 | 贵州茅台 | 92.3 | ¥9,800 | 5 | 9.8% | 1674.86 | 2184.60 |

报表底部固定显示：
> ⚠️ 金额为按预设规则的算术计算结果，非投资建议。买卖决策请自行判断。

---

## 9. 输出层

### 9.1 统一数据源（`PickRecord`）

```python
@dataclass
class PickRecord:
    rank: int
    code: str
    name: str
    industry: str
    board: str
    close: float
    change_pct: float
    score: float
    factor_scores: dict[str, float]
    reasons: list[str]               # 自动生成：得分 ≥ 80 的因子
    pe: float | None
    pb: float | None
    market_cap: float
    roe: float | None
    volume_ratio: float
    turnover_rate: float
    kline_60d: pd.DataFrame | None   # HTML 内嵌图用
    # 仓位计算结果（若启用）
    suggested_amount: float | None
    suggested_shares: int | None
    stop_loss_price: float | None
    take_profit_price: float | None
```

### 9.2 Excel（`reporters/excel.py`）

4 个 sheet：

| Sheet | 内容 |
|---|---|
| Top 30 名单（主表） | 排名/代码/名称/行业/收盘/涨跌/评分/PE/PB/市值/ROE/量比/换手/建议金额/入选理由 |
| 因子得分明细 | 排名/代码/名称/总分/各因子分（条件格式：≥80 绿，<40 红） |
| 元信息 | 策略/版本/运行时间/股池漏斗/各步耗时/失败数 |
| 失败股票 | 代码/失败原因 |

**关键技巧**：
- 代码列设为文本格式（避免 `600519` → `6.00519e+06`）
- 评分列加数据条（一眼看出强弱）
- 代码列下方加注释「← 可直接复制到涨乐财富通批量添加自选」

### 9.3 HTML（`reporters/html.py`）

`jinja2` 模板 + `mplfinance` K 线图（base64 PNG 内嵌，单文件可分享）。

```html
<header>策略/日期/Top 30</header>
<section id="summary">漏斗图：4823 → 3512 → 80 → 40 → 30</section>
<section id="picks">
  <table id="picks-table">  <!-- DataTables CDN，可排序搜索分页 -->
    <tr>... 600519 贵州茅台 ... 评分 92.3 ... 📊 按钮</tr>
    <tr class="hidden"><img src="data:image/png;base64,..."></tr>
  </table>
</section>
<section id="failed">失败列表（折叠）</section>
```

K 线图（`reporters/charts.py`）：

```python
def render_kline(kline: pd.DataFrame, code: str, name: str) -> str:
    fig, axes = mpf.plot(
        kline.tail(60), type="candle", style="charles",
        volume=True, mav=(5, 20, 60),
        title=f"{code} {name}",
        returnfig=True, figsize=(10, 6),
    )
    _annotate_signals(axes[0], kline)  # MACD 金叉、突破点等
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=100, bbox_inches="tight")
    return base64.b64encode(buf.getvalue()).decode()
```

**性能**：30 张 K 线图约 30 秒生成。

### 9.4 Markdown（`reporters/markdown.py`）

git 友好、便于版本对比：

```markdown
# 选股报告 - 2026-06-14 - 波段趋势 v1

> 股池: 4823 → 3512 → 80 → 30 · 耗时: 2m47s

## Top 30 候选股
| # | 代码 | 名称 | 行业 | 收盘 | 评分 | 入选理由 |
| 1 | 600519 | 贵州茅台 | 白酒 | 1820.5 | 92.3 | 均线多头 + MACD 金叉 + 主力流入 |

## 行业分布
| 行业 | 数量 | 占比 |

## 因子贡献度
| 因子 | 平均得分 | 命中率 |

## 失败股票
12 只计算失败，详见 logs/
```

### 9.5 JSON（`reporters/json_reporter.py`）

机器可读，给后续子系统（盯盘/回测/持仓）用：

```json
{
  "meta": { "strategy_name": "...", "version": "...", "target_date": "..." },
  "summary": { "universe_size": 4823, "passed_filters": 3512, ... },
  "picks": [{ "rank": 1, "code": "600519", ..., "factor_scores": {...} }],
  "failed": [{ "code": "688999", "reason": "..." }]
}
```

### 9.6 文件命名

```
reports/
├── 2026-06-14_band_trend_v1.{xlsx,html,md,json}
├── 2026-06-13_band_trend_v1.*
├── 2026-06-14_breakout_strong.*    # 同日多策略共存
└── _archive/                        # 超 30 天归档
```

格式：`{YYYY-MM-DD}_{strategy_name}.{ext}`，文件名字典序 = 时间序。

---

## 10. 错误处理与运行环境

### 10.1 akshare 限速

```python
class RateLimiter:
    """令牌桶：≤ 3 req/s"""

class AkshareFetcher(DataFetcher):
    @retry(stop=stop_after_attempt(3),
           wait=wait_exponential(multiplier=1, min=2, max=30),
           retry=retry_if_exception_type((ConnectionError, TimeoutError, json.JSONDecodeError)))
    @rate_limited(max_rate=3)
    def get_daily_kline(self, code, start, end, adjust="qfq"):
        return ak.stock_zh_a_hist(symbol=code, ...)
```

### 10.2 日志

```
logs/
├── select_2026-06-14.log
├── update_2026-06-14.log
└── app.log                        # 全局，滚动 30 天
```

```python
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(f"logs/select_{today}.log", encoding="utf-8"),
    ],
)
```

### 10.3 Python 环境（uv）

不用系统自带 Python 3.9.6（版本老、易污染）。**推荐 uv**（Rust 写的现代包管理器）：

```bash
brew install uv
cd /Users/lindeng/Stone
uv init --python 3.12
uv add akshare pandas numpy pyarrow pyyaml pydantic pandas-ta \
       mplfinance plotly openpyxl xlsxwriter jinja2 tenacity tqdm
uv add --dev pytest pytest-cov ruff mypy ipykernel jupyter

uv run python main.py update
uv run pytest
uv run jupyter lab
```

### 10.4 定时任务（macOS launchd，不用 cron）

每日 16:00 自动跑（避开收盘后高峰）：

```xml
<!-- ~/Library/LaunchAgents/com.stone.daily.plist -->
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple" "-//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>com.stone.daily</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Users/lindeng/Stone/.venv/bin/python</string>
        <string>/Users/lindeng/Stone/main.py</string>
        <string>daily</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key><integer>16</integer>
        <key>Minute</key><integer>0</integer>
    </dict>
    <key>WorkingDirectory</key><string>/Users/lindeng/Stone</string>
</dict>
</plist>
```

```bash
launchctl load ~/Library/LaunchAgents/com.stone.daily.plist
```

> **不用 cron**：macOS 需给 `cron` 授予全磁盘访问权限，易踩坑。launchd 是原生方案。

### 10.5 CLI 入口（`main.py`）

```bash
stone update                                    # 增量更新今日数据
stone update --retry-failed                     # 重试失败日期
stone update --backfill 2024-01-01 2026-06-14   # 回填历史

stone select --strategy band_trend_v1           # 选股（默认今日）
stone select --strategy band_trend_v1 --date 2026-06-13
stone select --all-strategies                   # 跑所有策略

stone daily                                     # = update + select + report

stone list-strategies
stone validate-config config/strategies/band_trend_v1.yaml
```

### 10.6 .gitignore 关键项

```gitignore
# 数据缓存（不入库）
data_cache/
_quarantine/

# 输出报表（默认不入库）
reports/

# 日志
logs/

# Python
.venv/
__pycache__/
*.pyc
.ipynb_checkpoints/

# 敏感（重要！）
.env
config/personal/                  # 含资金金额，绝对不入库
```

---

## 11. 测试策略

按 superpowers test-driven-development 技能 + CLAUDE.md TDD 规则：**测试先行、覆盖率 ≥ 80%**。

### 11.1 测试金字塔

```
            ▲
           / \
          / E2E\        5%   CLI 端到端
         /───────\
        / 集成测试 \     20%   跨模块协作（mock akshare）
       /───────────\
      /   单元测试    \   75%   每个类/函数
     /───────────────\
```

### 11.2 单元测试覆盖

| 模块 | 测试数 | 关键用例 |
|---|---|---|
| 因子（16 个） | 64 | 完美排列 / 下跌 / 历史不足 / 参数 roundtrip |
| 打分引擎 | 12 | 权重和=1 强制 / 评分 ∈ [0,100] / 单因子失败不崩 |
| YAML/配置 | 15 | 未知因子拒绝 / criterion 注入拦截 / 权重和不等于 1 |
| Parquet 存储 | 10 | 写入/读取一致性 / 日期分区正确 |
| Fetcher（mock akshare） | 8 | 重试 / 限速 / 失败收集 |
| 仓位计算 | 10 | equal_weight / max_per_stock cap / round_to_100 |
| ConstraintSolver | 6 | max_per_industry 强制 |

### 11.3 集成测试（mock akshare）

```python
@pytest.fixture
def mock_fetcher(tmp_path):
    store = ParquetStore(base_dir=tmp_path / "cache")
    _seed_test_data(store, universe_size=100, days=250)
    return MockFetcher(store)

class TestEndToEndPipeline:
    def test_full_run_produces_30_picks(self, mock_fetcher): ...
    def test_failed_codes_dont_crash_pipeline(self, mock_fetcher):
        """10% 失败 → 仍能产出结果"""
    def test_all_reporters_run_without_error(self, mock_fetcher, tmp_path): ...
```

### 11.4 E2E 测试

```python
class TestCLI:
    def test_select_command_produces_all_formats(self, tmp_path):
        result = subprocess.run(
            ["uv", "run", "python", "main.py", "select",
             "--strategy", "band_trend_v1", "--date", "2026-06-14"],
            capture_output=True, timeout=120,
        )
        assert result.returncode == 0
        assert (tmp_path / "reports/2026-06-14_band_trend_v1.xlsx").exists()
        # ... html/md/json
```

### 11.5 测试数据策略

```
tests/
├── fixtures/
│   ├── kline/
│   │   ├── uptrend_250d.parquet
│   │   ├── downtrend_250d.parquet
│   │   ├── volatile_250d.parquet
│   │   ├── sideways_250d.parquet
│   │   └── with_nan_250d.parquet
│   ├── universe_100.parquet
│   └── golden_reports/             # 黄金基准（回归测试）
└── helpers/
    ├── kline_generator.py          # 参数化合成 K 线
    └── seed_data.py
```

### 11.6 覆盖率门禁

```ini
# pyproject.toml
[tool.pytest.ini_options]
addopts = "--cov=stone --cov-report=html --cov-report=term-missing --cov-fail-under=80"
testpaths = ["tests"]

[tool.coverage.run]
source = ["data", "selector", "reporters"]
omit = ["tests/*", "**/__init__.py", "main.py"]
```

**强制**：覆盖率 < 80% → pytest 退出码非零 → CI 失败。

### 11.7 TDD 工作流（每个新因子/模块）

```
1. RED   - 写测试，确认测试失败
2. GREEN - 写最小实现让测试通过
3. REFACTOR - 重构，测试仍通过
```

### 11.8 CI（GitHub Actions，可选）

```yaml
name: CI
on: [push, pull_request]
jobs:
  test:
    runs-on: macos-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - run: uv sync
      - run: uv run ruff check .
      - run: uv run mypy .
      - run: uv run pytest --cov-fail-under=80
```

### 11.9 测试工作量估算

| 类别 | 测试数 | 工作量 |
|---|---|---|
| 因子（16） | 64 | 1.5 天 |
| 打分引擎 | 12 | 0.5 天 |
| YAML/配置 | 15 | 0.5 天 |
| Parquet 存储 | 10 | 0.5 天 |
| Fetcher（mock） | 8 | 0.5 天 |
| 仓位计算 | 10 | 0.5 天 |
| ConstraintSolver | 6 | 0.25 天 |
| 集成 | 8 | 1 天 |
| E2E | 3 | 0.5 天 |
| **合计** | **~136** | **5.25 天** |

---

## 12. 关键设计决策汇总

| # | 决策 | 理由 |
|---|---|---|
| 1 | 项目定位为「个人投研辅助工具」（非荐股、非自动交易） | 法律合规 |
| 2 | 数据层 4 子系统共用，先稳定接口 | DRY，地基可复用 |
| 3 | parquet 按日期分区（非按股票） | 增量更新简单 + 全市场扫描快 |
| 4 | 因子按「自身历史分位」归一化（非横截面） | 避免当日极端值影响 |
| 5 | 基本面是「过滤型」（非打分型） | 用于排雷，YAGNI |
| 6 | YAML 配置 + pydantic 校验 + 安全 criterion | 用户友好 + 安全 |
| 7 | 权重总和必须 = 1.0（强制） | 避免计算错误 |
| 8 | 行业分散用贪心（非 ILP） | Top 30 规模小，实现简单 |
| 9 | 单股 10s 超时 + 单因子失败不崩 | 容错优先 |
| 10 | ProcessPoolExecutor 4 workers 并行 | 性能优化 |
| 11 | 仓位计算是算术工具（非建议） | 法律合规 |
| 12 | 资金配置不入库（`config/personal/`） | 隐私保护 |
| 13 | uv + Python 3.12（非系统 3.9.6） | 现代工具链 |
| 14 | launchd 定时任务（非 cron） | macOS 原生 |
| 15 | 测试覆盖率强制 ≥ 80% | 质量保障 |
| 16 | HTML K 线用 base64 PNG（单文件可分享） | 用户体验 |

---

## 13. 后续工作（Phase 2-5）

本设计文档仅覆盖 **Phase 1（数据层）+ Phase 2（选股子系统）**。后续子系统各自走完整 brainstorming → spec → plan 流程：

| Phase | 子系统 | 依赖 |
|---|---|---|
| 3 | 盯盘与信号提醒 | 数据层 + 信号引擎 + 推送（Server酱/企业微信） |
| 4 | 策略回测 | 数据层 + 回测引擎（T+1 模拟）+ 绩效报告 |
| 5 | 持仓管理与分析 | 持仓模型 + 交易日志 + 可视化 |

每个子系统启动时，复用本设计的 `data/` 地基，新模块挂载即可。

---

## 14. 风险与未决问题

| 风险 | 缓解 |
|---|---|
| akshare 接口变更（无版本保证） | 抽象 DataFetcher 接口；失败日志记录；可换 tushare pro |
| 全市场扫描性能不达标 | 已预算并行化；最坏可加缓存索引 |
| 因子过拟合（在历史数据上表现好但实战差） | 鼓励回测子系统验证（Phase 4）；保留参数化能力 |
| 用户错把候选股当荐股使用 | 报表底部固定显示免责声明 |
| 个人资金信息泄露 | `config/personal/` 入 .gitignore，强制不提交 |

---

**文档结束。**
