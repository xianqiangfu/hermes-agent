# 记忆系统

## 概述

记忆系统是 Hermes 的核心组件，用于存储、检索和管理对话中的重要信息。它提供了一套完整的机制，让 AI 能够记住用户的偏好、重要的事实、对话历史等，并在后续对话中智能地检索和使用这些信息。

记忆系统采用插件化架构，支持多种记忆存储后端，包括：

- **holographic**: 内置的全息压缩表示存储（推荐）
- **honcho**: Honcho 记忆服务
- **mem0**: Mem0 记忆服务
- **byterover**: ByteRover 记忆服务
- **openvikings**: OpenVikings 记忆服务
- **retaindb**: RetainDB 记忆服务
- **supermemory**: SuperMemory 记忆服务

## 核心概念

### 记忆存储（Memory Store）

记忆存储是记忆的持久化层，负责保存事实、实体关联、信任分数等信息。内置的 `holographic` 存储使用 SQLite 数据库，提供了：

- 事实的增删改查
- 实体提取和关联
- 信任分数管理
- 全文检索
- 全息压缩表示（HRR）编码

### 记忆检索（Memory Retrieval）

记忆检索提供了多种策略来查找相关记忆：

1. **全文检索（FTS）**: 基于 SQLite FTS5 的关键词搜索
2. **Jaccard 相似度**: 基于 token 重叠度的重排序
3. **全息压缩表示（HRR）**: 基于向量代数的语义检索
4. **实体探测**: 查找与特定实体相关的事实
5. **关联发现**: 发现与实体内在关联的事实
6. **组合推理**: 多实体的组合查询

### 记忆策展（Memory Curation）

记忆策展由 `agent/curator.py` 模块负责，主要功能包括：

- 自动维护技能的生命周期状态
- 定期审查和整理技能
- 将细粒度技能合并为更广泛的"保护伞"技能
- 归档过时或不相关的技能
- 管理技能的固定/取消固定状态

## 全息压缩表示（HRR）

全息压缩表示是一种向量符号架构，用于将组合结构编码为固定宽度的分布式表示。核心操作包括：

- **绑定（Bind）**: 将两个概念关联（相位相加）
- **解绑（Unbind）**: 检索绑定的值（相位相减）
- **打包（Bundle）**: 合并多个概念（复数叠加的循环平均）

HRR 的优势：
- 跨平台可重复的原子编码（基于 SHA-256）
- 支持代数推理
- 可检测矛盾事实
- 内存效率高

## 完整工作流

### 1. 记忆记录流程

```
用户对话
    ↓
消息处理钩子
    ↓
实体提取（首字母大写词、引号内容、aka模式）
    ↓
事实创建（内容、分类、标签）
    ↓
实体解析和关联
    ↓
HRR 向量编码（内容 + 实体）
    ↓
更新记忆库向量
    ↓
保存到 SQLite 数据库
    ↓
更新全文索引
```

### 2. 记忆检索流程

```
用户查询
    ↓
查询预处理（分词、向量化）
    ↓
FTS5 候选获取（多返回 3 倍结果用于重排序）
    ↓
Jaccard 相似度计算
    ↓
HRR 向量相似度计算
    ↓
权重合并（FTS:0.4, Jaccard:0.3, HRR:0.3）
    ↓
信任分数加权
    ↓
时间衰减（可选）
    ↓
排序并返回 Top-N 结果
    ↓
增加检索计数
```

### 3. 记忆策展流程

```
定期触发（默认每周一次）
    ↓
检查空闲时间（默认至少 2 小时）
    ↓
自动状态迁移
    ├─ 标记过时（默认 30 天不活跃）
    ├─ 归档（默认 90 天不活跃）
    └─ 重新激活（恢复活跃的技能）
    ↓
创建预运行快照
    ↓
LLM 审查（可选，用于合并技能）
    ├─ 识别前缀聚类
    ├─ 创建/更新保护伞技能
    ├─ 移动内容到 references/templates/scripts
    └─ 归档被吸收的技能
    ↓
更新 cron 作业引用
    ↓
保存运行报告
    ↓
更新 .curator_state
```

## 使用示例

### 配置记忆提供商

在 `~/.hermes/config.yaml` 中配置：

```yaml
memory:
  provider: holographic  # 选择记忆提供商
```

### 直接使用记忆存储

```python
from plugins.memory.holographic.store import MemoryStore
from plugins.memory.holographic.retrieval import FactRetriever

# 创建存储实例
store = MemoryStore()

# 添加事实
fact_id = store.add_fact(
    content="Alice 喜欢 Python 编程语言",
    category="user_preferences",
    tags="alice,language,python"
)

# 检索事实
results = store.search_facts("Alice 喜欢什么语言？")

# 使用高级检索
retriever = FactRetriever(store)
results = retriever.search("Python", category="user_preferences")

# 实体探测
entity_facts = retriever.probe("Alice")

# 发现关联
related = retriever.related("Python")

# 组合推理
reasoning = retriever.reason(["Alice", "Python"])

# 检测矛盾
contradictions = retriever.contradict()
```

### 使用记忆策展

```python
from agent import curator

# 手动运行策展（同步）
result = curator.run_curator_review(
    synchronous=True,
    dry_run=False  # 设置为 True 仅预览不执行变更
)

# 检查是否应该运行
if curator.should_run_now():
    curator.maybe_run_curator()

# 管理状态
curator.set_paused(True)   # 暂停策展
curator.set_paused(False)  # 恢复策展
curator.is_paused()        # 检查状态
curator.is_enabled()       # 检查是否启用
```

## 核心文件说明

### `plugins/memory/__init__.py`

记忆提供商插件发现和加载模块。主要功能：

- 扫描内置和用户安装的记忆提供商插件
- 加载指定的记忆提供商
- 提供插件 CLI 命令发现

### `plugins/memory/holographic/holographic.py`

全息压缩表示（HRR）核心实现。主要函数：

- `encode_atom(word, dim)`: 编码单个原子为相位向量
- `bind(a, b)`: 绑定两个向量（相位相加）
- `unbind(memory, key)`: 解绑向量（相位相减）
- `bundle(*vectors)`: 打包多个向量
- `similarity(a, b)`: 计算两个向量的余弦相似度
- `encode_text(text, dim)`: 编码文本为词袋向量
- `encode_fact(content, entities, dim)`: 编码事实及其实体
- `phases_to_bytes(phases)`: 序列化相位向量
- `bytes_to_phases(data)`: 反序列化相位向量
- `snr_estimate(dim, n_items)`: 估计信噪比

### `plugins/memory/holographic/store.py`

SQLite 记忆存储实现。主要类：

- `MemoryStore`: 记忆存储核心类
  - `add_fact(content, category, tags)`: 添加事实
  - `search_facts(query, category, min_trust, limit)`: 全文搜索
  - `update_fact(fact_id, content, trust_delta, tags, category)`: 更新事实
  - `remove_fact(fact_id)`: 删除事实
  - `list_facts(category, min_trust, limit)`: 列出事实
  - `record_feedback(fact_id, helpful)`: 记录用户反馈
  - `rebuild_all_vectors(dim)`: 重建所有 HRR 向量

### `plugins/memory/holographic/retrieval.py`

高级检索实现。主要类：

- `FactRetriever`: 多策略事实检索器
  - `search(query, category, min_trust, limit)`: 混合搜索
  - `probe(entity, category, limit)`: 实体检索
  - `related(entity, category, limit)`: 关联发现
  - `reason(entities, category, limit)`: 组合推理
  - `contradict(category, threshold, limit)`: 矛盾检测

### `agent/curator.py`

记忆策展模块。主要函数：

- `load_state()`: 加载策展状态
- `save_state(data)`: 保存策展状态
- `set_paused(paused)`: 设置暂停状态
- `is_paused()`: 检查暂停状态
- `is_enabled()`: 检查是否启用
- `should_run_now(now)`: 检查是否应该运行
- `apply_automatic_transitions(now)`: 应用自动状态迁移
- `run_curator_review(on_summary, synchronous, dry_run)`: 运行策展审查
- `maybe_run_curator(idle_for_seconds, on_summary)`: 尝试运行策展

## 数据库结构

### facts 表

| 字段 | 类型 | 说明 |
|------|------|------|
| fact_id | INTEGER | 主键，自增 |
| content | TEXT | 事实内容（唯一） |
| category | TEXT | 分类，默认 general |
| tags | TEXT | 标签，逗号分隔 |
| trust_score | REAL | 信任分数，默认 0.5 |
| retrieval_count | INTEGER | 检索次数，默认 0 |
| helpful_count | INTEGER | 有帮助次数，默认 0 |
| created_at | TIMESTAMP | 创建时间 |
| updated_at | TIMESTAMP | 更新时间 |
| hrr_vector | BLOB | HRR 向量 |

### entities 表

| 字段 | 类型 | 说明 |
|------|------|------|
| entity_id | INTEGER | 主键，自增 |
| name | TEXT | 实体名称 |
| entity_type | TEXT | 实体类型，默认 unknown |
| aliases | TEXT | 别名，逗号分隔 |
| created_at | TIMESTAMP | 创建时间 |

### fact_entities 表

| 字段 | 类型 | 说明 |
|------|------|------|
| fact_id | INTEGER | 关联的事实 ID |
| entity_id | INTEGER | 关联的实体 ID |

### memory_banks 表

| 字段 | 类型 | 说明 |
|------|------|------|
| bank_id | INTEGER | 主键，自增 |
| bank_name | TEXT | 记忆库名称（唯一） |
| vector | BLOB | 打包的向量 |
| dim | INTEGER | 向量维度 |
| fact_count | INTEGER | 包含的事实数量 |
| updated_at | TIMESTAMP | 更新时间 |

## 配置选项

### curator 配置

在 `~/.hermes/config.yaml` 中：

```yaml
curator:
  enabled: true  # 是否启用策展
  interval_hours: 168  # 运行间隔（小时），默认 7 天
  min_idle_hours: 2  # 最小空闲时间（小时），默认 2 小时
  stale_after_days: 30  # 标记过时天数，默认 30 天
  archive_after_days: 90  # 归档天数，默认 90 天
  auxiliary:  # 用于策展的 LLM 配置（旧版）
    provider: anthropic
    model: claude-3-opus
    api_key: ...
    base_url: ...

# 推荐使用新的统一辅助任务配置
auxiliary:
  curator:
    provider: anthropic
    model: claude-3-opus
    api_key: ...
    base_url: ...
```

## 注意事项

1. **信任分数**: 新事实默认信任分数 0.5，用户可以通过反馈调整。有帮助 +0.05，无帮助 -0.10。

2. **HRR 容量**: HRR 向量维度 1024 时，推荐最多存储约 250 个事实（SNR=2）。超过会降低检索准确性。

3. **实体提取**: 自动提取以下模式的实体：
   - 首字母大写的多词短语（如 "Alice Smith"）
   - 双引号内容（如 "Python"）
   - 单引号内容（如 'pytest'）
   - aka 模式（如 "Guido aka BDFL"）

4. **并发安全**: MemoryStore 使用 `threading.RLock` 保证线程安全，支持多线程访问。

5. **WAL 模式**: SQLite 使用 WAL（Write-Ahead Logging）模式提高并发性能。

6. **策展安全**: 策展永不直接删除技能，只会移动到 `.archive/` 目录，可恢复。

7. **固定技能**: 标记为 `pinned` 的技能不受自动状态迁移和策展合并影响。

8. **Cron 作业**: 策展会自动更新 cron 作业中的技能引用，确保合并后的作业继续工作。

## 相关文档

- 各个记忆提供商的详细说明请参阅各自目录下的 `README.md`
- 技能管理相关请参阅 `tools/skill_usage.py`
- Cron 作业相关请参阅 `cron/jobs.py`
