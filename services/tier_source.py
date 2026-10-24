"""档位来源（tier_source）的单一语义定义。

`products` 表里 `tier` 与 `tier_source` 是一对：档位值本身不携带「谁写的」信息，
所以 `tier_source` 必须由**每一个**写 `tier` 的入口同步维护，否则锁定语义失效。

历史上这里踩过两个坑（2026-10-22 审计）：

1. 人工入口（`api/catalog_mutations_api.py`、`api/misc_legacy_api.py`）改 `tier`
   时不写 `tier_source`，留下一批 `tier` 非空但来源为空的行。表面看不出问题，
   但它们会被 `scripts/sync_five_dim_tier.py` 当成人工锁定永久跳过。
2. 两套算法对「来源为空」的理解**相反**：
   - `scripts/sync_five_dim_tier.is_locked` 判定「非空档位 + 来源不在算法集合」= 锁定，
     即来源为空 → **锁定**；
   - `services/product_matrix_service.apply_tier_writeback` 判定
     `if current_source and current_source != TIER_SOURCE_TAG: skip`，
     即来源为空 → **可覆盖**。
   同一个空值，一边保护一边放行，取决于哪个算法先跑。

本模块把语义收敛成一条规则（与 `sync_five_dim_tier` 原有行为一致，即保守侧）：

    锁定 当且仅当  档位非空 且 来源不是算法标记

意味着「来源为空但有档位」一律视为人工/外来赋值，算法不得覆盖；
空档位（尚未分层）无论来源如何都可写，否则新商品永远进不了分层。
"""

MANUAL_TIER_SOURCE = 'manual'

#: 算法自己写入档位时使用的来源标记。只有这两个值允许被算法改写。
TIER_SOURCE_MATRIX = 'matrix-auto'
TIER_SOURCE_FIVE_DIM = 'five-dim-auto'
ALGORITHM_TIER_SOURCES = frozenset({TIER_SOURCE_MATRIX, TIER_SOURCE_FIVE_DIM})


def _blank(value):
    return (value or '').strip()


def is_tier_locked(tier, tier_source):
    """档位是否被人工锁定（算法不得覆盖）。

    空档位永远不算锁定——那是「还没分层」，不是「人工选定」。
    有档位且来源为空也算锁定：来源缺失只说明写入口没记账，不说明可以随便改。
    """
    if not _blank(tier):
        return False
    return _blank(tier_source) not in ALGORITHM_TIER_SOURCES


def tier_source_for_write(field, current_source):
    """人工改字段时应写入的 `tier_source` 值。

    只有 `tier` 需要联动来源标记；改 `style`/`scene`/`manager`/`remark` 不动它
    （这些字段与分层无关，动它们会让历史来源失真）。
    """
    if (field or '').strip() != 'tier':
        return _blank(current_source)
    return MANUAL_TIER_SOURCE
