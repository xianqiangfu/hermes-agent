"""
记忆存储的混合关键词/BM25 检索。

从 KIK memory_agent.py 移植——结合 FTS5 全文搜索与
Jaccard 相似度重排序和信任加权评分。
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .store import MemoryStore

try:
    from . import holographic as hrr
except ImportError:
    import holographic as hrr  # type: ignore[no-redef]


class FactRetriever:
    """
    具有信任加权评分的多策略事实检索器。

    支持的检索策略：
    - 混合搜索（全文 + Jaccard + HRR）
    - 实体探测（HRR 代数查询）
    - 关联发现（通过结构相似性）
    - 组合推理（多实体交集）
    - 矛盾检测（实体重叠 + 内容分歧）
    """

    def __init__(
        self,
        store: MemoryStore,
        temporal_decay_half_life: int = 0,  # 天数，0 表示禁用
        fts_weight: float = 0.4,
        jaccard_weight: float = 0.3,
        hrr_weight: float = 0.3,
        hrr_dim: int = 1024,
    ) -> None:
        """
        初始化事实检索器。

        参数：
            store: MemoryStore 实例
            temporal_decay_half_life: 时间衰减半衰期（天数），0 表示禁用
            fts_weight: 全文搜索权重
            jaccard_weight: Jaccard 相似度权重
            hrr_weight: HRR 向量相似度权重
            hrr_dim: HRR 向量维度
        """
        self.store = store
        self.half_life = temporal_decay_half_life
        self.hrr_dim = hrr_dim

        # 如果 numpy 不可用，自动重新分配权重
        if hrr_weight > 0 and not hrr._HAS_NUMPY:
            fts_weight = 0.6
            jaccard_weight = 0.4
            hrr_weight = 0.0

        self.fts_weight = fts_weight
        self.jaccard_weight = jaccard_weight
        self.hrr_weight = hrr_weight

    def search(
        self,
        query: str,
        category: str | None = None,
        min_trust: float = 0.3,
        limit: int = 10,
    ) -> list[dict]:
        """
        混合搜索：FTS5 候选 → Jaccard 重排序 → 信任加权。

        处理流程：
        1. FTS5 搜索：获取 limit*3 个候选（多取一些用于重排序）
        2. Jaccard 增强：查询与事实内容的 token 重叠
        3. 信任加权：最终分数 = 相关性 * 信任分数
        4. 时间衰减（可选）：decay = 0.5^(age_days / half_life)

        返回带有 score 字段的事实字典列表，按分数降序排序。
        """
        # 阶段 1：获取 FTS5 候选（多取一些用于重排序）
        candidates = self._fts_candidates(query, category, min_trust, limit * 3)

        if not candidates:
            return []

        # 阶段 2：使用 Jaccard + 信任 + 可选衰减进行重排序
        query_tokens = self._tokenize(query)
        scored = []

        for fact in candidates:
            content_tokens = self._tokenize(fact["content"])
            tag_tokens = self._tokenize(fact.get("tags", ""))
            all_tokens = content_tokens | tag_tokens

            jaccard = self._jaccard_similarity(query_tokens, all_tokens)
            fts_score = fact.get("fts_rank", 0.0)

            # HRR 相似度
            if self.hrr_weight > 0 and fact.get("hrr_vector"):
                fact_vec = hrr.bytes_to_phases(fact["hrr_vector"])
                query_vec = hrr.encode_text(query, self.hrr_dim)
                hrr_sim = (hrr.similarity(query_vec, fact_vec) + 1.0) / 2.0  # 移到 [0,1]
            else:
                hrr_sim = 0.5  # 中性值

            # 合并 FTS5 + Jaccard + HRR
            relevance = (self.fts_weight * fts_score
                        + self.jaccard_weight * jaccard
                        + self.hrr_weight * hrr_sim)

            # 信任加权
            score = relevance * fact["trust_score"]

            # 可选时间衰减
            if self.half_life > 0:
                score *= self._temporal_decay(fact.get("updated_at") or fact.get("created_at"))

            fact["score"] = score
            scored.append(fact)

        # 按分数降序排序，返回前 limit 个
        scored.sort(key=lambda x: x["score"], reverse=True)
        results = scored[:limit]
        # 移除原始 HRR 字节——调用者期望 JSON 可序列化的字典
        for fact in results:
            fact.pop("hrr_vector", None)
        return results

    def probe(
        self,
        entity: str,
        category: str | None = None,
        limit: int = 10,
    ) -> list[dict]:
        """
        使用 HRR 代数的组合实体检索。

        将实体从记忆库中解绑以提取关联内容。
        这不是关键词搜索——它使用代数结构来查找实体在其中扮演结构角色的事实。

        如果 numpy 不可用则回退到 FTS5 搜索。
        """
        if not hrr._HAS_NUMPY:
            # 回退到实体名称的关键词搜索
            return self.search(entity, category=category, limit=limit)

        conn = self.store._conn

        # 将实体编码为角色绑定向量
        role_entity = hrr.encode_atom("__hrr_role_entity__", self.hrr_dim)
        entity_vec = hrr.encode_atom(entity.lower(), self.hrr_dim)
        probe_key = hrr.bind(entity_vec, role_entity)

        # 先尝试分类特定的库，然后是所有事实
        if category:
            bank_name = f"cat:{category}"
            bank_row = conn.execute(
                "SELECT vector FROM memory_banks WHERE bank_name = ?",
                (bank_name,),
            ).fetchone()
            if bank_row:
                bank_vec = hrr.bytes_to_phases(bank_row["vector"])
                extracted = hrr.unbind(bank_vec, probe_key)
                # 使用提取的信号对单个事实进行评分
                return self._score_facts_by_vector(
                    extracted, category=category, limit=limit
                )

        # 直接对单个事实向量进行评分
        where = "WHERE hrr_vector IS NOT NULL"
        params: list = []
        if category:
            where += " AND category = ?"
            params.append(category)

        rows = conn.execute(
            f"""
            SELECT fact_id, content, category, tags, trust_score,
                   retrieval_count, helpful_count, created_at, updated_at,
                   hrr_vector
            FROM facts
            {where}
            """,
            params,
        ).fetchall()

        if not rows:
            # 最终回退：关键词搜索
            return self.search(entity, category=category, limit=limit)

        scored = []
        for row in rows:
            fact = dict(row)
            fact_vec = hrr.bytes_to_phases(fact.pop("hrr_vector"))
            # 从事实中解绑探测键，查看实体是否在结构上存在
            residual = hrr.unbind(fact_vec, probe_key)
            # 将残差与内容信号进行比较
            role_content = hrr.encode_atom("__hrr_role_content__", self.hrr_dim)
            content_vec = hrr.bind(hrr.encode_text(fact["content"], self.hrr_dim), role_content)
            sim = hrr.similarity(residual, content_vec)
            fact["score"] = (sim + 1.0) / 2.0 * fact["trust_score"]
            scored.append(fact)

        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:limit]

    def related(
        self,
        entity: str,
        category: str | None = None,
        limit: int = 10,
    ) -> list[dict]:
        """
        发现与实体共享结构连接的事实。

        与探测不同（探测查找关于实体的事实），关联发现查找通过共享上下文连接的事实——
        例如，与此实体一起提到的其他实体，或在结构上重叠的内容。

        如果 numpy 不可用则回退到 FTS5 搜索。
        """
        if not hrr._HAS_NUMPY:
            return self.search(entity, category=category, limit=limit)

        conn = self.store._conn

        # 将实体编码为裸原子（不绑定角色——我们想要任何结构匹配）
        entity_vec = hrr.encode_atom(entity.lower(), self.hrr_dim)

        # 获取所有带有向量的事实
        where = "WHERE hrr_vector IS NOT NULL"
        params: list = []
        if category:
            where += " AND category = ?"
            params.append(category)

        rows = conn.execute(
            f"""
            SELECT fact_id, content, category, tags, trust_score,
                   retrieval_count, helpful_count, created_at, updated_at,
                   hrr_vector
            FROM facts
            {where}
            """,
            params,
        ).fetchall()

        if not rows:
            return self.search(entity, category=category, limit=limit)

        # 通过实体的原子在其向量中的出现程度对每个事实进行评分
        # 这会捕获角色绑定的实体匹配和内容词匹配
        scored = []
        for row in rows:
            fact = dict(row)
            fact_vec = hrr.bytes_to_phases(fact.pop("hrr_vector"))

            # 检查结构相似性：从事实中解绑实体
            residual = hrr.unbind(fact_vec, entity_vec)
            # 与任何已知角色向量的高相似度残差意味着该实体在事实中扮演结构角色
            role_entity = hrr.encode_atom("__hrr_role_entity__", self.hrr_dim)
            role_content = hrr.encode_atom("__hrr_role_content__", self.hrr_dim)

            entity_role_sim = hrr.similarity(residual, role_entity)
            content_role_sim = hrr.similarity(residual, role_content)
            # 取最大值——实体可能出现在任何角色中
            best_sim = max(entity_role_sim, content_role_sim)

            fact["score"] = (best_sim + 1.0) / 2.0 * fact["trust_score"]
            scored.append(fact)

        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:limit]

    def reason(
        self,
        entities: list[str],
        category: str | None = None,
        limit: int = 10,
    ) -> list[dict]:
        """
        多实体组合查询——向量空间交集。

        给定多个实体，代数地相交它们的结构连接，以找到同时与所有实体相关的事实。
        这是没有嵌入数据库可以做到的组合推理。

        示例：reason(["peppi", "backend"]) 查找 peppi 和 backend 同时扮演结构角色的事实——无需关键词匹配。

        如果 numpy 不可用则回退到 FTS5 搜索。
        """
        if not hrr._HAS_NUMPY or not entities:
            # 回退：使用所有实体作为关键词搜索
            query = " ".join(entities)
            return self.search(query, category=category, limit=limit)

        conn = self.store._conn
        role_entity = hrr.encode_atom("__hrr_role_entity__", self.hrr_dim)

        # 对每个实体，通过从每个事实向量中解绑实体+角色来计算库"记住"了关于它的什么
        entity_residuals = []
        for entity in entities:
            entity_vec = hrr.encode_atom(entity.lower(), self.hrr_dim)
            probe_key = hrr.bind(entity_vec, role_entity)
            entity_residuals.append(probe_key)

        # 获取所有带有向量的事实
        where = "WHERE hrr_vector IS NOT NULL"
        params: list = []
        if category:
            where += " AND category = ?"
            params.append(category)

        rows = conn.execute(
            f"""
            SELECT fact_id, content, category, tags, trust_score,
                   retrieval_count, helpful_count, created_at, updated_at,
                   hrr_vector
            FROM facts
            {where}
            """,
            params,
        ).fetchall()

        if not rows:
            query = " ".join(entities)
            return self.search(query, category=category, limit=limit)

        # 通过每个实体在结构上存在的程度对每个事实进行评分。
        # 只有所有实体都有结构存在的事实才会得到高分
        # （通过 min 实现 AND 语义，OR 会使用 mean/max）。
        role_content = hrr.encode_atom("__hrr_role_content__", self.hrr_dim)

        scored = []
        for row in rows:
            fact = dict(row)
            fact_vec = hrr.bytes_to_phases(fact.pop("hrr_vector"))

            entity_scores = []
            for probe_key in entity_residuals:
                residual = hrr.unbind(fact_vec, probe_key)
                sim = hrr.similarity(residual, role_content)
                entity_scores.append(sim)

            min_sim = min(entity_scores)
            fact["score"] = (min_sim + 1.0) / 2.0 * fact["trust_score"]
            scored.append(fact)

        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:limit]

    def contradict(
        self,
        category: str | None = None,
        threshold: float = 0.3,
        limit: int = 10,
    ) -> list[dict]:
        """
        通过实体重叠 + 内容分歧发现可能矛盾的事实。

        当两个事实共享实体（相同的主题）但具有低内容向量相似度（不同的主张）时，它们是矛盾的。
        这是自动化的记忆卫生——没有其他记忆系统能做到这一点。

        返回成对事实的列表，带有矛盾分数。
        如果 numpy 不可用则回退到空列表。
        """
        if not hrr._HAS_NUMPY:
            return []

        conn = self.store._conn

        # 获取所有带有向量及其链接实体的事实
        where = "WHERE f.hrr_vector IS NOT NULL"
        params: list = []
        if category:
            where += " AND f.category = ?"
            params.append(category)

        rows = conn.execute(
            f"""
            SELECT f.fact_id, f.content, f.category, f.tags, f.trust_score,
                   f.created_at, f.updated_at, f.hrr_vector
            FROM facts f
            {where}
            """,
            params,
        ).fetchall()

        if len(rows) < 2:
            return []

        # 防止大型事实存储上的 O(n²) 爆炸。
        # 在 500 个事实时，大约 125K 比较——可以接受。
        # 超过这个，只检查最近更新的事实。
        _MAX_CONTRADICT_FACTS = 500
        if len(rows) > _MAX_CONTRADICT_FACTS:
            rows = sorted(rows, key=lambda r: r["updated_at"] or r["created_at"], reverse=True)
            rows = rows[:_MAX_CONTRADICT_FACTS]

        # 为每个事实构建实体集合
        fact_entities: dict[int, set[str]] = {}
        for row in rows:
            fid = row["fact_id"]
            entity_rows = conn.execute(
                """
                SELECT e.name FROM entities e
                JOIN fact_entities fe ON fe.entity_id = e.entity_id
                WHERE fe.fact_id = ?
                """,
                (fid,),
            ).fetchall()
            fact_entities[fid] = {r["name"].lower() for r in entity_rows}

        # 比较所有对：高实体重叠 + 低内容相似度 = 矛盾
        facts = [dict(r) for r in rows]
        contradictions = []

        for i in range(len(facts)):
            for j in range(i + 1, len(facts)):
                f1, f2 = facts[i], facts[j]
                ents1 = fact_entities.get(f1["fact_id"], set())
                ents2 = fact_entities.get(f2["fact_id"], set())

                if not ents1 or not ents2:
                    continue

                # 实体重叠（Jaccard）
                entity_overlap = len(ents1 & ents2) / len(ents1 | ents2) if (ents1 | ents2) else 0.0

                if entity_overlap < 0.3:
                    continue  # 实体重叠不足，不构成矛盾

                # 通过 HRR 向量计算内容相似度
                v1 = hrr.bytes_to_phases(f1["hrr_vector"])
                v2 = hrr.bytes_to_phases(f2["hrr_vector"])
                content_sim = hrr.similarity(v1, v2)

                # 高实体重叠 + 低内容相似度 = 潜在矛盾
                # contradiction_score：越高越矛盾
                contradiction_score = entity_overlap * (1.0 - (content_sim + 1.0) / 2.0)

                if contradiction_score >= threshold:
                    # 从输出中移除 hrr_vector（不可 JSON 序列化）
                    f1_clean = {k: v for k, v in f1.items() if k != "hrr_vector"}
                    f2_clean = {k: v for k, v in f2.items() if k != "hrr_vector"}
                    contradictions.append({
                        "fact_a": f1_clean,
                        "fact_b": f2_clean,
                        "entity_overlap": round(entity_overlap, 3),
                        "content_similarity": round(content_sim, 3),
                        "contradiction_score": round(contradiction_score, 3),
                        "shared_entities": sorted(ents1 & ents2),
                    })

        contradictions.sort(key=lambda x: x["contradiction_score"], reverse=True)
        return contradictions[:limit]

    def _score_facts_by_vector(
        self,
        target_vec: "np.ndarray",
        category: str | None = None,
        limit: int = 10,
    ) -> list[dict]:
        """通过与目标向量的相似度对事实进行评分。"""
        conn = self.store._conn

        where = "WHERE hrr_vector IS NOT NULL"
        params: list = []
        if category:
            where += " AND category = ?"
            params.append(category)

        rows = conn.execute(
            f"""
            SELECT fact_id, content, category, tags, trust_score,
                   retrieval_count, helpful_count, created_at, updated_at,
                   hrr_vector
            FROM facts
            {where}
            """,
            params,
        ).fetchall()

        scored = []
        for row in rows:
            fact = dict(row)
            fact_vec = hrr.bytes_to_phases(fact.pop("hrr_vector"))
            sim = hrr.similarity(target_vec, fact_vec)
            fact["score"] = (sim + 1.0) / 2.0 * fact["trust_score"]
            scored.append(fact)

        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:limit]

    def _fts_candidates(
        self,
        query: str,
        category: str | None,
        min_trust: float,
        limit: int,
    ) -> list[dict]:
        """
        从存储中获取原始 FTS5 候选。

        直接使用存储的数据库连接进行带排名评分的 FTS5 MATCH。
        将 FTS5 排名规范化到 [0, 1] 范围。
        """
        conn = self.store._conn

        # 构建查询——FTS5 排名是负数（越低匹配越好）
        # 我们需要将 facts_fts 与 facts 连接以获取所有列
        params: list = []
        where_clauses = ["facts_fts MATCH ?"]
        params.append(query)

        if category:
            where_clauses.append("f.category = ?")
            params.append(category)

        where_clauses.append("f.trust_score >= ?")
        params.append(min_trust)

        where_sql = " AND ".join(where_clauses)

        sql = f"""
            SELECT f.*, facts_fts.rank as fts_rank_raw
            FROM facts_fts
            JOIN facts f ON f.fact_id = facts_fts.rowid
            WHERE {where_sql}
            ORDER BY facts_fts.rank
            LIMIT ?
        """
        params.append(limit)

        try:
            rows = conn.execute(sql, params).fetchall()
        except Exception:
            # FTS5 MATCH 可能在格式错误的查询上失败——回退到空
            return []

        if not rows:
            return []

        # 规范化 FTS5 排名：排名是负数，越低越好
        # 转换为 [0, 1] 范围内的正分数
        raw_ranks = [abs(row["fts_rank_raw"]) for row in rows]
        max_rank = max(raw_ranks) if raw_ranks else 1.0
        max_rank = max(max_rank, 1e-6)  # 避免除以零

        results = []
        for row, raw_rank in zip(rows, raw_ranks):
            fact = dict(row)
            fact.pop("fts_rank_raw", None)
            fact["fts_rank"] = raw_rank / max_rank  # 规范化到 [0, 1]
            results.append(fact)

        return results

    @staticmethod
    def _tokenize(text: str) -> set[str]:
        """
        简单的小写空格分词。

        去除常见标点符号。没有词干/词形还原（第一阶段）。
        """
        if not text:
            return set()
        # 按空格分割，小写，去除标点
        tokens = set()
        for word in text.lower().split():
            cleaned = word.strip(".,;:!?\"'()[]{}#@<>")
            if cleaned:
                tokens.add(cleaned)
        return tokens

    @staticmethod
    def _jaccard_similarity(set_a: set, set_b: set) -> float:
        """Jaccard 相似度系数：|A ∩ B| / |A ∪ B|。"""
        if not set_a or not set_b:
            return 0.0
        intersection = len(set_a & set_b)
        union = len(set_a | set_b)
        return intersection / union if union > 0 else 0.0

    def _temporal_decay(self, timestamp_str: str | None) -> float:
        """
        指数衰减：0.5^(age_days / half_life_days)。

        如果禁用衰减或缺少时间戳，返回 1.0。
        """
        if not self.half_life or not timestamp_str:
            return 1.0

        try:
            if isinstance(timestamp_str, str):
                # 从 SQLite 解析 ISO 格式时间戳
                ts = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
            else:
                ts = timestamp_str

            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)

            age_days = (datetime.now(timezone.utc) - ts).total_seconds() / 86400
            if age_days < 0:
                return 1.0

            return math.pow(0.5, age_days / self.half_life)
        except (ValueError, TypeError):
            return 1.0
