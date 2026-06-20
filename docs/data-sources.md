# 数据源说明

QuantSeed 支持三种 A 股数据源，按需选择即可。三者各有取舍，**新手建议从 AkShare 起步，进阶切到 Tushare，实盘对接 QMT**。

## 选型对比

| 维度 | AkShare | Tushare Pro | QMT (xtquant) |
|---|---|---|---|
| 是否免费 | ✅ 完全免费 | ⚠️ 部分免费（积分制） | ⚠️ 需券商账户 |
| 是否注册 | ❌ 不需要 | ✅ 必须注册 | ✅ 必须开户 |
| 数据覆盖 | 全市场 + 港美股 + 期货 + 宏观 | A 股 + 港美股 + 期货 + 基金 | A 股 + 期货 + 期权（订阅制） |
| 频率限制 | ⚠️ 强（东财/新浪会断连） | ✅ 按积分分级 | ✅ 本地数据，无限制 |
| 实时行情 | ⚠️ 全市场快照 60s 缓存 | ✅ 付费订阅 | ✅ tick 级实时 |
| 历史回溯 | 全历史 | 全历史 | 取决于本地下载 |
| 适合场景 | 学习 / 原型验证 | 回测 / 因子研究 | 实盘交易 |
| 安装 | `pip install akshare` | `pip install tushare` | 随 QMT 客户端附带 |

---

## 一、AkShare（默认，零门槛）

### 简介
- **官网**：https://akshare.akfamily.xyz/
- **GitHub**：https://github.com/akfamily/akshare
- **性质**：开源免费，聚合东财、新浪、同花顺等公开接口
- **注册**：**不需要任何账号**，`pip install akshare` 即装即用

### 启用方式
```bash
# 不需要任何环境变量，开箱即用
pip install akshare
```

QuantSeed 默认就是 AkShare，无需配置。

### ⚠️ 已知限制（重要）
1. **频率限制**：底层走东财/新浪公开接口，**连续高频请求会被服务端主动断连**，典型报错：
   ```
   ('Connection aborted.', RemoteDisconnected('Remote end closed connection without response'))
   ```
   - QuantSeed 已在 `AkShareProvider` 内置 0.3 秒请求间隔节流
   - 全市场 5000+ 只股票逐个拉取仍可能触发，**演示和回测请限制样本数**
   - 民间偏方：在浏览器登录 https://www.eastmoney.com/ 后再运行，可缓解

2. **接口稳定性**：第三方接口偶尔会因源站改版失效，akshare 升级版本通常能修复
3. **实时行情**：`stock_zh_a_spot_em` 返回全市场快照，QuantSeed 缓存 60 秒

### 常用接口
| 功能 | 函数 |
|---|---|
| A 股日线 | `ak.stock_zh_a_hist(symbol, period, start_date, end_date, adjust)` |
| 指数日线 | `ak.stock_zh_index_daily(symbol)` |
| 全市场实时 | `ak.stock_zh_a_spot_em()` |
| 交易日历 | `ak.tool_trade_date_hist_sina()` |
| 财务报表 | `ak.stock_financial_report_sina(symbol)` |

---

## 二、Tushare Pro（推荐进阶）

### 简介
- **官网**：https://tushare.pro
- **性质**：社区维护的 Pro 版，数据质量稳定，按积分分级授权
- **注册**：**必须注册账号**，获取 Token 后才能调用

### 注册步骤
1. 访问 https://tushare.pro/register 注册账号
2. 登录后进入「个人主页」→「接口 TOKEN」复制 Token
3. 完成新手任务、邀请等可获得积分（免费 120 积分起步）

### 启用方式
```bash
# Windows PowerShell
$env:TUSHARE_TOKEN = "你的token"

# Linux/macOS
export TUSHARE_TOKEN="你的token"

# 切换数据源
$env:QUANTSEED_DATA_PROVIDER = "tushare"
```

### 积分权限表（摘自官方文档）

| 积分数 | 每分钟频次 | 每天上限 | 可访问接口 | 价格（元/年） |
|---|---|---|---|---|
| 120 | 50 | 8000 次 | 非复权日线 | 0（免费） |
| 2000+ | 200 | 100000 次/接口 | 复权行情、daily_basic、龙虎榜等 | 200 |
| 5000+ | 500 | 常规无上限 | 大部分常规接口 | 500 |
| 10000+ | 500 | 特色 300 次/分 | 盈利预测、筹码分布等特色数据 | 1000 |

> 分钟数据、港美股、新闻舆情等需**单独开权限**，与积分无关，详见 https://tushare.pro/document/1?doc_id=290

### 关键接口积分要求
| 接口 | 用途 | 最低积分 |
|---|---|---|
| `daily` | 非复权日线 | 120 |
| `pro_bar` | 复权日线（前复权/后复权） | 2000 |
| `daily_basic` | 每日指标（PE/PB/换手率） | 2000 |
| `fina_indicator` | 财务指标 | 2000 |
| `trade_cal` | 交易日历 | 120 |
| `stock_basic` | 股票列表 | 120 |

### ⚠️ 使用注意
- **复权数据**：`pro.daily` 不支持 `adj` 参数，必须用 `pro_bar`（2000 积分）
- **日期格式**：Tushare 接口要求 `YYYYMMDD`（无分隔符），QuantSeed 已在 Provider 内自动转换
- **频次控制**：免费 120 积分用户每分钟仅 50 次，建议加缓存或升级积分

---

## 三、QMT / MiniQMT（实盘交易）

### 简介
- **官网**：https://qmt.hxquant.com/
- **性质**：迅投科技出品的量化交易终端，对接券商柜台
- **注册**：**必须在合作券商开户**并申请 QMT 权限（国金、华泰、中信建投等支持）

### 三件套关系
- **MiniQMT**：本地终端软件，作为本地服务器运行，接收行情 + 提供交易接口
- **XtQuant**：MiniQMT 的 Python 接口库，随客户端附带
- **xtdata**：XtQuant 中的行情模块（历史 K 线 + 实时订阅）
- **xttrader**：XtQuant 中的交易模块（下单 / 撤单 / 持仓查询）

### 启用步骤
1. 在合作券商开户并申请 QMT/MiniQMT 权限
2. 下载安装 MiniQMT 客户端并登录
3. 找到 MiniQMT 安装目录下的 `userdata_mini` 文件夹路径
4. 配置环境变量：
   ```bash
   # Windows（典型路径，按实际安装位置调整）
   $env:QMT_USERDATA_PATH = "D:\国金QMT\userdata_mini"
   $env:QMT_SESSION_ID = "123456"   # 任意 6 位数字
   $env:QMT_DATA_PATH = "quantseed_data.db"  # SQLite 数据库路径
   $env:QUANTSEED_DATA_PROVIDER = "sqlite"
   ```

### 数据获取方式
QMT 不直接走 HTTP API，而是从本地 MiniQMT 服务读取已下载的数据：
```python
from xtquant import xtdata
xtdata.download_history_data("600519.SH", "1d", "20240101", "20241231")
data = xtdata.get_local_data([], "1d", "20240101", "20241231")
```

QuantSeed 通过 `SQLiteProvider` 读取预先同步到 SQLite 的数据，避免每次运行都依赖 MiniQMT 在线。

### ⚠️ 使用注意
1. **账户订阅可能失败**：`xttrader.connect()` 返回 0 不代表账户订阅成功，QuantSeed 已加 `account is None` 检查
2. **数据需先下载**：`xtdata.get_local_data` 只返回已下载的数据，未下载的需先调 `download_history_data`
3. **MiniQMT 必须保持运行**：交易时段下单需要 MiniQMT 在线
4. **xtquant 不在 PyPI**：必须从 MiniQMT 安装目录复制 `xtquant` 文件夹到 site-packages

### 数据同步
```bash
# 触发数据同步（实际下载需在 MiniQMT 客户端操作）
quantseed sync
```

---

## 切换数据源

通过环境变量 `QUANTSEED_DATA_PROVIDER` 切换，取值：`akshare` / `tushare` / `sqlite`

```bash
# AkShare（默认）
$env:QUANTSEED_DATA_PROVIDER = "akshare"

# Tushare
$env:QUANTSEED_DATA_PROVIDER = "tushare"
$env:TUSHARE_TOKEN = "你的token"

# QMT 本地数据
$env:QUANTSEED_DATA_PROVIDER = "sqlite"
$env:QMT_DATA_PATH = "quantseed_data.db"
```

切换后用 `quantseed check` 验证连通性。

---

## 常见问题

### Q1: AkShare 报 RemoteDisconnected 怎么办？
A: 这是东财/新浪的反爬。QuantSeed 已内置 0.3s 节流，但仍可能触发。解决方案：
1. 演示/回测限制股票数量（demo 策略默认只取 10 只）
2. 浏览器登录 https://www.eastmoney.com/ 后再运行
3. 切换到 Tushare（推荐）或 QMT 本地数据

### Q2: Tushare 报 "权限不足" 怎么办？
A: 对应接口积分不够。免费 120 积分只能用 `daily`（非复权日线），复权数据需 2000 积分。可在 https://tushare.pro/weborder/#/permission 升级。

### Q3: QMT 连接成功但下单失败？
A: 检查：
1. MiniQMT 是否在线（任务栏图标）
2. `QMT_USERDATA_PATH` 是否指向 `userdata_mini` 而非 `userdata`
3. 账户是否已订阅成功（看日志是否有 "订阅账户失败"）

### Q4: 三种数据源的字段格式一致吗？
A: 一致。QuantSeed 在 Provider 层做了字段标准化，调用方拿到的 DataFrame 列名统一为 `trade_date / code / open / close / high / low / volume / amount / change_pct / turnover_rate`，日期格式统一为 `YYYY-MM-DD`。
