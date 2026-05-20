"""
策展器——后台技能维护协调器。

策展器是一个辅助模型任务，定期审查代理创建的技能并维护集合。
它在不活动时触发（无 cron 守护进程）：当代理空闲且上次策展器运行
早于 ``interval_hours`` 时，``maybe_run_curator()`` 会派生出一个
分叉的 AIAgent 来进行审查。

职责：
  - 根据派生的技能活动时间戳自动转换生命周期状态
  - 派生出后台审查代理，可以通过 skill_manage 固定/归档/合并/补丁代理创建的技能
  - 在 .curator_state 中持久化策展器状态（last_run_at、paused 等）

严格不变量：
  - 只接触代理创建的技能（请参阅 tools/skill_usage.is_agent_created）
  - 永远不自动删除——只归档。归档是可恢复的。
  - 固定的技能绕过所有自动转换
  - 使用辅助客户端；永远不接触主会话的提示缓存
"""

from __future__ import annotations

import json
import logging
import os
import re
import tempfile
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, NamedTuple, Optional, Set

from hermes_constants import get_hermes_home
from tools import skill_usage

logger = logging.getLogger(__name__)


def _strip_aux_credential(value: Any) -> Optional[str]:
    """去除辅助凭据值的空白，并处理 None 值。"""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


class _ReviewRuntimeBinding(NamedTuple):
    """策展器审查分叉的提供商/模型以及可选的每个槽覆盖。"""
    provider: str
    model: str
    explicit_api_key: Optional[str]
    explicit_base_url: Optional[str]


DEFAULT_INTERVAL_HOURS = 24 * 7  # 7 天
DEFAULT_MIN_IDLE_HOURS = 2
DEFAULT_STALE_AFTER_DAYS = 30
DEFAULT_ARCHIVE_AFTER_DAYS = 90


# ---------------------------------------------------------------------------
# .curator_state——持久化调度器 + 状态
# ---------------------------------------------------------------------------

def _state_file() -> Path:
    """返回 .curator_state 文件的路径。"""
    return get_hermes_home() / "skills" / ".curator_state"


def _default_state() -> Dict[str, Any]:
    """返回默认的策展器状态字典。"""
    return {
        "last_run_at": None,
        "last_run_duration_seconds": None,
        "last_run_summary": None,
        "last_run_summary_shown_at": None,
        "last_report_path": None,
        "paused": False,
        "run_count": 0,
    }


def load_state() -> Dict[str, Any]:
    """
    加载策展器状态。

    如果文件不存在或损坏，返回默认状态。
    """
    path = _state_file()
    if not path.exists():
        return _default_state()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            base = _default_state()
            base.update({k: v for k, v in data.items() if k in base or k.startswith("_")})
            return base
    except (OSError, json.JSONDecodeError) as e:
        logger.debug("Failed to read curator state: %s", e)
    return _default_state()


def save_state(data: Dict[str, Any]) -> None:
    """
    保存策展器状态。

    原子写入：先写入临时文件，然后重命名以避免损坏。
    """
    path = _state_file()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".curator_state_", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, sort_keys=True, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, path)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
    except Exception as e:
        logger.debug("Failed to save curator state: %s", e, exc_info=True)


def set_paused(paused: bool) -> None:
    """设置策展器的暂停状态。"""
    state = load_state()
    state["paused"] = bool(paused)
    save_state(state)


def is_paused() -> bool:
    """检查策展器是否暂停。"""
    return bool(load_state().get("paused"))


# ---------------------------------------------------------------------------
# 配置访问
# ---------------------------------------------------------------------------

def _load_config() -> Dict[str, Any]:
    """
    从 ~/.hermes/config.yaml 读取 curator.* 配置。容忍文件缺失。
    """
    try:
        from hermes_cli.config import load_config
        cfg = load_config()
    except Exception as e:
        logger.debug("Failed to load config for curator: %s", e)
        return {}
    if not isinstance(cfg, dict):
        return {}
    cur = cfg.get("curator") or {}
    if not isinstance(cur, dict):
        return {}
    return cur


def is_enabled() -> bool:
    """没有配置说明否则时默认启用。"""
    cfg = _load_config()
    return bool(cfg.get("enabled", True))


def get_interval_hours() -> int:
    """获取策展运行间隔（小时）。"""
    cfg = _load_config()
    try:
        return int(cfg.get("interval_hours", DEFAULT_INTERVAL_HOURS))
    except (TypeError, ValueError):
        return DEFAULT_INTERVAL_HOURS


def get_min_idle_hours() -> float:
    """获取触发策展所需的最小空闲时间（小时）。"""
    cfg = _load_config()
    try:
        return float(cfg.get("min_idle_hours", DEFAULT_MIN_IDLE_HOURS))
    except (TypeError, ValueError):
        return DEFAULT_MIN_IDLE_HOURS


def get_stale_after_days() -> int:
    """获取标记为过时的天数阈值。"""
    cfg = _load_config()
    try:
        return int(cfg.get("stale_after_days", DEFAULT_STALE_AFTER_DAYS))
    except (TypeError, ValueError):
        return DEFAULT_STALE_AFTER_DAYS


def get_archive_after_days() -> int:
    """获取归档的天数阈值。"""
    cfg = _load_config()
    try:
        return int(cfg.get("archive_after_days", DEFAULT_ARCHIVE_AFTER_DAYS))
    except (TypeError, ValueError):
        return DEFAULT_ARCHIVE_AFTER_DAYS


# ---------------------------------------------------------------------------
# 空闲/间隔检查
# ---------------------------------------------------------------------------

def _parse_iso(ts: Optional[str]) -> Optional[datetime]:
    """解析 ISO 格式时间戳字符串，失败时返回 None。"""
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts)
    except (TypeError, ValueError):
        return None


def should_run_now(now: Optional[datetime] = None) -> bool:
    """
    如果策展器现在应该运行则返回 True。

    门槛：
      - curator.enabled == True
      - 未暂停
      - last_run_at 存在且早于 interval_hours

    首次运行行为：当没有 ``last_run_at`` 时（全新安装，或
    安装早于策展器），我们不会立即运行。策展器设计为
    在至少 ``interval_hours``（默认为 7 天）的技能活动后运行，
    而不是在 ``hermes update`` 后的第一个后台 tick 上运行。
    首次观察时，我们将 ``last_run_at`` 设定为"现在"，
    并将第一次真正的运行推迟一个完整的间隔。
    希望更早运行的用户总是可以显式调用
    ``hermes curator run``（带或不带 ``--dry-run``）——该路径绕过此门槛。

    空闲检查（min_idle_hours）在知道代理是否正在运行的调用站点应用——
    这里我们只执行静态门槛。
    """
    if not is_enabled():
        return False
    if is_paused():
        return False

    state = load_state()
    last = _parse_iso(state.get("last_run_at"))
    if last is None:
        # 从未运行过。设定状态以便我们等待一个完整的间隔后再进行第一次真正的运行。
        # 仅报告；不要在更新后第一次网关 tick 时自动改变库。
        if now is None:
            now = datetime.now(timezone.utc)
        try:
            state["last_run_at"] = now.isoformat()
            state["last_run_summary"] = (
                "deferred first run — curator seeded, will run after one "
                "interval; use `hermes curator run --dry-run` to preview now"
            )
            save_state(state)
        except Exception as e:  # pragma: no cover — 尽最大努力持久化
            logger.debug("Failed to seed curator last_run_at: %s", e)
        return False

    if now is None:
        now = datetime.now(timezone.utc)
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    interval = timedelta(hours=get_interval_hours())
    return (now - last) >= interval


# ---------------------------------------------------------------------------
# 自动状态转换（纯函数，无 LLM）
# ---------------------------------------------------------------------------

def apply_automatic_transitions(now: Optional[datetime] = None) -> Dict[str, int]:
    """
    遍历每个代理创建的技能，并根据最新的真实活动时间戳移动 active/stale/archived。
    固定的技能永远不被接触。

    返回描述变化的计数字典。
    """
    from tools import skill_usage as _u

    if now is None:
        now = datetime.now(timezone.utc)
    stale_cutoff = now - timedelta(days=get_stale_after_days())
    archive_cutoff = now - timedelta(days=get_archive_after_days())

    counts = {"marked_stale": 0, "archived": 0, "reactivated": 0, "checked": 0}

    for row in _u.agent_created_report():
        counts["checked"] += 1
        name = row["name"]
        if row.get("pinned"):
            continue

        last_activity = _parse_iso(row.get("last_activity_at"))
        # 如果从未活动，将 created_at 作为锚点，这样新技能不会立即归档自己。
        anchor = last_activity or _parse_iso(row.get("created_at")) or now
        if anchor.tzinfo is None:
            anchor = anchor.replace(tzinfo=timezone.utc)

        current = row.get("state", _u.STATE_ACTIVE)

        if anchor <= archive_cutoff and current != _u.STATE_ARCHIVED:
            ok, _msg = _u.archive_skill(name)
            if ok:
                counts["archived"] += 1
        elif anchor <= stale_cutoff and current == _u.STATE_ACTIVE:
            _u.set_state(name, _u.STALE_STALE)
            counts["marked_stale"] += 1
        elif anchor > stale_cutoff and current == _u.STATE_STALE:
            # 技能在被标记为过时时又被使用了——重新激活。
            _u.set_state(name, _u.STATE_ACTIVE)
            counts["reactivated"] += 1

    return counts


# ---------------------------------------------------------------------------
# 分叉代理的审查提示
# ---------------------------------------------------------------------------

CURATOR_DRY_RUN_BANNER = """
═══════════════════════════════════════════════════════════════
DRY-RUN — 仅报告。不要改变技能库。
═══════════════════════════════════════════════════════════════

这是预览运行。完全按照以下说明操作，除了：

  • 不要调用 skill_manage 使用 action=patch、create、delete、write_file 或 remove_file。
  • 不要调用 terminal 将技能目录移动到 .archive/ 中。
  • 不要调用 terminal 在 ~/.hermes/skills/ 下移动、复制、删除或重写任何文件。
  • skills_list 和 skill_view 没问题——尽情阅读。

你的输出就是交付物。生成与真实运行时完全相同的
人类可读摘要和结构化 YAML 块——但描述你会采取的行动，
而不是你已采取的行动。下游审阅者将阅读报告并决定是否
批准使用 `hermes curator run`（不带标志）的真实运行。

如果你不小心采取了变更操作，请在摘要中明确说明，以便审阅者可以恢复它。
═══════════════════════════════════════════════════════════════
"""


CURATOR_REVIEW_PROMPT = """
你作为 Hermes 的后台技能策展器运行。这是伞形构建合并通道，
不是被动审计，也不是重复项查找器。

技能库的目标是类级指令和经验知识的库。
数百个狭义技能的集合，每个都捕获一个会话的特定 bug，
是库的失败——不是特性。代理搜索技能时匹配描述，
而不是精确名称；一个带有标记子部分的广泛伞形技能在可发现性方面胜过五个狭义的兄弟技能，
而不是相反。

正确的目标形状是类级技能，具有丰富的 SKILL.md 主体 + references/、templates/、
和 scripts/ 子文件用于会话特定细节——不是一个会话一个技能的微条目。

硬性规则——不要违反：
1. 不要接触捆绑或从集线器安装的技能。下面的候选列表已过滤为仅代理创建的技能。
2. 不要删除任何技能。归档（将技能目录移动到 ~/.hermes/skills/.archive/）是最大的破坏性操作。
   归档是可恢复的；删除不是。
3. 不要接触显示为 pinned=yes 的技能。完全跳过它们。
4. 不要使用使用计数作为跳过合并的理由。计数器是新的，通常大部分为零。根据内容判断重叠，
   而不是使用计数。'use=0' 不是技能有价值的证据；这是两者都没有的证据。
5. 不要以'每个技能都有不同的触发器'为由拒绝合并。成对的区别是错误的标准。
   正确的标准是：'人类维护者会将此写成 N 个单独的技能，还是写成一个带有 N 个标记子部分的技能？'
   当答案是后者时，合并。

如何工作——不可选：
1. 扫描完整候选列表。识别前缀聚类（共享第一个单词或领域关键词的技能）。
   你可能会发现的示例：hermes-config-*、hermes-dashboard-*、gateway-*、codex-*、
   ollama-*、anthropic-*、gemini-*、mcp-*、salvage-*、pr-*、competitor-*、python-*、security-* 等。
   预计有 10-25 个聚类。
2. 对于每个有 2+ 成员的聚类，不要问'这些成对重叠吗？'——而是问'这些技能都服务的伞形类是什么？
   维护者会命名那个类并为它写一个技能吗？'如果是，选择（或创建）伞形并吸收兄弟技能。
3. 三种合并方式——为每个聚类使用正确的一种：
   a. 合并到现有伞形——聚类中的一个技能已经足够广泛成为伞形（例如：PR 审查聚类的 `pr-triage-salvage`）。
      补丁它为每个兄弟的独特洞察添加标记部分，然后归档兄弟技能。
   b. 创建新的伞形 SKILL.md——没有现有成员足够广泛。使用 skill_manage action=create
      写一个新的类级技能，其 SKILL.md 涵盖共享工作流程并有简短的标记子部分。归档现在被吸收的狭义兄弟技能。
   c. 降级为 references/templates/scripts——兄弟技能有狭义但有价值的会话特定内容。
      将其移动到伞形的适当支持目录中：
        • references/<topic>.md 用于会话特定细节或浓缩知识库（引用的研究、API 文档摘录、领域说明、
          提供商怪癖、复现食谱）
        • templates/<name>.<ext> 用于旨在被复制和修改的启动文件
        • scripts/<name>.<ext> 用于静态可重运行操作（验证脚本、夹具生成器、探测器）
      然后归档旧的兄弟技能。使用 `terminal` 与 `mkdir -p ~/.hermes/skills/<umbrella>/references/ && mv ... <umbrella>/references/<topic>.md`
      （或 templates/ / scripts/）。
4. 还要标记名称过于狭窄的技能（包含 PR 编号、功能代号、特定错误字符串、
   '审计'/'诊断'/'打捞'会话工件）。这些几乎总是属于类级伞形下的子部分或支持文件。
5. 迭代。一轮合并后，扫描剩余集并寻找下一个伞形机会。不要在 3 次合并后停止。

你的工具集：
  • skills_list、skill_view——阅读当前格局
  • skill_manage action=patch——向伞形添加部分
  • skill_manage action=create——创建新的伞形 SKILL.md
  • skill_manage action=write_file——向现有技能添加 references/、templates/ 或 scripts/ 文件（技能必须已存在）
  • skill_manage action=delete——归档技能。当你将其内容合并到另一个技能时，必须传递 `absorbed_into=<umbrella>`，
    或者当你真正修剪时传递 `absorbed_into=""`。这驱动 cron 作业技能引用迁移——
    事后从你的 YAML 摘要猜测是脆弱的。
  • terminal——将兄弟技能移动到归档或将其内容移动到支持子文件

'保持'是一个合法的决定，仅当技能已经是类级伞形并且没有提议的合并会改善可发现性时。
'这很狭窄但与兄弟不同'不是保持的理由——这是作为子部分或支持文件移到伞形下的理由。

预期输出：真正的伞形化。处理每个明显的聚类。如果你以少于 10 个归档结束运行，
你停止得太早了——回去看看你留下的聚类。

完成后，写一个人类摘要和一个结构化的机器可读块，以便下游工具可以区分合并和修剪。
完全按以下格式：

## 结构化摘要（必填）
```yaml
consolidations:
  - from: <old-skill-name>
    into: <umbrella-skill-name>
    reason: <一个简短句子——为什么合并，而不只是'相似'>
prunings:
  - name: <skill-name>
    reason: <一个简短句子——为什么无合并目标地归档>
```

你移动到 .archive/ 的每个技能必须恰好出现在两个列表之一中。如果你将 X 合并到伞形 Y
（补丁 Y，向 Y 写 references 文件，或创建 Y 吸收 X 的内容），X 进入 `consolidations` 并带有 `into: Y`。
如果你归档 X 而没有吸收——真正过时、不相关或过时——X 进入 `prunings`。
如果没有则将列表留空（`consolidations: []`）。不要省略该块。该块在你的人类可读的
聚类处理、补丁制作和决定保持的摘要之后。
"""


# ---------------------------------------------------------------------------
# 每次运行报告——logs/curator/{YYYYMMDD-HHMMSS}/ 下的 run.json + REPORT.md
# ---------------------------------------------------------------------------

def _reports_root() -> Path:
    """
    策展运行报告写入的目录。

    位于配置文件感知的日志目录（``~/.hermes/logs/curator/``）下，
    与 ``agent.log`` 和 ``gateway.log`` 一起，以便任何寻找操作遥测的人都能找到它，
    而不是与用户在 ``~/.hermes/skills/`` 中的创作技能数据混在一起。

    ``ensure_hermes_home()`` 在每次 CLI 启动时预先创建此目录，
    并且 v22→v23 迁移为现有配置文件回填它，但我们仍然在这里 mkdir
    作为腰带和吊带，以便策展器甚至可以从绕过这两者的奇怪入口路径
    （例如：仅网关安装，裸库使用）工作。
    """
    root = get_hermes_home() / "logs" / "curator"
    try:
        root.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        logger.debug("Curator reports dir create failed: %s", e)
    return root


def _needle_in_path_component(needle: str, path: str) -> bool:
    """
    检查 *needle* 是否是 *path* 中的完整文件名词干或目录名。

    与简单的子字符串匹配不同，这避免了短技能名称嵌入在较长文件名中的误报
    （例如："api" 匹配 "references/api-design.md"）。
    连字符和下划线被规范化，以便 "open-webui-setup" 匹配 "open_webui_setup.md"。
    """
    norm_needle = needle.replace("-", "_")
    for part in path.replace("\\", "/").split("/"):
        if not part:
            continue
        stem = part.rsplit(".", 1)[0] if "." in part else part
        if stem.replace("-", "_") == norm_needle:
            return True
    return False


def _classify_removed_skills(
    removed: List[str],
    added: List[str],
    after_names: Set[str],
    tool_calls: List[Dict[str, Any]],
) -> Dict[str, List[Dict[str, Any]]]:
    """
    将 ``removed`` 拆分为合并与修剪。

    当策展器在此次运行中将其内容吸收到另一个技能（伞形）中时，删除的技能是"合并的"——
    内容仍然存在，只是名称不同。
    当策展器因过时而归档它而没有在其他地方保留其内容时，删除的技能是"修剪的"。

    启发式：扫描此次运行的 ``skill_manage`` 工具调用，并寻找其目标技能
    （``name`` 参数）不是已删除技能且其 ``file_path``/``file_content``/``content``
    参数引用已删除技能名称的 ``write_file``/``patch``/``create``/``edit`` 操作。
    这是教科书式的"吸收到伞形"信号。平局通过首次匹配解决（最早的工具调用获胜）。

    返回 ``{"consolidated": [{"name", "into", "evidence"}, ...], "pruned": [{"name"}, ...]}``。
    """
    consolidated: List[Dict[str, Any]] = []
    pruned: List[Dict[str, Any]] = []

    # 预解析工具调用：我们只关心 skill_manage。
    parsed_calls: List[Dict[str, Any]] = []
    for tc in tool_calls or []:
        if not isinstance(tc, dict):
            continue
        if tc.get("name") != "skill_manage":
            continue
        raw = tc.get("arguments") or ""
        # 参数可以是 JSON 字符串（标准）或字典（防御性）。
        args: Dict[str, Any] = {}
        if isinstance(raw, dict):
            args = raw
        elif isinstance(raw, str):
            try:
                args = json.loads(raw)
            except Exception:
                # 截断或格式错误——回退到原始字符串的子字符串匹配，以便我们仍然捕获常见情况。
                args = {"_raw": raw}
        if not isinstance(args, dict):
            continue
        parsed_calls.append(args)

    # 构建"目标"技能名称集合：此次运行后仍然存在的任何东西 + 此次运行中新添加的任何东西。
    # 被删除的技能从其中一个被引用是合并信号。
    destinations = set(after_names) | set(added or [])

    for name in removed:
        if not name:
            continue
        into: Optional[str] = None
        evidence: Optional[str] = None

        # 规范化我们将在路径/内容字符串中搜索的名称变体。
        needles = {name, name.replace("-", "_"), name.replace("_", "-")}

        for args in parsed_calls:
            target = args.get("name")
            if not isinstance(target, str) or not target:
                continue
            # 对被删除技能本身进行操作的调用不是合并证据。
            if target == name:
                continue
            # 目标必须是幸存或新创建的技能——否则我们指向一个不存在的技能。
            if target not in destinations:
                continue

            # 在 file_path / content / raw 中寻找被删除技能的名称。
            # 匹配策略因字段类型而异：
            #   file_path——needle 必须是完整路径组件（文件名词干或目录名），
            #     因此 "api" 不会错误匹配 "references/api-design.md"。
            #   content 字段——单词边界正则表达式，因此 "test" 不会错误匹配 "latest" 或 "testing"。
            haystacks: List[tuple[str, str]] = []
            for key in ("file_path", "file_content", "content", "new_string", "_raw"):
                v = args.get(key)
                if isinstance(v, str):
                    haystacks.append((key, v))
            hit = False
            for key, hay in haystacks:
                for needle in needles:
                    if not needle:
                        continue
                    if key == "file_path":
                        matched = _needle_in_path_component(needle, hay)
                    else:
                        matched = bool(
                            re.search(rf'\b{re.escape(needle)}\b', hay)
                        )
                    if matched:
                        hit = True
                        evidence = (
                            f"skill_manage action={args.get('action', '?')} "
                            f"on '{target}' referenced '{name}' "
                            f"in {hay[:80]}"
                        )
                        break
                if hit:
                    break
            if hit:
                into = target
                break

        if into:
            consolidated.append({"name": name, "into": into, "evidence": evidence})
        else:
            pruned.append({"name": name})

    return {"consolidated": consolidated, "pruned": pruned}


def _parse_structured_summary(
    llm_final: str,
) -> Dict[str, List[Dict[str, str]]]:
    """
    从策展器的最终响应中提取结构化 YAML 块。

    策展器提示要求在 ``## 结构化摘要（必填）`` 下
    有一个带围栏的 ```yaml 块，包含 ``consolidations:`` 和
    ``prunings:`` 列表。这宽容地解析它：

    - 缺少块→返回空列表（我们将回退到启发式）。
    - 格式错误的 YAML→返回空列表并依赖启发式。
    - 部分块（例如：只有 consolidations）→返回我们能解析的。

    返回 ``{"consolidations": [{"from", "into", "reason"}, ...], "prunings": [{"name", "reason"}, ...]}``。
    """
    empty = {"consolidations": [], "prunings": []}
    if not llm_final or not isinstance(llm_final, str):
        return empty

    # 找到 YAML 带围栏的块。我们专门寻找 ```yaml ... ```，
    # 而不是任何带围栏的块，这样我们就不会意外地选择模型在其他地方引用的代码样本。
    import re
    match = re.search(
        r"```ya?ml\s*\n(.*?)\n```",
        llm_final,
        re.DOTALL | re.IGNORECASE,
    )
    if not match:
        return empty

    body = match.group(1)

    # 优先使用 PyYAML——每个 hermes 安装都已经有它（config.yaml 加载器）。
    # 出于偏执回退到手写解析器。
    try:
        import yaml  # type: ignore
        data = yaml.safe_load(body)
    except Exception:
        return empty

    if not isinstance(data, dict):
        return empty

    out: Dict[str, List[Dict[str, str]]] = {"consolidations": [], "prunings": []}
    cons_raw = data.get("consolidations") or []
    prun_raw = data.get("prunings") or []

    if isinstance(cons_raw, list):
        for entry in cons_raw:
            if not isinstance(entry, dict):
                continue
            frm = entry.get("from")
            into = entry.get("into")
            if not (isinstance(frm, str) and frm.strip()
                    and isinstance(into, str) and into.strip()):
                continue
            reason = entry.get("reason")
            out["consolidations"].append({
                "from": frm.strip(),
                "into": into.strip(),
                "reason": (reason or "").strip() if isinstance(reason, str) else "",
            })

    if isinstance(prun_raw, list):
        for entry in prun_raw:
            if not isinstance(entry, dict):
                continue
            name = entry.get("name")
            if not (isinstance(name, str) and name.strip()):
                continue
            reason = entry.get("reason")
            out["prunings"].append({
                "name": name.strip(),
                "reason": (reason or "").strip() if isinstance(reason, str) else "",
            })

    return out


def _extract_absorbed_into_declarations(
    tool_calls: List[Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    """
    遍历此次运行的工具调用并提取模型声明的吸收目标。

    策展器提示要求每个 ``skill_manage(action='delete')`` 调用
    在合并时传递 ``absorbed_into=<umbrella>``，或在真正修剪时传递 ``absorbed_into=""``。
    这是分类的单一权威信号——模型在删除时的直接声明，
    它胜过事后 YAML 摘要解析和其他工具调用上的子字符串启发式两者。

    返回 ``{skill_name: {"into": "<umbrella>" | "", "declared": True}}``。
    带有 ``into == ""`` 的条目是显式修剪。
    没有 ``skill_manage(delete)`` 调用，或有但省略了 ``absorbed_into`` 的技能，
    不在返回字典中——调用者回退到现有的启发式/YAML 逻辑处理那些
    （与旧策展运行向后兼容以及任何未填充该参数的调用者）。
    """
    out: Dict[str, Dict[str, Any]] = {}
    for tc in tool_calls or []:
        if not isinstance(tc, dict):
            continue
        if tc.get("name") != "skill_manage":
            continue
        raw = tc.get("arguments") or ""
        args: Dict[str, Any] = {}
        if isinstance(raw, dict):
            args = raw
        elif isinstance(raw, str):
            try:
                args = json.loads(raw)
            except Exception:
                continue
        if not isinstance(args, dict):
            continue
        if args.get("action") != "delete":
            continue
        name = args.get("name")
        if not (isinstance(name, str) and name.strip()):
            continue
        # absorbed_into 必须存在（即使空字符串也有意义）；缺少键意味着模型没有声明意图。
        if "absorbed_into" not in args:
            continue
        target = args.get("absorbed_into")
        if target is None:
            continue
        if not isinstance(target, str):
            continue
        out[name.strip()] = {"into": target.strip(), "declared": True}
    return out


def _reconcile_classification(
    removed: List[str],
    heuristic: Dict[str, List[Dict[str, Any]]],
    model_block: Dict[str, List[Dict[str, str]]],
    destinations: Set[str],
    absorbed_declarations: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Dict[str, List[Dict[str, Any]]]:
    """
    合并启发式（工具调用审计）与模型的结构化块。

    规则（按顺序评估；首次匹配获胜）：
    • **删除时模型声明的 absorbed_into 是权威的。**
      ``absorbed_declarations`` 中的任何条目胜过所有其他信号。这是模型在删除时直接告诉我们它做了什么。
      ``into != ""`` 并且目标存在→合并。``into == ""``→修剪。
      ``into != ""`` 但目标不存在→幻觉；回退到通常信号。
    • 当模型声明的合并的 ``into`` 目标存在于 ``destinations``（幸存或新创建）中时，该声明获胜。
      这赋予模型对意图+理由的权威。
    • 模型声明的合并的 ``into`` 目标不存在是降级：模型产生了伞形幻觉。
      我们更喜欢该技能的启发式发现，或回退到修剪。
    • 仅启发式发现（模型没有提到它，工具调用确认）被保留为合并，
      标记为 ``source="tool-call audit"``。
    • 模型声明的修剪被接受，除非启发式有工具调用证据反驳它（罕见——启发式会标记合并）。
      在那种情况下，我们记录两者。

    每个删除的技能都被放置在恰好一个桶中。
    """
    heur_cons = {e["name"]: e for e in heuristic.get("consolidated", [])}
    heur_pruned = {e["name"] for e in heuristic.get("pruned", [])}

    model_cons = {e["from"]: e for e in model_block.get("consolidations", [])}
    model_pruned = {e["name"]: e for e in model_block.get("prunings", [])}

    declared = absorbed_declarations or {}

    consolidated: List[Dict[str, Any]] = []
    pruned: List[Dict[str, Any]] = []

    for name in removed:
        mc = model_cons.get(name)
        mp = model_pruned.get(name)
        hc = heur_cons.get(name)
        dec = declared.get(name)

        # 权威：模型在删除调用时声明了 `absorbed_into`。
        if dec is not None:
            into_claim = dec.get("into", "")
            if into_claim and into_claim in destinations:
                entry: Dict[str, Any] = {
                    "name": name,
                    "into": into_claim,
                    "source": "absorbed_into (model-declared at delete)",
                    "reason": (mc.get("reason") or "") if mc else "",
                }
                if hc and hc.get("evidence"):
                    entry["evidence"] = hc["evidence"]
                consolidated.append(entry)
                continue
            if into_claim == "":
                # 显式修剪声明
                pruned.append({
                    "name": name,
                    "source": "absorbed_into=\"\" (model-declared pruning)",
                    "reason": (mp.get("reason") or "") if mp else "",
                })
                continue
            # into_claim 非空但目标不存在：模型在删除时命名了一个不存在的伞形。
            # 工具已经在 skill_manage 层拒绝了这一点，所以我们在实践中应该看不到它——
            # 但如果它通过（例如：伞形在同一运行稍后被删除），
            # 回退到通常信号而不是信任一个坏引用。

        # 模型说合并——如果目标真实则信任它。
        if mc and mc.get("into") in destinations:
            entry: Dict[str, Any] = {
                "name": name,
                "into": mc["into"],
                "source": "model" + ("+audit" if hc else ""),
                "reason": mc.get("reason") or "",
            }
            if hc and hc.get("evidence"):
                entry["evidence"] = hc["evidence"]
            consolidated.append(entry)
            continue

        # 模型说合并但伞形不存在——幻觉。回退到启发式或修剪。
        if mc and mc.get("into") not in destinations:
            if hc:
                consolidated.append({
                    "name": name,
                    "into": hc["into"],
                    "source": "tool-call audit (model named missing umbrella)",
                    "reason": "",
                    "evidence": hc.get("evidence", ""),
                    "model_claimed_into": mc["into"],
                })
            else:
                pruned.append({
                    "name": name,
                    "source": "fallback (model named missing umbrella, no tool-call evidence)",
                    "reason": "",
                })
            continue

        # 启发式找到了模型没有提到的合并。
        if hc:
            consolidated.append({
                "name": name,
                "into": hc["into"],
                "source": "tool-call audit (model omitted from structured block)",
                "reason": "",
                "evidence": hc.get("evidence", ""),
            })
            continue

        # 模型说修剪（或没有提到 + 没有启发式证据）。
        reason = mp.get("reason", "") if mp else ""
        pruned.append({
            "name": name,
            "source": "model" if mp else "no-evidence fallback",
            "reason": reason,
        })

    return {"consolidated": consolidated, "pruned": pruned}


def _build_rename_summary(
    *,
    before_names: Set[str],
    after_report: List[Dict[str, Any]],
    tool_calls: List[Dict[str, Any]],
    model_final: str,
) -> str:
    """
    为策展运行格式化用户可见的重命名映射。

    渲染"我的技能去哪里了？"行，这些行被附加到提供给网关/CLI 接收器的
    ``final_summary`` 字符串。当此次运行没有归档任何内容时为空字符串——
    大多数 tick 是空操作，不应该添加额外的日志噪声。

    格式：

        archived 4 skill(s):
          • pdf-extraction → document-tools
          • docx-extraction → document-tools
          • flaky-thing — pruned (stale)
          • old-utility → spreadsheet-ops
        full report: hermes curator status
        keep an umbrella stable: hermes curator pin document-tools

    上限为 10 个条目，这样 50 个技能的合并不会炸毁 agent.log；
    完整列表始终在 REPORT.md 中。
    仅当至少有一个合并产生了值得固定的伞形时，才会显示固定提示——
    仅修剪的运行会跳过它。
    """
    after_by_name = {r.get("name"): r for r in after_report if isinstance(r, dict)}
    after_names = set(after_by_name.keys())
    removed = sorted(before_names - after_names)
    added = sorted(after_names - before_names)
    if not removed:
        return ""

    heuristic = _classify_removed_skills(
        removed=removed,
        added=added,
        after_names=after_names,
        tool_calls=tool_calls,
    )
    model_block = _parse_structured_summary(model_final)
    destinations = set(after_names) | set(added)
    absorbed_declarations = _extract_absorbed_into_declarations(tool_calls)
    classification = _reconcile_classification(
        removed=removed,
        heuristic=heuristic,
        model_block=model_block,
        destinations=destinations,
        absorbed_declarations=absorbed_declarations,
    )
    consolidated = classification["consolidated"]
    pruned = classification["pruned"]

    SHOW = 10
    lines: List[str] = []
    total = len(consolidated) + len(pruned)
    lines.append(f"archived {total} skill(s):")
    shown = 0
    for entry in consolidated:
        if shown >= SHOW:
            break
        name = entry.get("name", "?")
        into = entry.get("into", "?")
        lines.append(f"  • {name} → {into}")
        shown += 1
    for entry in pruned:
        if shown >= SHOW:
            break
        name = entry.get("name", "?") if isinstance(entry, dict) else str(entry)
        lines.append(f"  • {name} — pruned (stale)")
        shown += 1
    if total > SHOW:
        lines.append(f"  … and {total - SHOW} more")
    lines.append("full report: hermes curator status")
    # 固定提示——仅当实际上有值得固定的目标技能时才显示它。吸收了内容的伞形技能是自然的候选：
    # 固定一个告诉未来的策展运行不要管它。仅修剪的运行不会得到这个提示（没有幸存下来可以固定）。
    if consolidated:
        umbrellas = sorted({e.get("into") for e in consolidated if e.get("into")})
        if umbrellas:
            example = umbrellas[0]
            lines.append(
                f"keep an umbrella stable: hermes curator pin {example}"
            )
    return "\n".join(lines)


def _write_run_report(
    *,
    started_at: datetime,
    elapsed_seconds: float,
    auto_counts: Dict[str, int],
    auto_summary: str,
    before_report: List[Dict[str, Any]],
    before_names: Set[str],
    after_report: List[Dict[str, Any]],
    llm_meta: Dict[str, Any],
) -> Optional[Path]:
    """
    在 logs/curator/{YYYYMMDD-HHMMSS}/ 下写入 run.json + REPORT.md。

    成功时返回报告目录路径，写入无法发生时返回 None（调用者记录并继续——报告是尽最大努力）。
    """
    root = _reports_root()
    try:
        root.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        logger.debug("Curator reports dir create failed: %s", e)
        return None

    stamp = started_at.strftime("%Y%m%d-%H%M%S")
    run_dir = root / stamp
    # 如果我们在同一秒内崩溃并重新运行，追加消歧器
    suffix = 1
    while run_dir.exists():
        suffix += 1
        run_dir = root / f"{stamp}-{suffix}"
    try:
        run_dir.mkdir(parents=True, exist_ok=False)
    except Exception as e:
        logger.debug("Curator run dir create failed: %s", e)
        return None

    # 之前/之后差异
    after_by_name = {r.get("name"): r for r in after_report if isinstance(r, dict)}
    after_names = set(after_by_name.keys())
    removed = sorted(before_names - after_names)  # 此次运行中归档
    added = sorted(after_names - before_names)  # 此次运行中新技能
    before_by_name = {r.get("name"): r for r in before_report if isinstance(r, dict)}

    # 两个快照之间的状态转换（例如：active → stale）
    transitions: List[Dict[str, str]] = []
    for name in sorted(after_names & before_names):
        s_before = (before_by_name.get(name) or {}).get("state")
        s_after = (after_by_name.get(name) or {}).get("state")
        if s_before and s_after and s_before != s_after:
            transitions.append({"name": name, "from": s_before, "to": s_after})

    # 分类 LLM 工具调用
    tc_counts: Dict[str, int] = {}
    for tc in llm_meta.get("tool_calls", []) or []:
        name = tc.get("name", "unknown")
        tc_counts[name] = tc_counts.get(name, 0) + 1

    # 将"已删除"拆分为合并（吸收到伞形）与修剪（因过时而归档，内容未在其他地方保留）。
    # 旧的"Skills archived"部分将两者混在一起，这误导了用户。
    #
    # 分类策略：
    # 1. 从策展器的最终响应中解析结构化 YAML 块。
    #    策展器现在被提示发出带有简短理由的 consolidations/prunings 列表。
    #    模型具有工具调用没有的意图可见性。
    # 2. 运行工具调用启发式作为地面真相审计。
    # 3. 协调：模型获得意图+理由的权威，启发式捕获幻觉（伞形不存在）和遗漏
    #    （模型忘记列出实际合并）。
    heuristic = _classify_removed_skills(
        removed=removed,
        added=added,
        after_names=after_names,
        tool_calls=llm_meta.get("tool_calls", []) or [],
    )
    model_block = _parse_structured_summary(llm_meta.get("final", "") or "")
    destinations = set(after_names) | set(added or [])
    # 权威信号：从此运行的工具调用中提取每个删除的 `absorbed_into` 声明。
    # 这些胜过 YAML 摘要块和子字符串启发式两者——模型在删除时直接告诉我们，
    # 每个归档的技能是被合并（into=<umbrella>）还是被修剪（into=""）。
    absorbed_declarations = _extract_absorbed_into_declarations(
        llm_meta.get("tool_calls", []) or []
    )
    classification = _reconcile_classification(
        removed=removed,
        heuristic=heuristic,
        model_block=model_block,
        destinations=destinations,
        absorbed_declarations=absorbed_declarations,
    )
    consolidated = classification["consolidated"]
    pruned = classification["pruned"]

    # 重写 cron 作业技能引用。当策展器将技能 X 合并到伞形 Y 时，
    # 任何列出 X 的 cron 作业在运行时无法加载它——调度器跳过它，作业在没有计划跟随的指令下运行。
    # 就地重写引用保持计划的作业在合并运行中继续工作。
    # 尽最大努力：永远不要让 cron 模块问题破坏策展器。
    cron_rewrites: Dict[str, Any] = {"rewrites": [], "jobs_updated": 0, "jobs_scanned": 0}
    try:
        consolidated_map = {
            e["name"]: e["into"]
            for e in consolidated
            if isinstance(e, dict) and e.get("name") and e.get("into")
        }
        pruned_names = [
            e["name"] for e in pruned
            if isinstance(e, dict) and e.get("name")
        ]
        if consolidated_map or pruned_names:
            from cron.jobs import rewrite_skill_refs as _rewrite_cron_refs
            cron_rewrites = _rewrite_cron_refs(
                consolidated=consolidated_map,
                pruned=pruned_names,
            )
    except Exception as e:
        logger.debug("Curator cron skill rewrite failed: %s", e, exc_info=True)
        cron_rewrites = {
            "rewrites": [],
            "jobs_updated": 0,
            "jobs_scanned": 0,
            "error": str(e),
        }

    payload = {
        "started_at": started_at.isoformat(),
        "duration_seconds": round(elapsed_seconds, 2),
        "model": llm_meta.get("model", ""),
        "provider": llm_meta.get("provider", ""),
        "auto_transitions": auto_counts,
        "counts": {
            "before": len(before_names),
            "after": len(after_names),
            "delta": len(after_names) - len(before_names),
            "archived_this_run": len(removed),
            "added_this_run": len(added),
            "consolidated_this_run": len(consolidated),
            "pruned_this_run": len(pruned),
            "state_transitions": len(transitions),
            "cron_jobs_rewritten": int(cron_rewrites.get("jobs_updated", 0)),
            "tool_calls_total": sum(tc_counts.values()),
        },
        "tool_call_counts": tc_counts,
        "archived": removed,
        "consolidated": consolidated,
        "pruned": pruned,
        "pruned_names": [p["name"] for p in pruned],
        "added": added,
        "state_transitions": transitions,
        "cron_rewrites": cron_rewrites,
        "llm_final": llm_meta.get("final", ""),
        "llm_summary": llm_meta.get("summary", ""),
        "llm_error": llm_meta.get("error"),
        "tool_calls": llm_meta.get("tool_calls", []),
    }

    # run.json——机器可读，完整保真度
    try:
        (run_dir / "run.json").write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    except Exception as e:
        logger.debug("Curator run.json write failed: %s", e)

    # REPORT.md——人类可读
    try:
        md = _render_report_markdown(payload)
        (run_dir / "REPORT.md").write_text(md, encoding="utf-8")
    except Exception as e:
        logger.debug("Curator REPORT.md write failed: %s", e)

    # cron_rewrites.json——仅当至少一个作业被触碰时，以保持常见空操作情况的运行目录整洁。
    try:
        if int(cron_rewrites.get("jobs_updated", 0)) > 0:
            (run_dir / "cron_rewrites.json").write_text(
                json.dumps(cron_rewrites, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
    except Exception as e:
        logger.debug("Curator cron_rewrites.json write failed: %s", e)

    return run_dir


def _render_report_markdown(p: Dict[str, Any]) -> str:
    """渲染人类可读的报告。"""
    lines: List[str] = []
    started = p.get("started_at", "")
    duration = p.get("duration_seconds", 0) or 0
    mins, secs = divmod(int(duration), 60)
    dur_label = f"{mins}m {secs}s" if mins else f"{secs}s"

    lines.append(f"# 策展运行 — {started}\n")
    model = p.get("model") or "(未解析)"
    prov = p.get("provider") or "(未解析)"
    counts = p.get("counts") or {}
    lines.append(
        f"模型：`{model}` 通过 `{prov}` · 持续时间：{dur_label} · "
        f"代理创建的技能：{counts.get('before', 0)} → {counts.get('after', 0)} "
        f"({counts.get('delta', 0):+d})\n"
    )

    error = p.get("llm_error")
    if error:
        lines.append(f"> ⚠ LLM 通道错误：`{error}`\n")

    # 自动转换（纯，无 LLM）
    auto = p.get("auto_transitions") or {}
    lines.append("## 自动转换（纯，无 LLM）\n")
    lines.append(f"- 检查：{auto.get('checked', 0)}")
    lines.append(f"- 标记过时：{auto.get('marked_stale', 0)}")
    lines.append(f"- 归档（无 LLM，纯基于时间的过时）：{auto.get('archived', 0)}")
    lines.append(f"- 重新激活：{auto.get('reactivated', 0)}")
    lines.append("")

    # LLM 通道数字
    tc_counts = p.get("tool_call_counts") or {}
    lines.append("## LLM 合并通道\n")
    lines.append(f"- 工具调用：**{counts.get('tool_calls_total', 0)}** "
                 f"(按名称：{', '.join(f'{k}={v}' for k, v in sorted(tc_counts.items())) or '无'})")
    lines.append(f"- 合并到伞形：**{counts.get('consolidated_this_run', 0)}**")
    lines.append(f"- 修剪（因过时而归档）：**{counts.get('pruned_this_run', 0)}**")
    lines.append(f"- 此次运行新技能：**{counts.get('added_this_run', 0)}**")
    lines.append(f"- 状态转换（active ↔ stale ↔ archived）："
                 f"**{counts.get('state_transitions', 0)}**")
    lines.append("")

    # 合并列表——内容吸收到伞形中。磁盘上的目录仍然存在于 ~/.hermes/skills/.archive/ 下
    #（每个删除都是设计可恢复的），但这些技能的"活"内容继续存在于目标伞形中。
    consolidated = p.get("consolidated") or []
    if consolidated:
        lines.append(f"### 合并到伞形技能（{len(consolidated)}）\n")
        lines.append(
            "这些技能在此次运行中**被吸收到另一个技能**——它们的内容仍然存在，只是名称不同。"
            "原始目录已移动到 `~/.hermes/skills/.archive/` 以确保安全，"
            "并且如果合并错误，可以通过 `hermes curator restore <name>` 恢复。\n"
        )
        SHOW = 50
        for entry in consolidated[:SHOW]:
            name = entry.get("name", "?")
            into = entry.get("into", "?")
            reason = (entry.get("reason") or "").strip()
            source = entry.get("source", "")
            line = f"- `{name}` → 合并到 `{into}`"
            if reason:
                line += f" — {reason}"
            if source and source.startswith("tool-call audit"):
                # 模型没有枚举这个——向用户展示，以便他们知道为什么该行没有理由。
                line += f"  _(通过 {source} 检测)_"
            lines.append(line)
            if entry.get("model_claimed_into"):
                lines.append(
                    f"  ⚠ 策展器的摘要将 `{entry['model_claimed_into']}` 命名为伞形，"
                    "但该技能在运行后不存在；显示工具调用审计的发现。"
                )
        if len(consolidated) > SHOW:
            lines.append(f"- … 还有 {len(consolidated) - SHOW} 个（参见 `run.json`）")
        lines.append("")

    # 修剪列表——归档而无合并。这些是 UI 应该清楚标记的"过时技能修剪"情况。
    pruned = p.get("pruned") or []
    if pruned:
        lines.append(f"### 修剪——因过时而归档（{len(pruned)}）\n")
        lines.append(
            "这些技能在没有合并到伞形的情况下被归档（例如：过时、未使用或被判定为不相关）。"
            "目录位于 `~/.hermes/skills/.archive/` 下。"
            "通过 `hermes curator restore <name>` 恢复任何一个。\n"
        )
        SHOW = 50
        for entry in pruned[:SHOW]:
            # 条目在通过协调器写入时是带有 {name, source, reason} 的字典，
            # 或者在旧格式滑过时是纯字符串。处理两者。
            if isinstance(entry, dict):
                name = entry.get("name", "?")
                reason = (entry.get("reason") or "").strip()
                line = f"- `{name}`"
                if reason:
                    line += f" — {reason}"
                lines.append(line)
            else:
                lines.append(f"- `{entry}`")
        if len(pruned) > SHOW:
            lines.append(f"- … 还有 {len(pruned) - SHOW} 个（参见 `run.json`）")
        lines.append("")

    # 添加列表
    added = p.get("added") or []
    if added:
        lines.append(f"### 此次运行新技能（{len(added)}）\n")
        lines.append("通常这些是通过 `skill_manage action=create` 创建的新类级伞形。\n")
        for n in added:
            lines.append(f"- `{n}`")
        lines.append("")

    # 状态转换
    trans = p.get("state_transitions") or []
    if trans:
        lines.append(f"### 状态转换（{len(trans)}）\n")
        for t in trans:
            lines.append(f"- `{t.get('name')}`: {t.get('from')} → {t.get('to')}")
        lines.append("")

    # Cron 作业重写——显示哪些计划的作业的技能引用被更新，以便用户可以审计自动重写做了正确的事情。
    # 仅在至少一个作业改变时出现。
    cron_rw = p.get("cron_rewrites") or {}
    cron_rewrites_list = cron_rw.get("rewrites") or []
    if cron_rewrites_list:
        lines.append(f"### Cron 作业技能引用重写（{len(cron_rewrites_list)}）\n")
        lines.append(
            "引用已合并或修剪技能的 Cron 作业被就地更新，以便它们在下次运行时继续加载正确的指令。"
            "完整记录参见 `cron_rewrites.json`。\n"
        )
        SHOW = 25
        for entry in cron_rewrites_list[:SHOW]:
            job_name = entry.get("job_name") or entry.get("job_id") or "?"
            before = entry.get("before") or []
            after = entry.get("after") or []
            mapped = entry.get("mapped") or {}
            dropped = entry.get("dropped") or []
            lines.append(
                f"- `{job_name}`: `{', '.join(before)}` → `{', '.join(after) or '(无)'}`"
            )
            for old, new in mapped.items():
                lines.append(f"    - `{old}` → `{new}`（已合并）")
            for name in dropped:
                lines.append(f"    - `{name}` 已删除（已修剪）")
        if len(cron_rewrites_list) > SHOW):
            lines.append(
                f"- … 还有 {len(cron_rewrites_list) - SHOW} 个"
                "（参见 `cron_rewrites.json`）"
            )
        lines.append("")

    # 完整的 LLM 最终响应
    final = (p.get("llm_final") or "").strip()
    if final:
        lines.append("## LLM 最终摘要\n")
        lines.append(final)
        lines.append("")
    elif not error:
        llm_sum = p.get("llm_summary") or ""
        if llm_sum:
            lines.append("## LLM 摘要\n")
            lines.append(llm_sum)
            lines.append("")

    # 恢复页脚
    lines.append("## 恢复\n")
    lines.append("- 恢复已归档的技能：`hermes curator restore <name>`")
    lines.append("- 所有归档都位于 `~/.hermes/skills/.archive/` 下，并且可以通过 `mv` 恢复")
    lines.append("- 完整的机器可读记录参见此目录中的 `run.json`。")
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 协调器——派生出分叉的 AIAgent 用于 LLM 审查通道
# ---------------------------------------------------------------------------

def _render_candidate_list() -> str:
    """人类/代理可读的具有使用统计的代理创建技能列表。"""
    rows = skill_usage.agent_created_report()
    if not rows:
        return "没有要审查的代理创建技能。"
    lines = [f"代理创建的技能（{len(rows)}）：\n"]
    for r in rows:
        lines.append(
            f"- {r['name']}  "
            f"state={r['state']}  "
            f"pinned={'yes' if r.get('pinned') else 'no'}  "
            f"activity={r.get('activity_count', 0)}  "
            f"use={r.get('use_count', 0)}  "
            f"view={r.get('view_count', 0)}  "
            f"patches={r.get('patch_count', 0)}  "
            f"last_activity={r.get('last_activity_at') or 'never'}"
        )
    return "\n".join(lines)


def run_curator_review(
    on_summary: Optional[Callable[[str], None]] = None,
    synchronous: bool = False,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    执行单次策展审查通道。

    步骤：
      1. 应用自动状态转换（纯，无 LLM）。
      2. 如果有代理创建的技能，派生出分叉的 AIAgent，它对当前候选列表运行 LLM 审查提示。
      3. 使用 last_run_at 和单行摘要更新 .curator_state。
      4. 使用用户可见的描述调用 *on_summary*。

    如果 *synchronous* 为 True，LLM 审查在调用线程中运行；默认是派生出守护线程，以便调用者立即返回。

    如果 *dry_run* 为 True，自动过时/归档转换被跳过，
    并且 LLM 审查通道被指示仅生成报告——
    没有 skill_manage 变更，没有 terminal 归档移动。REPORT.md 仍然被写入，
    并且 ``state.last_report_path`` 仍然记录它，以便用户可以阅读策展器会做什么。
    """
    start = datetime.now(timezone.utc)
    if dry_run:
        # 计数候选而不改变状态。
        try:
            report = skill_usage.agent_created_report()
            counts = {
                "checked": len(report),
                "marked_stale": 0,
                "archived": 0,
                "reactivated": 0,
            }
        except Exception:
            counts = {"checked": 0, "marked_stale": 0, "archived": 0, "reactivated": 0}
    else:
        # 变更前快照——尽最大努力，永远不阻塞运行。
        # 失败的快照在调试级别记录并继续（替代方案是瞬态磁盘问题静默永久禁用策展器，这更糟）。
        # 希望快照的用户可以在修复磁盘空间之前完全禁用策展器。
        try:
            from agent import curator_backup
            snap = curator_backup.snapshot_skills(reason="pre-curator-run")
            if snap is not None and on_summary:
                try:
                    on_summary(f"curator: snapshot created ({snap.name})")
                except Exception:
                    pass
        except Exception as e:
            logger.debug("Curator pre-run snapshot failed: %s", e, exc_info=True)
        counts = apply_automatic_transitions(now=start)

    auto_summary_parts = []
    if counts["marked_stale"]:
        auto_summary_parts.append(f"{counts['marked_stale']} marked stale")
    if counts["archived"]:
        auto_summary_parts.append(f"{counts['archived']} archived")
    if counts["reactivated"]:
        auto_summary_parts.append(f"{counts['reactivated']} reactivated")
    auto_summary = ", ".join(auto_summary_parts) if auto_summary_parts else "no changes"

    # 在 LLM 通道之前持久化状态，以便在审查中途崩溃仍然记录运行并且不会立即重新触发。
    # 在空运行中，我们不增加 last_run_at 或 run_count——预览不应该将下一次计划的真实运行推远。
    # 我们仍然记录摘要，以便 `hermes curator status` 显示预览已运行。
    state = load_state()
    if not dry_run:
        state["last_run_at"] = start.isoformat()
        state["run_count"] = int(state.get("run_count", 0)) + 1
    prefix = "dry-run auto: " if dry_run else "auto: "
    state["last_run_summary"] = f"{prefix}{auto_summary}"
    save_state(state)

    def _llm_pass():
        nonlocal auto_summary
        # LLM 通道之前的技能状态快照，以便报告可以差异。
        try:
            before_report = skill_usage.agent_created_report()
        except Exception:
            before_report = []
        before_names = {r.get("name") for r in before_report if isinstance(r, dict)}

        llm_meta: Dict[str, Any] = {}
        try:
            candidate_list = _render_candidate_list()
            if "没有要审查的代理创建技能" in candidate_list:
                final_summary = f"{prefix}{auto_summary}; llm: skipped (no candidates)"
                llm_meta = {
                    "final": "",
                    "summary": "skipped (no candidates)",
                    "model": "",
                    "provider": "",
                    "tool_calls": [],
                    "error": None,
                }
            else:
                if dry_run:
                    prompt = (
                        f"{CURATOR_DRY_RUN_BANNER}\n\n"
                        f"{CURATOR_REVIEW_PROMPT}\n\n"
                        f"{candidate_list}"
                    )
                else:
                    prompt = f"{CURATOR_REVIEW_PROMPT}\n\n{candidate_list}"
                llm_meta = _run_llm_review(prompt)
                final_summary = (
                    f"{prefix}{auto_summary}; llm: {llm_meta.get('summary', 'no change')}"
                )
        except Exception as e:
            logger.debug("Curator LLM pass failed: %s", e, exc_info=True)
            final_summary = f"{prefix}{auto_summary}; llm: error ({e})"
            llm_meta = {
                "final": "",
                "summary": f"error ({e})",
                "model": "",
                "provider": "",
                "tool_calls": [],
                "error": str(e),
            }

        # 将重命名映射（`old-name → umbrella`）附加到用户可见摘要，
        # 以便人们不必深入 REPORT.md 就能发现他们的技能去了哪里。
        # 尽最大努力：分类是纯的，但永远不要在格式化问题上阻塞运行。
        try:
            rename_lines = _build_rename_summary(
                before_names=before_names,
                after_report=skill_usage.agent_created_report(),
                tool_calls=llm_meta.get("tool_calls", []) or [],
                model_final=llm_meta.get("final", "") or "",
            )
            if rename_lines:
                final_summary = f"{final_summary}\n{rename_lines}"
        except Exception as e:
            logger.debug("Curator rename summary build failed: %s", e, exc_info=True)

        elapsed = (datetime.now(timezone.utc) - start).total_seconds()
        state2 = load_state()
        state2["last_run_duration_seconds"] = elapsed
        state2["last_run_summary"] = final_summary

        # 写入每次运行的报告。在 try 中运行，以便报告错误永远不会破坏策展器本身。
        # 报告路径记录在状态中，以便 `hermes curator status` 可以指向它。
        try:
            after_report = skill_usage.agent_created_report()
        except Exception:
            after_report = []
        try:
            report_path = _write_run_report(
                started_at=start,
                elapsed_seconds=elapsed,
                auto_counts=counts,
                auto_summary=auto_summary,
                before_report=before_report,
                before_names=before_names,
                after_report=after_report,
                llm_meta=llm_meta,
            )
            if report_path is not None:
                state2["last_report_path"] = str(report_path)
        except Exception as e:
            logger.debug("Curator report write failed: %s", e, exc_info=True)

        save_state(state2)

        if on_summary:
            try:
                on_summary(f"curator: {final_summary}")
            except Exception:
                pass

    if synchronous:
        _llm_pass()
    else:
        t = threading.Thread(target=_llm_pass, daemon=True, name="curator-review")
        t.start()

    return {
        "started_at": start.isoformat(),
        "auto_transitions": counts,
        "summary_so_far": auto_summary,
    }


def _resolve_review_runtime(cfg: Dict[str, Any]) -> _ReviewRuntimeBinding:
    """
    解析策展审查分叉的提供商/模型和每个槽覆盖。

    与 `_resolve_review_model()` 优先级相同。来自活动槽的非空 ``api_key``/``base_url``
    作为显式覆盖返回，以便 `resolve_runtime_provider` 不会为路由的辅助模型静默重用主聊天凭据链。
    """
    _main = cfg.get("model", {}) if isinstance(cfg.get("model"), dict) else {}
    _main_provider = _main.get("provider") or "auto"
    _main_model = _main.get("default") or _main.get("model") or ""

    # 1. 规范辅助任务槽
    _aux = cfg.get("auxiliary", {}) if isinstance(cfg.get("auxiliary"), dict) else {}
    _cur_task = _aux.get("curator", {}) if isinstance(_aux.get("curator"), dict) else {}
    _task_provider = (_cur_task.get("provider") or "").strip() or None
    _task_model = (_cur_task.get("model") or "").strip() or None
    if _task_provider and _task_provider != "auto" and _task_model:
        return _ReviewRuntimeBinding(
            _task_provider,
            _task_model,
            _strip_aux_credential(_cur_task.get("api_key")),
            _strip_aux_credential(_cur_task.get("base_url")),
        )

    # 2. 旧版 curator.auxiliary.{provider,model}（已弃用，统一前）
    _cur = cfg.get("curator", {}) if isinstance(cfg.get("curator"), dict) else {}
    _legacy = _cur.get("auxiliary", {}) if isinstance(_cur.get("auxiliary"), dict) else {}
    _legacy_provider = _legacy.get("provider") or None
    _legacy_model = _legacy.get("model") or None
    if _legacy_provider and _legacy_model:
        logger.info(
            "curator: using deprecated curator.auxiliary.{provider,model} "
            "config — please migrate to auxiliary.curator.{provider,model}"
        )
        return _ReviewRuntimeBinding(
            str(_legacy_provider),
            str(_legacy_model),
            _strip_aux_credential(_legacy.get("api_key")),
            _strip_aux_credential(_legacy.get("base_url")),
        )

    # 3. 回退到主聊天模型
    return _ReviewRuntimeBinding(_main_provider, _main_model, None, None)


def _resolve_review_model(cfg: Dict[str, Any]) -> tuple[str, str]:
    """
    选择策展审查分叉的（provider, model）。

    策展器是常规的辅助任务槽——``auxiliary.curator.{provider,model}``——
    所以它参与规范的辅助模型管道（``hermes model`` → 辅助选择器，
    仪表板模型选项卡，``auxiliary.curator.{timeout,base_url,api_key,extra_body}``）。
    带有空模型的 ``provider: "auto"`` 意味着"使用主聊天模型"——与每个其他辅助任务相同的默认值。

    旧版回退：在之前的一次性方案下配置 ``curator.auxiliary.{provider,model}`` 的用户仍然可以工作。
    优先级：
      1. 当两者都设置为非 auto 时为 ``auxiliary.curator.{provider,model}``
      2. 当两者都设置时为旧版 ``curator.auxiliary.{provider,model}``
      3. 主 ``model.{provider,default/model}`` 对
    """
    b = _resolve_review_runtime(cfg)
    return b.provider, b.model


def _run_llm_review(prompt: str) -> Dict[str, Any]:
    """
    派生出 AIAgent 分叉来运行策展审查提示。

    返回包含以下内容的字典：
      - final: 来自审阅者的完整（未截断）最终响应
      - summary: 适合状态文件的简短摘要（240 字符上限）
      - model, provider: 分叉实际运行在什么上
      - tool_calls: 此次通道期间进行的每个工具调用的 {name, arguments} 列表（参数可能为可读性截断）
      - error: 通道中途失败时设置；final/summary 仍然可能为空

    永远不抛出；调用者得到结构化失败。
    """
    import contextlib
    result_meta: Dict[str, Any] = {
        "final": "",
        "summary": "",
        "model": "",
        "provider": "",
        "tool_calls": [],
        "error": None,
    }
    try:
        from run_agent import AIAgent
    except Exception as e:
        result_meta["error"] = f"AIAgent import failed: {e}"
        result_meta["summary"] = result_meta["error"]
        return result_meta

    # 以与 CLI 完全相同的方式解析 provider + model，以便策展器分叉继承用户的活动主配置，
    # 而不是回退到空的 provider/model 对（这发送 HTTP 400 "No models provided"）。
    # 没有显式 provider/model 参数的 AIAgent() 会命中一个自动解析路径，该路径对于 OAuth 唯一提供程序和池支持凭据失败。
    #
    # `_resolve_review_runtime()` 尊重 `auxiliary.curator.{provider,model,...}`
    #（规范辅助任务槽，连接到 `hermes model` → 辅助选择器和仪表板模型选项卡），
    # 旧版回退到 `curator.auxiliary.{provider,model,...}`。
    # 参见 docs/user-guide/features/curator.md。
    _api_key = None
    _base_url = None
    _api_mode = None
    _resolved_provider = None
    _model_name = ""
    try:
        from hermes_cli.config import load_config
        from hermes_cli.runtime_provider import resolve_runtime_provider
        _cfg = load_config()
        _binding = _resolve_review_runtime(_cfg)
        _provider, _model_name = _binding.provider, _binding.model
        _rp = resolve_runtime_provider(
            requested=_provider,
            target_model=_model_name,
            explicit_api_key=_binding.explicit_api_key,
            explicit_base_url=_binding.explicit_base_url,
        )
        _api_key = _rp.get("api_key")
        _base_url = _rp.get("base_url")
        _api_mode = _rp.get("api_mode")
        _resolved_provider = _rp.get("provider") or _provider
    except Exception as e:
        logger.debug("Curator provider resolution failed: %s", e, exc_info=True)

    result_meta["model"] = _model_name
    result_meta["provider"] = _resolved_provider or ""

    review_agent = None
    try:
        review_agent = AIAgent(
            model=_model_name,
            provider=_resolved_provider,
            api_key=_api_key,
            base_url=_base_url,
            api_mode=_api_mode,
            # 在大型技能库上构建伞形值得高迭代上限——
            # 该通道通常在数百个候选技能上需要 50-100 个 API 调用。
            # 单会话审查路径在更小的数量上限自己，因为它不做策展清扫。
            max_iterations=9999,
            quiet_mode=True,
            platform="curator",
            skip_context_files=True,
            skip_memory=True,
        )
        # 禁用递归微调——策展器绝不能派生出自己的审查。
        review_agent._memory_nudge_interval = 0
        review_agent._skill_nudge_interval = 0

        # 在运行时将分叉代理的 stdout/stderr 重定向到 /dev/null，
        # 以便它的工具调用聊天不会污染前台终端。
        # 后台线程运行器也隐藏它；当调用者从 CLI 同步调用 `run_curator_review()` 时，
        # 这条腰带和吊带路径很重要。
        with open(os.devnull, "w", encoding="utf-8") as _devnull, \
             contextlib.redirect_stdout(_devnull), \
             contextlib.redirect_stderr(_devnull):
            conv_result = review_agent.run_conversation(user_message=prompt)

        final = ""
        if isinstance(conv_result, dict):
            final = str(conv_result.get("final_response") or "").strip()
        result_meta["final"] = final
        result_meta["summary"] = (final[:240] + "…") if len(final) > 240 else (final or "no change")

        # 收集报告的工具调用。遍历分叉代理的会话消息并提取此次通道期间进行的每个 tool_call。
        # 截断参数有效负载，以便巨大的 skill_manage create 不会炸毁报告。
        _calls: List[Dict[str, Any]] = []
        for msg in getattr(review_agent, "_session_messages", []) or []:
            if not isinstance(msg, dict):
                continue
            tcs = msg.get("tool_calls") or []
            for tc in tcs:
                if not isinstance(tc, dict):
                    continue
                fn = tc.get("function") or {}
                name = fn.get("name") or ""
                args_raw = fn.get("arguments") or ""
                if isinstance(args_raw, str) and len(args_raw) > 400:
                    args_raw = args_raw[:400] + "…"
                _calls.append({"name": name, "arguments": args_raw})
        result_meta["tool_calls"] = _calls
    except Exception as e:
        result_meta["error"] = f"error: {e}"
        result_meta["summary"] = result_meta["error"]
    finally:
        if review_agent is not None:
            try:
                review_agent.close()
            except Exception:
                pass
    return result_meta


# ---------------------------------------------------------------------------
# 会话开始钩子的公共入口点
# ---------------------------------------------------------------------------

def maybe_run_curator(
    *,
    idle_for_seconds: Optional[float] = None,
    on_summary: Optional[Callable[[str], None]] = None,
) -> Optional[Dict[str, Any]]:
    """
    尽最大努力：如果所有门槛都通过，则运行策展通道。如果开始运行则返回结果字典，否则返回 None。
    永远不抛出。
    """
    try:
        if not should_run_now():
            return None
        # 空闲门槛：仅当调用者提供测量时才强制执行。
        if idle_for_seconds is not None:
            min_idle_s = get_min_idle_hours() * 3600.0
            if idle_for_seconds < min_idle_s:
                return None
        return run_curator_review(on_summary=on_summary)
    except Exception as e:
        logger.debug("maybe_run_curator failed: %s", e, exc_info=True)
        return None
