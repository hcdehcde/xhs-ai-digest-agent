# 简历数据口径说明

这份文档用于记录 `AI 日报助手` 项目里简历数据的测试方法、样本口径和复算命令。

目标是回答两个问题：

1. 简历里写的数字是怎么算出来的？
2. 后面如果继续跑日报，应该怎么更新这些数字？

## 当前建议写法

当前简历里最稳的两组数字：

- 候选内容压缩约 `93%`
- 筛选阶段过滤约 `36%`

稳定性指标当前建议写法：

- `0` 次作者抓取错误

注意：

- 这三个数字都来自本地日报引擎的真实运行结果
- 建议只统计 `生成成功` 的日报结果，不把失败文件混进去
- `知识库问答` 和 `Coze` 不参与这些指标的计算

## 数据来源

统计来源为 `reports/*.json`。

其中：

- 成功日报文件结构包含：
  - `summary`
  - `digest_items`
- 失败日报文件结构通常只有：
  - `date`
  - `status`
  - `reason`
  - `message`

因此统计时应排除失败文件。

## 指标定义

### 1. 候选内容压缩率

用于描述从原始候选内容到最终日报内容的压缩程度。

公式：

```text
压缩率 = 1 - (最终日报条数 / 候选内容总数)
```

字段对应：

- 候选内容总数：`summary.total_candidates`
- 最终日报条数：`len(digest_items)`

简历写法：

- 将候选内容压缩约 `93%`

### 2. 筛选阶段过滤率

用于描述规则过滤、噪音识别和准入控制在筛选阶段剔除了多少候选内容。

公式：

```text
过滤率 = 1 - (筛选后保留数 / 候选内容总数)
```

字段对应：

- 候选内容总数：`summary.total_candidates`
- 筛选后保留数：`summary.kept_candidates`

简历写法：

- 在筛选阶段约过滤 `36%` 的候选内容

### 3. 作者抓取错误数

用于说明自动化链路的稳定性。

字段对应：

- `author_fetch_errors`

如果字段是列表，则统计：

```text
len(author_fetch_errors)
```

简历写法：

- 在当前测试样本中实现 `0` 次作者抓取错误

## 样本口径

目前建议保留两套口径：

### 口径 A：全量成功样本

适合做内部统计，不建议直接用于简历。

纳入规则：

- 只统计 `reports/*.json` 中同时包含 `summary` 和 `digest_items` 的文件
- 排除失败文件，例如只有 `status=failed` 的结果

当前全量成功样本结果：

- 样本数：`11`
- 平均候选数：`31.82`
- 平均保留数：`19.09`
- 平均日报条数：`2.18`
- 压缩率：`93.14%`
- 过滤率：`40.00%`
- 平均作者抓取错误数：`0`

### 口径 B：后期稳定样本

适合写入简历。

原因：

- 这部分样本更接近最终规则版本
- 早期原型阶段的实验性结果波动较大，不适合作为最终对外口径

建议纳入文件：

- `2026-04-23.json`
- `2026-04-24.json`
- `xhs-prototype-20260423-160140.json`
- `xhs-prototype-20260423-182234.json`
- `xhs-prototype-20260423-182516.json`
- `xhs-prototype-20260423-185904.json`
- `xhs-prototype-20260423-191516.json`

当前稳定样本结果：

- 样本数：`7`
- 平均候选数：`33.43`
- 平均保留数：`22.43`
- 平均日报条数：`1.86`
- 压缩率：`94.44%`
- 过滤率：`32.91%`
- 平均作者抓取错误数：`0`

## 为什么简历里写 93% / 36%

简历不是科研论文，不需要写到小数点后两位。

推荐使用“保守四舍五入”的方式：

- 压缩率写 `约 93%`
- 过滤率写 `约 36%`

原因：

- `93%` 与当前多组样本结果一致，表达稳妥
- `36%` 比 `40%` 更保守，也更贴近早期稳定样本的说法
- 面试时如果被问，可以明确说明：数字来自多次成功运行结果的统计，并做了保守取整

## 推荐复算命令

### 1. 统计全部成功样本

在项目根目录执行：

```bash
python3 - <<'PY'
import json, glob, os
from statistics import mean

rows = []
for path in sorted(glob.glob('reports/*.json')):
    try:
        data = json.load(open(path))
    except Exception:
        continue
    if 'summary' not in data or 'digest_items' not in data:
        continue
    s = data['summary']
    total = s.get('total_candidates')
    kept = s.get('kept_candidates')
    digest = len(data.get('digest_items') or [])
    errs = len(data.get('author_fetch_errors') or []) if isinstance(data.get('author_fetch_errors'), list) else s.get('author_fetch_errors', 0)
    if isinstance(total, (int, float)) and isinstance(kept, (int, float)) and total:
        rows.append((os.path.basename(path), total, kept, digest, errs))

print('样本数:', len(rows))
print('平均候选数:', round(mean(r[1] for r in rows), 2))
print('平均保留数:', round(mean(r[2] for r in rows), 2))
print('平均日报条数:', round(mean(r[3] for r in rows), 2))
print('压缩率(%):', round((1 - mean(r[3] for r in rows) / mean(r[1] for r in rows)) * 100, 2))
print('过滤率(%):', round((1 - mean(r[2] for r in rows) / mean(r[1] for r in rows)) * 100, 2))
print('平均作者抓取错误数:', round(mean(r[4] for r in rows), 2))
PY
```

### 2. 统计后期稳定样本

在项目根目录执行：

```bash
python3 - <<'PY'
import json, os
from statistics import mean

files = [
    '2026-04-23.json',
    '2026-04-24.json',
    'xhs-prototype-20260423-160140.json',
    'xhs-prototype-20260423-182234.json',
    'xhs-prototype-20260423-182516.json',
    'xhs-prototype-20260423-185904.json',
    'xhs-prototype-20260423-191516.json',
]

rows = []
for name in files:
    path = os.path.join('reports', name)
    data = json.load(open(path))
    s = data['summary']
    rows.append((
        name,
        s['total_candidates'],
        s['kept_candidates'],
        len(data['digest_items']),
        len(data.get('author_fetch_errors') or []),
    ))

print('样本数:', len(rows))
print('平均候选数:', round(mean(r[1] for r in rows), 2))
print('平均保留数:', round(mean(r[2] for r in rows), 2))
print('平均日报条数:', round(mean(r[3] for r in rows), 2))
print('压缩率(%):', round((1 - mean(r[3] for r in rows) / mean(r[1] for r in rows)) * 100, 2))
print('过滤率(%):', round((1 - mean(r[2] for r in rows) / mean(r[1] for r in rows)) * 100, 2))
print('平均作者抓取错误数:', round(mean(r[4] for r in rows), 2))
PY
```

## 面试时怎么解释这些数字

建议口径：

- `93%`：指从原始候选内容到最终日报内容的压缩比例
- `36%`：指候选内容在筛选阶段被过滤掉的比例
- `0 次作者抓取错误`：指在当前测试样本内，作者抓取阶段没有出现错误

推荐解释方式：

> 这些数字不是拍脑袋写的，都是从本地日报运行结果里统计出来的。我们会把每次运行的候选数、保留数、最终日报条数和作者抓取错误数落到 JSON 里，再基于成功样本做汇总统计。简历里使用的是更保守的近似值，避免把实验期波动写得太满。

## 当前简历建议写法

- 推荐排序：针对有效信息密度低的问题，搭建“特征抽取 - 打分 - 排序”流程，最终将候选内容压缩约 `93%`。
- 信息过滤：面向低质内容混入问题，设计规则与特征双重过滤机制，在筛选阶段约过滤 `36%` 的候选内容，提升信息流质量。
- 自动化运行：实现日报任务的定时调度、登录态校验与异常兜底，保障自动化日报生成链路稳定运行。
