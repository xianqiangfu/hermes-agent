"""
SKILL.md 共享预处理模块

提供技能内容的预处理功能，包括：
- 模板变量替换（${HERMES_SKILL_DIR}、${HERMES_SESSION_ID}）
- 内联 Shell 命令执行（!`command`）

这些功能可以在配置中启用或禁用。
"""

import logging
import re
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

# Matches ${HERMES_SKILL_DIR} / ${HERMES_SESSION_ID} tokens in SKILL.md.
# Tokens that don't resolve (e.g. ${HERMES_SESSION_ID} with no session) are
# left as-is so the user can debug them.
_SKILL_TEMPLATE_RE = re.compile(r"\$\{(HERMES_SKILL_DIR|HERMES_SESSION_ID)\}")

# Matches inline shell snippets like:  !`date +%Y-%m-%d`
# Non-greedy, single-line only -- no newlines inside the backticks.
_INLINE_SHELL_RE = re.compile(r"!`([^`\n]+)`")

# Cap inline-shell output so a runaway command can't blow out the context.
_INLINE_SHELL_MAX_OUTPUT = 4000


def load_skills_config() -> dict:
    """
    加载 config.yaml 的 ``skills`` 部分（尽力而为）。

    Returns:
        dict - 技能配置字典，如果加载失败则返回空字典
    """
    try:
        from hermes_cli.config import load_config

        cfg = load_config() or {}
        skills_cfg = cfg.get("skills")
        if isinstance(skills_cfg, dict):
            return skills_cfg
    except Exception:
        logger.debug("Could not read skills config", exc_info=True)
    return {}


def substitute_template_vars(
    content: str,
    skill_dir: Path | None,
    session_id: str | None,
) -> str:
    """
    替换技能内容中的 ${HERMES_SKILL_DIR} / ${HERMES_SESSION_ID} 模板变量。

    只替换那些有具体值可用的标记——未解析的标记会保留在原位，以便作者可以发现它们。

    Args:
        content: 技能内容字符串
        skill_dir: 技能目录路径
        session_id: 会话 ID

    Returns:
        str - 替换后的内容
    """
    if not content:
        return content

    skill_dir_str = str(skill_dir) if skill_dir else None

    def _replace(match: re.Match) -> str:
        token = match.group(1)
        if token == "HERMES_SKILL_DIR" and skill_dir_str:
            return skill_dir_str
        if token == "HERMES_SESSION_ID" and session_id:
            return str(session_id)
        return match.group(0)

    return _SKILL_TEMPLATE_RE.sub(_replace, content)


def run_inline_shell(command: str, cwd: Path | None, timeout: int) -> str:
    """
    执行单个内联 Shell 片段并返回其标准输出（去除尾部空白）。

    失败时返回简短的 ``[inline-shell error: ...]`` 标记而不是抛出异常，
    这样一个糟糕的片段不会破坏整个技能消息。

    Args:
        command: 要执行的 Shell 命令
        cwd: 工作目录
        timeout: 超时时间（秒）

    Returns:
        str - 命令输出或错误标记
    """
    try:
        completed = subprocess.run(
            ["bash", "-c", command],
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            timeout=max(1, int(timeout)),
            check=False,
        )
    except subprocess.TimeoutExpired:
        return f"[inline-shell timeout after {timeout}s: {command}]"
    except FileNotFoundError:
        return "[inline-shell error: bash not found]"
    except RuntimeError as exc:
        # tests/conftest.py installs a live-system guard that blocks real
        # os.kill on out-of-tree PIDs. subprocess.run(timeout=...) may trip
        # that guard while trying to clean up the timed-out shell; treat that
        # as the same timeout outcome instead of surfacing the guard error.
        if "live-system guard: blocked os.kill" in str(exc):
            return f"[inline-shell timeout after {timeout}s: {command}]"
        return f"[inline-shell error: {exc}]"
    except Exception as exc:
        return f"[inline-shell error: {exc}]"

    output = (completed.stdout or "").rstrip("\n")
    if not output and completed.stderr:
        output = completed.stderr.rstrip("\n")
    if len(output) > _INLINE_SHELL_MAX_OUTPUT:
        output = output[:_INLINE_SHELL_MAX_OUTPUT] + "...[truncated]"
    return output


def expand_inline_shell(
    content: str,
    skill_dir: Path | None,
    timeout: int,
) -> str:
    """
    将 ``content`` 中的每个 !`cmd` 片段替换为其标准输出。

    使用技能目录作为工作目录运行每个片段，这样片段中的相对路径能按作者预期工作。

    Args:
        content: 技能内容字符串
        skill_dir: 技能目录路径
        timeout: 超时时间（秒）

    Returns:
        str - 替换后的内容
    """
    if "!`" not in content:
        return content

    def _replace(match: re.Match) -> str:
        cmd = match.group(1).strip()
        if not cmd:
            return ""
        return run_inline_shell(cmd, skill_dir, timeout)

    return _INLINE_SHELL_RE.sub(_replace, content)


def preprocess_skill_content(
    content: str,
    skill_dir: Path | None,
    session_id: str | None = None,
    skills_cfg: dict | None = None,
) -> str:
    """
    应用配置的 SKILL.md 模板和内联 Shell 预处理。

    根据配置执行：
    1. 模板变量替换（如果启用）
    2. 内联 Shell 扩展（如果启用）

    Args:
        content: 技能内容字符串
        skill_dir: 技能目录路径
        session_id: 会话 ID
        skills_cfg: 技能配置字典，如果为 None 则从配置文件加载

    Returns:
        str - 预处理后的内容
    """
    if not content:
        return content

    cfg = skills_cfg if isinstance(skills_cfg, dict) else load_skills_config()
    if cfg.get("template_vars", True):
        content = substitute_template_vars(content, skill_dir, session_id)
    if cfg.get("inline_shell", False):
        timeout = int(cfg.get("inline_shell_timeout", 10) or 10)
        content = expand_inline_shell(content, skill_dir, timeout)
    return content
