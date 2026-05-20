"""
采用相位编码的全息压缩表示（HRR）。

HRR 是一种向量符号架构，用于将组合结构编码为固定宽度的分布式表示。
本模块使用 *相位向量*：每个概念是 [0, 2π) 范围内的角度向量。代数操作包括：

  - 绑定（bind）  — 循环卷积（相位相加） — 关联两个概念
  - 解绑（unbind）—— 循环相关（相位相减） — 检索绑定的值
  - 打包（bundle）—— 叠加（循环平均）   — 合并多个概念

相位编码数值稳定，避免了传统复数 HRR 的幅度崩溃问题，
并且可以干净地映射到余弦相似度。

原子通过 SHA-256 确定性生成，因此表示在进程、机器和语言版本之间是相同的。

参考文献：
  - Plate (1995) — 全息压缩表示
  - Gayler (2004) — 向量符号架构回答 Jackendoff 的挑战
"""

import hashlib
import logging
import struct
import math

try:
    import numpy as np
    _HAS_NUMPY = True
except ImportError:
    _HAS_NUMPY = False

logger = logging.getLogger(__name__)

_TWO_PI = 2.0 * math.pi


def _require_numpy() -> None:
    """检查 numpy 是否可用，不可用时抛出 RuntimeError。"""
    if not _HAS_NUMPY:
        raise RuntimeError("numpy is required for holographic operations")


def encode_atom(word: str, dim: int = 1024) -> "np.ndarray":
    """
    通过 SHA-256 计数器块生成确定性相位向量。

    使用 hashlib（不是 numpy RNG）实现跨平台可重复性。

    算法：
    - 通过哈希 f"{word}:{i}" 生成足够的 SHA-256 块，i=0,1,2,...
    - 连接摘要，通过 struct.unpack 解释为 uint16 值
    - 缩放到 [0, 2π) 范围：phases = values * (2π / 65536)
    - 截断到 dim 个元素
    - 返回形状为 (dim,) 的 np.float64 数组
    """
    _require_numpy()

    # 每个 SHA-256 摘要是 32 字节 = 16 个 uint16 值
    values_per_block = 16
    blocks_needed = math.ceil(dim / values_per_block)

    uint16_values: list[int] = []
    for i in range(blocks_needed):
        digest = hashlib.sha256(f"{word}:{i}".encode()).digest()
        uint16_values.extend(struct.unpack("<16H", digest))

    phases = np.array(uint16_values[:dim], dtype=np.float64) * (_TWO_PI / 65536.0)
    return phases


def bind(a: "np.ndarray", b: "np.ndarray") -> "np.ndarray":
    """
    循环卷积 = 逐元素相位相加。

    绑定将两个概念关联成单个复合向量。
    结果与两个输入都不相似（准正交）。
    """
    _require_numpy()
    return (a + b) % _TWO_PI


def unbind(memory: "np.ndarray", key: "np.ndarray") -> "np.ndarray":
    """
    循环相关 = 逐元素相位相减。

    解绑从记忆向量中检索与键关联的值。
    unbind(bind(a, b), a) ≈ b（叠加噪声导致的近似）。
    """
    _require_numpy()
    return (memory - key) % _TWO_PI


def bundle(*vectors: "np.ndarray") -> "np.ndarray":
    """
    通过复数指数的循环平均实现叠加。

    打包将多个向量合并成一个与每个输入都相似的向量。
    在相似度下降之前，结果可以容纳 O(sqrt(dim)) 个项目。
    """
    _require_numpy()
    complex_sum = np.sum([np.exp(1j * v) for v in vectors], axis=0)
    return np.angle(complex_sum) % _TWO_PI


def similarity(a: "np.ndarray", b: "np.ndarray") -> float:
    """
    相位余弦相似度。范围 [-1, 1]。

    相同向量返回 1.0，随机（不相关）向量返回接近 0.0，
    完全反相关向量返回 -1.0。
    """
    _require_numpy()
    return float(np.mean(np.cos(a - b)))


def encode_text(text: str, dim: int = 1024) -> "np.ndarray":
    """
    词袋：每个 token 的原子向量的打包。

    通过小写、按空格分割、并从每个 token 中去除前后标点符号进行分词。

    返回所有 token 原子向量的打包。
    如果文本为空或不产生 token，返回 encode_atom("__hrr_empty__", dim)。
    """
    _require_numpy()

    tokens = [
        token.strip(".,!?;:\"'()[]{}")
        for token in text.lower().split()
    ]
    tokens = [t for t in tokens if t]

    if not tokens:
        return encode_atom("__hrr_empty__", dim)

    atom_vectors = [encode_atom(token, dim) for token in tokens]
    return bundle(*atom_vectors)


def encode_fact(content: str, entities: list[str], dim: int = 1024) -> "np.ndarray":
    """
    结构化编码：内容绑定到 ROLE_CONTENT，每个实体绑定到 ROLE_ENTITY，全部打包在一起。

    角色向量是保留原子："__hrr_role_content__"、"__hrr_role_entity__"

    组件：
    1. bind(encode_text(content, dim), encode_atom("__hrr_role_content__", dim))
    2. 对于每个实体：bind(encode_atom(entity.lower(), dim), encode_atom("__hrr_role_entity__", dim))
    3. 将所有组件打包在一起

    这启用了代数提取：
        unbind(fact, bind(entity, ROLE_ENTITY)) ≈ content_vector
    """
    _require_numpy()

    role_content = encode_atom("__hrr_role_content__", dim)
    role_entity = encode_atom("__hrr_role_entity__", dim)

    components: list[np.ndarray] = [
        bind(encode_text(content, dim), role_content)
    ]

    for entity in entities:
        components.append(bind(encode_atom(entity.lower(), dim), role_entity))

    return bundle(*components)


def phases_to_bytes(phases: "np.ndarray") -> bytes:
    """
    将相位向量序列化为字节。float64 到字节——dim=1024 时为 8 KB。
    """
    _require_numpy()
    return phases.tobytes()


def bytes_to_phases(data: bytes) -> "np.ndarray":
    """
    将字节反序列化为相位向量。phases_to_bytes 的逆操作。

    需要 .copy() 调用，因为 frombuffer 返回一个由字节对象支持的只读视图；
    调用者需要一个可变数组。
    """
    _require_numpy()
    return np.frombuffer(data, dtype=np.float64).copy()


def snr_estimate(dim: int, n_items: int) -> float:
    """
    全息存储的信噪比估计。

    当 n_items > 0 时，SNR = sqrt(dim / n_items)，否则为无穷大。

    当 n_items > dim / 4 时，SNR 下降到 2.0 以下，这意味着检索错误变得可能。
    当超过此阈值时记录警告。
    """
    _require_numpy()

    if n_items <= 0:
        return float("inf")

    snr = math.sqrt(dim / n_items)

    if snr < 2.0:
        logger.warning(
            "HRR storage near capacity: SNR=%.2f (dim=%d, n_items=%d). "
            "Retrieval accuracy may degrade. Consider increasing dim or reducing stored items.",
            snr,
            dim,
            n_items,
        )

    return snr
