# -*- coding: utf-8 -*-
"""cycle_count — 动态维护三关系循环连接（R⋈S⋈T）的总行数。

总数定义（R/S/T 为允许键对集合，mR/mS/mT 为各键对的非负整数重数）::

    TOTAL = Σ_{a,b,c} mR(a,b)·mS(b,c)·mT(c,a)
          = Σ_{(a,b)∈R} Σ_{(b,c)∈S} Σ_{(c,a)∈T} mR(a,b)·mS(b,c)·mT(c,a)

接口
====
``CycleCount(r, s, t)``：r/s/t 为各自无重复的字符串键对列表，分别限定
R(a,b)、S(b,c)、T(c,a) 的允许键对；三类键空间独立；初始重数全为 0。

``add(table, left, right, delta)``：把 table（仅 'R'/'S'/'T'）中键对
(left, right) 的重数加上 delta（非布尔整数），返回调整后的当前总数。
非法 table、非整数/布尔 delta、未知键对、或会导致负重数的更新均抛
ValueError 且状态不变。

``count()``：返回当前总数。

索引结构与不变量
================
记 M = |R|+|S|+|T|（允许键对总数），阈值 θ = √(M+1)。对每条关系的每一侧，
按**静态度数**（该侧值出现的允许键对数，与重数无关）分类：

    deg(v)² > M+1  ⟺  v 为热点(heavy)，邻居数 > θ
    否则           ⟺  v 为冷点(light)，邻居数 ≤ θ

每侧度数之和 ≤ M，故每侧热点数 < M/θ < θ。维护三张"热点×热点"部分和表
（缺失键视为 0）：

    ST[a,b] = Σ_c mS(b,c)·mT(c,a)   仅当 b 为 S-热点 且 a 为 T-热点
    RT[b,c] = Σ_a mR(a,b)·mT(c,a)   仅当 b 为 R-热点 且 c 为 T-热点
    RS[a,c] = Σ_b mR(a,b)·mS(b,c)   仅当 a 为 R-热点 且 c 为 S-热点

不变量：每次 add 返回后，以上三式对所有热点-热点键对精确成立。构造时重数
全 0、表为空，不变量平凡成立；更新时按如下传播规则增量维护：

    R(a,b) += δ :  RT[b,·] += δ·mT(·,a)（对所有 T-热点 c，要求 b 为 R-热点）
                   RS[a,·] += δ·mS(b,·)（对所有 S-热点 c，要求 a 为 R-热点）
    S(b,c) += δ :  ST[·,b] += δ·mT(c,·)（对所有 T-热点 a，要求 b 为 S-热点）
                   RS[·,c] += δ·mR(·,b)（对所有 R-热点 a，要求 c 为 S-热点）
    T(c,a) += δ :  ST[a,·] += δ·mS(·,c)（对所有 S-热点 b，要求 a 为 T-热点）
                   RT[·,c] += δ·mR(a,·)（对所有 R-热点 b，要求 c 为 T-热点）

更新算法（以 R(a,b) += δ 为例，S/T 对称）
==========================================
1. 增量 Q = Σ_c mS(b,c)·mT(c,a)：
   * b 为 S-热点且 a 为 T-热点 → O(1) 查 ST[a,b]；
   * 否则两侧至少一侧为冷点，扫描度数较小一侧的邻居列表（≤ θ 项）逐项查表
     求和。无论哪种情况都**不扫描热点（度数 > θ）的全部邻居**。
2. TOTAL += δ·Q；更新 mR(a,b)（归零即删除，可重加）。
3. 按上述传播规则维护 RT、RS：各遍历一个长度 < θ 的热点列表。

复杂度（按整数算术与字典/集合操作次数计）
========================================
* 空间 O(M+1)：允许键对集合、双向邻居索引、重数字典合计 O(M)；
  三张部分和表各 < θ² = M+1 项。
* 预处理 O(M)（不超过 O(M·√(M+1))）：建索引与热点分类；部分和表初始为空。
* 单次更新期望 O(√(M+1))：步骤 1 至多 θ 个邻居或 O(1) 查表；步骤 3 至多
  2θ 次迭代；字典/集合操作期望 O(1)。

诊断
====
``probe()`` 返回 (字典/集合操作次数, 整数乘加次数) 的累计诊断计数，
``reset_probe()`` 清零，供实测单次更新开销（见 bench_cycle_count.py）。
"""

__all__ = ["CycleCount"]


class CycleCount:
    """动态维护 TOTAL = Σ mR(a,b)·mS(b,c)·mT(c,a)。详见模块文档字符串。"""

    _INDEX = {"R": 0, "S": 1, "T": 2}

    def __init__(self, r, s, t):
        allowed = []
        fwd = []  # 每条关系：左值 -> [右值]（静态度数 = 列表长度）
        rev = []  # 每条关系：右值 -> [左值]
        m_total = 0
        for name, raw in (("R", r), ("S", s), ("T", t)):
            pairs = self._normalize(name, raw)
            allowed.append(frozenset(pairs))
            f = {}
            v = {}
            for left, right in pairs:
                f.setdefault(left, []).append(right)
                v.setdefault(right, []).append(left)
            fwd.append(f)
            rev.append(v)
            m_total += len(pairs)

        limit = m_total + 1  # 热点判据：deg**2 > limit ⟺ deg > √(M+1)
        self._allowed = allowed          # [frozenset((left, right))]
        self._mult = [{}, {}, {}]        # [dict((left, right) -> 正整数重数)]，只存非零
        self._fwd = fwd
        self._rev = rev
        self._heavy_fwd = [
            {k for k, lst in f.items() if len(lst) * len(lst) > limit} for f in fwd
        ]
        self._heavy_rev = [
            {k for k, lst in v.items() if len(lst) * len(lst) > limit} for v in rev
        ]
        self._st = {}   # (a, b) -> Σ_c mS(b,c)·mT(c,a)，b 为 S-热点且 a 为 T-热点
        self._rt = {}   # (b, c) -> Σ_a mR(a,b)·mT(c,a)，b 为 R-热点且 c 为 T-热点
        self._rs = {}   # (a, c) -> Σ_b mR(a,b)·mS(b,c)，a 为 R-热点且 c 为 S-热点
        self._total = 0
        self._ops_dict = 0  # 诊断：字典/集合操作计数
        self._ops_int = 0   # 诊断：整数乘加计数

    # ------------------------------------------------------------------ 接口

    def add(self, table, left, right, delta):
        """调整指定键对的重数并返回当前总数。非法更新抛 ValueError 且状态不变。"""
        if not isinstance(table, str) or table not in self._INDEX:
            raise ValueError(f"table 只能是 'R'/'S'/'T'，得到 {table!r}")
        idx = self._INDEX[table]
        if isinstance(delta, bool) or not isinstance(delta, int):
            raise ValueError(f"delta 必须是非布尔整数，得到 {delta!r}")
        pair = (left, right)
        try:
            known = pair in self._allowed[idx]
        except TypeError:  # left/right 不可哈希，视为未知键对
            known = False
        if not known:
            raise ValueError(f"{table} 中不存在键对 ({left!r}, {right!r})")
        mult = self._mult[idx]
        new_value = mult.get(pair, 0) + delta
        if new_value < 0:
            raise ValueError(
                f"{table}({left!r}, {right!r}) 的重数将变为负数：{new_value}"
            )
        # ---- 校验完毕，此后才改变状态 ----
        self._ops_dict += 3   # table 查表 + 允许集查询 + 重数读取
        self._ops_int += 1
        q = self._join_sum(idx, left, right)
        self._total += delta * q
        self._ops_int += 2
        if new_value:
            mult[pair] = new_value
        else:
            mult.pop(pair, None)  # 归零即删除，可重加
        self._ops_dict += 1
        self._propagate(idx, left, right, delta)
        return self._total

    def count(self):
        """返回当前总数 Σ mR(a,b)·mS(b,c)·mT(c,a)（非负整数）。"""
        return self._total

    def probe(self):
        """返回诊断计数 (字典/集合操作次数, 整数乘加次数)。"""
        return (self._ops_dict, self._ops_int)

    def reset_probe(self):
        """清零诊断计数。"""
        self._ops_dict = 0
        self._ops_int = 0

    # -------------------------------------------------------------- 构造校验

    @staticmethod
    def _normalize(name, raw):
        """把一条关系的允许键对列表规范化：每项须为长度 2 的字符串列表/元组。"""
        try:
            iterator = iter(raw)
        except TypeError:
            raise ValueError(f"{name}: 允许键对列表不可迭代：{raw!r}") from None
        pairs = []
        seen = set()
        for item in iterator:
            if not isinstance(item, (list, tuple)) or len(item) != 2:
                raise ValueError(
                    f"{name}: 键对必须是长度为 2 的列表/元组，得到 {item!r}"
                )
            left, right = item
            if not isinstance(left, str) or not isinstance(right, str):
                raise ValueError(f"{name}: 键必须是字符串，得到 {item!r}")
            pair = (left, right)
            if pair in seen:
                raise ValueError(f"{name}: 存在重复键对 {pair!r}")
            seen.add(pair)
            pairs.append(pair)
        return pairs

    # -------------------------------------------------------------- 内部算法

    def _join_sum(self, idx, x, y):
        """固定被更新键对 (x,y) 时，另两条关系沿连接属性的乘积和 Q。"""
        self._ops_dict += 2  # 两次热点集合成员判定
        if idx == 0:
            # R(a,b)：Q = Σ_c mS(b,c)·mT(c,a)，x=a，y=b
            if y in self._heavy_fwd[1] and x in self._heavy_rev[2]:
                self._ops_dict += 1
                return self._st.get((x, y), 0)
            nbrs_s = self._fwd[1].get(y)   # 所有满足 S(y,c) 的 c
            nbrs_t = self._rev[2].get(x)   # 所有满足 T(c,x) 的 c
            self._ops_dict += 2
            if not nbrs_s or not nbrs_t:
                return 0
            m_s = self._mult[1]
            m_t = self._mult[2]
            nbrs = nbrs_s if len(nbrs_s) <= len(nbrs_t) else nbrs_t
            self._ops_dict += 2 * len(nbrs)
            self._ops_int += 2 * len(nbrs)
            total = 0
            for c in nbrs:
                total += m_s.get((y, c), 0) * m_t.get((c, x), 0)
            return total
        if idx == 1:
            # S(b,c)：Q = Σ_a mR(a,b)·mT(c,a)，x=b，y=c
            if x in self._heavy_rev[0] and y in self._heavy_fwd[2]:
                self._ops_dict += 1
                return self._rt.get((x, y), 0)
            nbrs_r = self._rev[0].get(x)   # 所有满足 R(a,x) 的 a
            nbrs_t = self._fwd[2].get(y)   # 所有满足 T(y,a) 的 a
            self._ops_dict += 2
            if not nbrs_r or not nbrs_t:
                return 0
            m_r = self._mult[0]
            m_t = self._mult[2]
            nbrs = nbrs_r if len(nbrs_r) <= len(nbrs_t) else nbrs_t
            self._ops_dict += 2 * len(nbrs)
            self._ops_int += 2 * len(nbrs)
            total = 0
            for a in nbrs:
                total += m_r.get((a, x), 0) * m_t.get((y, a), 0)
            return total
        # idx == 2
        # T(c,a)：Q = Σ_b mR(a,b)·mS(b,c)，x=c，y=a
        if y in self._heavy_fwd[0] and x in self._heavy_rev[1]:
            self._ops_dict += 1
            return self._rs.get((y, x), 0)
        nbrs_r = self._fwd[0].get(y)   # 所有满足 R(y,b) 的 b
        nbrs_s = self._rev[1].get(x)   # 所有满足 S(b,x) 的 b
        self._ops_dict += 2
        if not nbrs_r or not nbrs_s:
            return 0
        m_r = self._mult[0]
        m_s = self._mult[1]
        nbrs = nbrs_r if len(nbrs_r) <= len(nbrs_s) else nbrs_s
        self._ops_dict += 2 * len(nbrs)
        self._ops_int += 2 * len(nbrs)
        total = 0
        for b in nbrs:
            total += m_r.get((y, b), 0) * m_s.get((b, x), 0)
        return total

    def _propagate(self, idx, x, y, delta):
        """按传播规则维护三张热点×热点部分和表（只遍历热点列表，长度 < θ）。"""
        self._ops_dict += 2  # 两次热点集合成员判定
        if idx == 0:
            # R(a,b) += δ，x=a，y=b
            if y in self._heavy_rev[0]:            # b 为 R-热点
                m_t = self._mult[2]
                rt = self._rt
                for c in self._heavy_fwd[2]:       # 所有 T-热点 c
                    tv = m_t.get((c, x), 0)
                    self._ops_dict += 1
                    if tv:
                        rt[(y, c)] = rt.get((y, c), 0) + delta * tv
                        self._ops_dict += 2
                        self._ops_int += 2
            if x in self._heavy_fwd[0]:            # a 为 R-热点
                m_s = self._mult[1]
                rs = self._rs
                for c in self._heavy_rev[1]:       # 所有 S-热点 c
                    sv = m_s.get((y, c), 0)
                    self._ops_dict += 1
                    if sv:
                        rs[(x, c)] = rs.get((x, c), 0) + delta * sv
                        self._ops_dict += 2
                        self._ops_int += 2
        elif idx == 1:
            # S(b,c) += δ，x=b，y=c
            if x in self._heavy_fwd[1]:            # b 为 S-热点
                m_t = self._mult[2]
                st = self._st
                for a in self._heavy_rev[2]:       # 所有 T-热点 a
                    tv = m_t.get((y, a), 0)
                    self._ops_dict += 1
                    if tv:
                        st[(a, x)] = st.get((a, x), 0) + delta * tv
                        self._ops_dict += 2
                        self._ops_int += 2
            if y in self._heavy_rev[1]:            # c 为 S-热点
                m_r = self._mult[0]
                rs = self._rs
                for a in self._heavy_fwd[0]:       # 所有 R-热点 a
                    rv = m_r.get((a, x), 0)
                    self._ops_dict += 1
                    if rv:
                        rs[(a, y)] = rs.get((a, y), 0) + delta * rv
                        self._ops_dict += 2
                        self._ops_int += 2
        else:
            # T(c,a) += δ，x=c，y=a
            if y in self._heavy_rev[2]:            # a 为 T-热点
                m_s = self._mult[1]
                st = self._st
                for b in self._heavy_fwd[1]:       # 所有 S-热点 b
                    sv = m_s.get((b, x), 0)
                    self._ops_dict += 1
                    if sv:
                        st[(y, b)] = st.get((y, b), 0) + delta * sv
                        self._ops_dict += 2
                        self._ops_int += 2
            if x in self._heavy_fwd[2]:            # c 为 T-热点
                m_r = self._mult[0]
                rt = self._rt
                for b in self._heavy_rev[0]:       # 所有 R-热点 b
                    rv = m_r.get((y, b), 0)
                    self._ops_dict += 1
                    if rv:
                        rt[(b, x)] = rt.get((b, x), 0) + delta * rv
                        self._ops_dict += 2
                        self._ops_int += 2
