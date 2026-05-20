"""hermes-memory-store — 使用 MemoryProvider 接口的全息记忆插件。

注册为 MemoryProvider 插件，为代理提供结构化事实存储，
具有实体检索、信任评分和基于 HRR 的组合检索。

原作者 dusterbloom 的插件（PR #2351），适配到 MemoryProvider ABC。

$HERMES_HOME/config.yaml 中的配置（配置文件范围）：
  plugins:
    hermes-memory-store:
      db_path: $HERMES_HOME/memory_store.db   # 省略以使用默认值
      auto_extract: false
      default_trust: 0.5
      min_trust_threshold: 0.3
      temporal_decay_half_life: 0
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List

from agent.memory_provider import MemoryProvider
from tools.registry import tool_error
from .store import MemoryStore
from .retrieval import FactRetriever
from hermes_cli.config import cfg_get

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 工具模式（与原始 PR 保持不变）
# ---------------------------------------------------------------------------

FACT_STORE_SCHEMA = {
    "name": "fact_store",
    "description": (
        "具有代数推理的深层结构化记忆。"
        "与 memory 工具一起使用——memory 用于永久上下文，"
        "fact_store 用于深层回忆和组合查询。\n\n"
        "操作（从简单到强大）：\n"
        "• add — 存储你希望记住的关于用户的事实。\n"
        "• search — 关键词查找（'editor config'、'deploy process'）。\n"
        "• probe — 实体检索：关于一个人/事物的所有事实。\n"
        "• related — 什么与实体相连？结构相邻性。\n"
        "• reason — 组合性：与多个实体同时相连的事实。\n"
        "• contradict — 记忆卫生：查找做出矛盾主张的事实。\n"
        "• update/remove/list — CRUD 操作。\n\n"
        "重要提示：在回答关于用户的问题之前，始终先 probe 或 reason。"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["add", "search", "probe", "related", "reason", "contradict", "update", "remove", "list"],
            },
            "content": {"type": "string", "description": "事实内容（'add' 必需）。"},
            "query": {"type": "string", "description": "搜索查询（'search' 必需）。"},
            "entity": {"type": "string", "description": "'probe'/'related' 的实体名称。"},
            "entities": {"type": "array", "items": {"type": "string"}, "description": "'reason' 的实体名称。"},
            "fact_id": {"type": "integer", "description": "'update'/'remove' 的事实 ID。"},
            "category": {"type": "string", "enum": ["user_pref", "project", "tool", "general"]},
            "tags": {"type": "string", "description": "逗号分隔的标签。"},
            "trust_delta": {"type": "number", "description": "'update' 的信任调整。"},
            "min_trust": {"type": "number", "description": "最小信任过滤（默认值：0.3）。"},
            "limit": {"type": "integer", "description": "最大结果数（默认值：10）。"},
        },
        "required": ["action"],
    },
}

FACT_FEEDBACK_SCHEMA = {
    "name": "fact_feedback",
    "description": (
        "使用事实后对其评分。如果准确，标记'helpful'；如果过时，标记'unhelpful'。"
        "这训练记忆——好事实上升，坏事实下沉。"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["helpful", "unhelpful"]},
            "fact_id": {"type": "integer", "description": "要评分的事实 ID。"},
        },
        "required": ["action", "fact_id"],
    },
}


# ---------------------------------------------------------------------------
# 配置
# ---------------------------------------------------------------------------

def _load_plugin_config() -> dict:
    """从 config.yaml 加载插件配置。"""
    from hermes_constants import get_hermes_home
    config_path = get_hermes_home() / "config.yaml"
    if not config_path.exists():
        return {}
    try:
        import yaml
        with open(config_path, encoding="utf-8-sig") as f:
            all_config = yaml.safe_load(f) or {}
        return cfg_get(all_config, "plugins", "hermes-memory-store", default={}) or {}
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# MemoryProvider 实现
# ---------------------------------------------------------------------------

class HolographicMemoryProvider(MemoryProvider):
    """具有结构化事实、实体检索和 HRR 检索的全息记忆。"""

    def __init__(self, config: dict | None = None):
        """初始化记忆提供程序，可选配置。"""
        self._config = config or _load_plugin_config()
        self._store = None
        self._retriever = None
        self._min_trust = float(self._config.get("min_trust_threshold", 0.3))

    @property
    def name(self) -> str:
        """此提供程序的唯一名称。"""
        return "holographic"

    def is_available(self) -> bool:
        """检查此提供程序是否可用（SQLite 始终可用，numpy 是可选的）。"""
        return True

    def save_config(self, values, hermes_home):
        """将配置写入 config.yaml 的 plugins.hermes-memory-store 下。"""
        from pathlib import Path
        config_path = Path(hermes_home) / "config.yaml"
        try:
            import yaml
            existing = {}
            if config_path.exists():
                with open(config_path, encoding="utf-8-sig") as f:
                    existing = yaml.safe_load(f) or {}
            existing.setdefault("plugins", {})
            existing["plugins"]["hermes-memory-store"] = values
            with open(config_path, "w", encoding="utf-8") as f:
                yaml.dump(existing, f, default_flow_style=False)
        except Exception:
            pass

    def get_config_schema(self):
        """获取插件的配置模式（用于 CLI 配置 UI）。"""
        from hermes_constants import display_hermes_home
        _default_db = f"{display_hermes_home()}/memory_store.db"
        return [
            {"key": "db_path", "description": "SQLite 数据库路径", "default": _default_db},
            {"key": "auto_extract", "description": "会话结束时自动提取事实", "default": "false", "choices": ["true", "false"]},
            {"key": "default_trust", "description": "新事实的默认信任分数", "default": "0.5"},
            {"key": "hrr_dim", "description": "HRR 向量维度", "default": "1024"},
        ]

    def initialize(self, session_id: str, **kwargs) -> None:
        """为会话初始化记忆存储和检索器。"""
        from hermes_constants import get_hermes_home
        _hermes_home = str(get_hermes_home())
        _default_db = _hermes_home + "/memory_store.db"
        db_path = self._config.get("db_path", _default_db)
        # 展开用户提供的路径中的 $HERMES_HOME，以便像
        # "$HERMES_HOME/memory_store.db" 或 "~/.hermes/memory_store.db" 这样的配置值
        # 都解析到活动配置文件的目录。
        if isinstance(db_path, str):
            db_path = db_path.replace("$HERMES_HOME", _hermes_home)
            db_path = db_path.replace("${HERMES_HOME}", _hermes_home)
        default_trust = float(self._config.get("default_trust", 0.5))
        hrr_dim = int(self._config.get("hrr_dim", 1024))
        hrr_weight = float(self._config.get("hrr_weight", 0.3))
        temporal_decay = int(self._config.get("temporal_decay_half_life", 0))

        self._store = MemoryStore(db_path=db_path, default_trust=default_trust, hrr_dim=hrr_dim)
        self._retriever = FactRetriever(
            store=self._store,
            temporal_decay_half_life=temporal_decay,
            hrr_weight=hrr_weight,
            hrr_dim=hrr_dim,
        )
        self._session_id = session_id

    def system_prompt_block(self) -> str:
        """生成系统提示块，描述记忆能力。"""
        if not self._store:
            return ""
        try:
            total = self._store._conn.execute(
                "SELECT COUNT(*) FROM facts"
            ).fetchone()[0]
        except Exception:
            total = 0
        if total == 0:
            return (
                "# 全息记忆\n"
                "活动。空事实存储——主动添加你希望记住的关于用户的事实。\n"
                "使用 fact_store(action='add') 来存储关于人物、项目、偏好、决策的持久结构化事实。\n"
                "使用 fact_feedback 在使用事实后对其评分（训练信任分数）。"
            )
        return (
            f"# 全息记忆\n"
            f"活动。{total} 个事实存储，具有实体检索和信任评分。\n"
            f"使用 fact_store 来搜索、探测实体、跨实体推理或添加事实。\n"
            f"使用 fact_feedback 在使用事实后对其评分（训练信任分数）。"
        )

    def prefetch(self, query: str, *, session_id: str = "") -> str:
        """预取与查询相关的事实，用于注入到上下文中。"""
        if not self._retriever or not query:
            return ""
        try:
            results = self._retriever.search(query, min_trust=self._min_trust, limit=5)
            if not results:
                return ""
            lines = []
            for r in results:
                trust = r.get("trust_score", r.get("trust", 0))
                lines.append(f"- [{trust:.1f}] {r.get('content', '')}")
            return "## 全息记忆\n" + "\n".join(lines)
        except Exception as e:
            logger.debug("Holographic prefetch failed: %s", e)
            return ""

    def sync_turn(self, user_content: str, assistant_content: str, *, session_id: str = "") -> None:
        """同步对话轮次（全息记忆通过工具存储显式事实，不是自动同步）。"""
        # 全息记忆通过工具存储显式事实，不是自动同步。
        # on_session_end 钩子在配置后处理自动提取。
        pass

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        """获取此记忆提供程序的工具模式列表。"""
        return [FACT_STORE_SCHEMA, FACT_FEEDBACK_SCHEMA]

    def handle_tool_call(self, tool_name: str, args: Dict[str, Any], **kwargs) -> str:
        """处理来自代理的工具调用。"""
        if tool_name == "fact_store":
            return self._handle_fact_store(args)
        elif tool_name == "fact_feedback":
            return self._handle_fact_feedback(args)
        return tool_error(f"Unknown tool: {tool_name}")

    def on_session_end(self, messages: List[Dict[str, Any]]) -> None:
        """会话结束钩子——如果配置，则自动提取事实。"""
        if not self._config.get("auto_extract", False):
            return
        if not self._store or not messages:
            return
        self._auto_extract_facts(messages)

    def on_memory_write(self, action: str, target: str, content: str) -> None:
        """镜像内置记忆写入为事实。"""
        if action == "add" and self._store and content:
            try:
                category = "user_pref" if target == "user" else "general"
                self._store.add_fact(content, category=category)
            except Exception as e:
                logger.debug("Holographic memory_write mirror failed: %s", e)

    def shutdown(self) -> None:
        """关闭记忆存储并释放资源。"""
        self._store = None
        self._retriever = None

    # -- 工具处理程序 -------------------------------------------------------

    def _handle_fact_store(self, args: dict) -> str:
        """处理 fact_store 工具调用。"""
        try:
            action = args["action"]
            store = self._store
            retriever = self._retriever

            if action == "add":
                fact_id = store.add_fact(
                    args["content"],
                    category=args.get("category", "general"),
                    tags=args.get("tags", ""),
                )
                return json.dumps({"fact_id": fact_id, "status": "added"})

            elif action == "search":
                results = retriever.search(
                    args["query"],
                    category=args.get("category"),
                    min_trust=float(args.get("min_trust", self._min_trust)),
                    limit=int(args.get("limit", 10)),
                )
                return json.dumps({"results": results, "count": len(results)})

            elif action == "probe":
                results = retriever.probe(
                    args["entity"],
                    category=args.get("category"),
                    limit=int(args.get("limit", 10)),
                )
                return json.dumps({"results": results, "count": len(results)})

            elif action == "related":
                results = retriever.related(
                    args["entity"],
                    category=args.get("category"),
                    limit=int(args.get("limit", 10)),
                )
                return json.dumps({"results": results, "count": len(results)})

            elif action == "reason":
                entities = args.get("entities", [])
                if not entities:
                    return tool_error("reason requires 'entities' list")
                results = retriever.reason(
                    entities,
                    category=args.get("category"),
                    limit=int(args.get("limit", 10)),
                )
                return json.dumps({"results": results, "count": len(results)})

            elif action == "contradict":
                results = retriever.contradict(
                    category=args.get("category"),
                    limit=int(args.get("limit", 10)),
                )
                return json.dumps({"results": results, "count": len(results)})

            elif action == "update":
                updated = store.update_fact(
                    int(args["fact_id"]),
                    content=args.get("content"),
                    trust_delta=float(args["trust_delta"]) if "trust_delta" in args else None,
                    tags=args.get("tags"),
                    category=args.get("category"),
                )
                return json.dumps({"updated": updated})

            elif action == "remove":
                removed = store.remove_fact(int(args["fact_id"]))
                return json.dumps({"removed": removed})

            elif action == "list":
                facts = store.list_facts(
                    category=args.get("category"),
                    min_trust=float(args.get("min_trust", 0.0)),
                    limit=int(args.get("limit", 10)),
                )
                return json.dumps({"facts": facts, "count": len(facts)})

            else:
                return tool_error(f"Unknown action: {action}")

        except KeyError as exc:
            return tool_error(f"Missing required argument: {exc}")
        except Exception as exc:
            return tool_error(str(exc))

    def _handle_fact_feedback(self, args: dict) -> str:
        """处理 fact_feedback 工具调用。"""
        try:
            fact_id = int(args["fact_id"])
            helpful = args["action"] == "helpful"
            result = self._store.record_feedback(fact_id, helpful=helpful)
            return json.dumps(result)
        except KeyError as exc:
            return tool_error(f"Missing required argument: {exc}")
        except Exception as exc:
            return tool_error(str(exc))

    # -- 自动提取（on_session_end）------------------------------------

    def _auto_extract_facts(self, messages: list) -> None:
        """从对话消息中自动提取事实（在会话结束时）。"""
        _PREF_PATTERNS = [
            re.compile(r'\bI\s+(?:prefer|like|love|use|want|need)\s+(.+)', re.IGNORECASE),
            re.compile(r'\bmy\s+(?:favorite|preferred|default)\s+\w+\s+is\s+(.+)', re.IGNORECASE),
            re.compile(r'\bI\s+(?:always|never|usually)\s+(.+)', re.IGNORECASE),
        ]
        _DECISION_PATTERNS = [
            re.compile(r'\bwe\s+(?:decided|agreed|chose)\s+(?:to\s+)?(.+)', re.IGNORECASE),
            re.compile(r'\bthe\s+project\s+(?:uses|needs|requires)\s+(.+)', re.IGNORECASE),
        ]

        extracted = 0
        for msg in messages:
            if msg.get("role") != "user":
                continue
            content = msg.get("content", "")
            if not isinstance(content, str) or len(content) < 10:
                continue

            for pattern in _PREF_PATTERNS:
                if pattern.search(content):
                    try:
                        self._store.add_fact(content[:400], category="user_pref")
                        extracted += 1
                    except Exception:
                        pass
                    break

            for pattern in _DECISION_PATTERNS:
                if pattern.search(content):
                    try:
                        self._store.add_fact(content[:400], category="project")
                        extracted += 1
                    except Exception:
                        pass
                    break

        if extracted:
            logger.info("Auto-extracted %d facts from conversation", extracted)


# ---------------------------------------------------------------------------
# 插件入口点
# ---------------------------------------------------------------------------

def register(ctx) -> None:
    """向插件系统注册全息记忆提供程序。"""
    config = _load_plugin_config()
    provider = HolographicMemoryProvider(config=config)
    ctx.register_memory_provider(provider)
