# -*- coding: utf-8 -*-
"""verify_cycle_count.py — 独立三重循环逐步核验 cycle_count.CycleCount。

参考模型 Reference 与被测实现完全独立：它只按规格直接维护重数字典，
总数一律用字面三重循环

    for (a,b) in R:  for (b',c) in S:  for (c',a') in T:
        若 b'==b 且 c'==c 且 a'==a:  total += mR·mS·mT

从零重算。驱动器把同一串（含非法操作的）更新序列同时喂给两者，
**每一步**都比对 add 的返回值 / ValueError 行为以及 count() 的取值。

运行：python3 verify_cycle_count.py   （全部通过时退出码 0）
"""
import math
import random
import sys

from cycle_count import CycleCount

TABLES = ("R", "S", "T")


# ---------------------------------------------------------------- 独立参考

def triple_loop_total(pairs, mults):
    """字面三重循环重算 Σ mR(a,b)·mS(b,c)·mT(c,a)。"""
    r_pairs, s_pairs, t_pairs = pairs
    m_r, m_s, m_t = mults
    total = 0
    for (a, b) in r_pairs:
        for (b2, c) in s_pairs:
            if b2 != b:
                continue
            for (c2, a2) in t_pairs:
                if c2 == c and a2 == a:
                    total += (
                        m_r.get((a, b), 0)
                        * m_s.get((b2, c), 0)
                        * m_t.get((c2, a2), 0)
                    )
    return total


class Reference:
    """独立参考模型：直接按规格维护重数，总数一律由三重循环重算。"""

    def __init__(self, r, s, t):
        self.pairs = ([tuple(p) for p in r], [tuple(p) for p in s],
                      [tuple(p) for p in t])
        self.allowed = [set(p) for p in self.pairs]
        self.mults = [{}, {}, {}]

    def add(self, table, left, right, delta):
        if not isinstance(table, str) or table not in TABLES:
            raise ValueError(f"bad table {table!r}")
        if isinstance(delta, bool) or not isinstance(delta, int):
            raise ValueError(f"bad delta {delta!r}")
        idx = TABLES.index(table)
        pair = (left, right)
        try:
            known = pair in self.allowed[idx]
        except TypeError:  # 不可哈希的键视为未知键对
            known = False
        if not known:
            raise ValueError(f"unknown pair {pair!r}")
        new = self.mults[idx].get(pair, 0) + delta
        if new < 0:
            raise ValueError(f"negative multiplicity {new}")
        if new:
            self.mults[idx][pair] = new
        else:
            self.mults[idx].pop(pair, None)
        return self.count()

    def count(self):
        return triple_loop_total(self.pairs, self.mults)


# ---------------------------------------------------------------- 测试用具

def apply_both(cc, ref, op):
    """把同一操作喂给两个实现，要求结果（返回值或 ValueError）一致。"""
    try:
        expected = ("ok", ref.add(*op))
    except ValueError:
        expected = ("err", None)
    try:
        got = ("ok", cc.add(*op))
    except ValueError:
        got = ("err", None)
    assert got == expected, f"操作 {op!r}：参考 {expected}，被测 {got}"
    assert cc.count() == ref.count(), (
        f"操作 {op!r} 后 count 不一致：参考 {ref.count()}，被测 {cc.count()}"
    )
    assert isinstance(cc.count(), int) and not isinstance(cc.count(), bool)
    return got


def shape_complete(na, nb, nc):
    """完全三部：R=A×B，S=B×C，T=C×A。"""
    a = [f"a{i}" for i in range(na)]
    b = [f"b{i}" for i in range(nb)]
    c = [f"c{i}" for i in range(nc)]
    return ([(x, y) for x in a for y in b],
            [(y, z) for y in b for z in c],
            [(z, x) for z in c for x in a])


def shape_random(rng, na, nb, nc, p):
    """随机子集三部。"""
    a = [f"a{i}" for i in range(na)]
    b = [f"b{i}" for i in range(nb)]
    c = [f"c{i}" for i in range(nc)]
    pick = lambda pairs: [q for q in pairs if rng.random() < p]
    return (pick([(x, y) for x in a for y in b]),
            pick([(y, z) for y in b for z in c]),
            pick([(z, x) for z in c for x in a]))


def shape_star(d):
    """单热点星型：b0 的 S 度、a0 的 T 度均为 d。"""
    return ([("a0", "b0")],
            [("b0", f"c{i}") for i in range(d)],
            [(f"c{i}", "a0") for i in range(d)])


def random_op(rng, pairs):
    """生成一个随机操作，含少量非法 table / delta / 未知键对。"""
    flat = [(ti, p) for ti in range(3) for p in pairs[ti]]
    roll = rng.random()
    if roll < 0.06:
        table = rng.choice(["r", "Q", "", 0, None, ["R"]])
    else:
        table = None
    if roll < 0.12 and roll >= 0.06:
        delta = rng.choice([True, False, 1.5, "2", None])
    else:
        delta = rng.randint(-3, 3)
    if roll < 0.18 and roll >= 0.12:
        ti = rng.randrange(3)
        while True:
            pair = (f"x{rng.randrange(10**6)}", f"y{rng.randrange(10**6)}")
            if pair not in set(pairs[ti]):
                break
        return (TABLES[ti] if table is None else table, pair[0], pair[1], delta)
    ti, (l, r_) = flat[rng.randrange(len(flat))]
    return (TABLES[ti] if table is None else table, l, r_, delta)


def run_random_case(name, pairs, seeds, n_ops, max_mult_seen):
    for seed in seeds:
        rng = random.Random(seed)
        cc = CycleCount(*pairs)
        ref = Reference(*pairs)
        assert cc.count() == ref.count() == 0
        for step in range(n_ops):
            op = random_op(rng, pairs)
            apply_both(cc, ref, op)
            cur = cc.count()
            assert 0 <= cur, "总数不应为负"
            max_mult_seen[0] = max(max_mult_seen[0], cur)
    print(f"[OK] {name:<34} seeds={len(seeds)} ops/seed={n_ops}")


# ---------------------------------------------------------------- 各测试组

def test_spec_example():
    cc = CycleCount([["a", "b"]], [["b", "c"]], [["c", "a"]])
    got = [
        cc.add("R", "a", "b", 2),
        cc.add("S", "b", "c", 3),
        cc.add("T", "c", "a", 4),
        cc.add("S", "b", "c", -1),
    ]
    assert got == [0, 0, 24, 16], got
    assert cc.count() == 16
    print("[OK] 规格示例：加 R2/S3/T4 -> 0,0,24；S-1 -> 16")


def test_zero_and_readd():
    cc = CycleCount([["a", "b"]], [["b", "c"]], [["c", "a"]])
    ref = Reference([["a", "b"]], [["b", "c"]], [["c", "a"]])
    ops = [
        ("R", "a", "b", 5), ("S", "b", "c", 7), ("T", "c", "a", 9),  # 315
        ("S", "b", "c", -7),   # 归零 -> 0
        ("S", "b", "c", 3),    # 重加 -> 135
        ("R", "a", "b", -5),   # 归零 -> 0
        ("R", "a", "b", 2),    # 重加 -> 54
        ("T", "c", "a", -9),   # 归零 -> 0
        ("T", "c", "a", -1),   # 非法：负重数
        ("T", "c", "a", 4),    # 重加 -> 24
    ]
    for op in ops:
        apply_both(cc, ref, op)
    assert cc.count() == 24
    print("[OK] 归零重加与交错修改逐步一致（含非法负重数拒绝）")


def test_constructor_validation():
    bad = [
        (([["a", "b"], ["a", "b"]], [], []), "重复键对"),
        (([["a", "b", "c"]], [], []), "长度不为 2"),
        (([["a"]], [], []), "长度不为 2"),
        ((["ab"], [], []), "字符串不是键对"),
        (([[1, "b"]], [], []), "非字符串键"),
        (([["a", None]], [], []), "非字符串键"),
        ((42, [], []), "不可迭代"),
        ((None, [], []), "不可迭代"),
    ]
    for args, desc in bad:
        try:
            CycleCount(*args)
        except ValueError:
            pass
        else:
            raise AssertionError(f"构造未拒绝：{desc}")
    # 元组键对、生成器输入均可接受
    cc = CycleCount((("a", "b"),), (("b", "c"),), (("c", "a"),))
    assert cc.add("R", "a", "b", 1) == 0
    cc = CycleCount((p for p in [["a", "b"]]), [["b", "c"]], [["c", "a"]])
    assert cc.count() == 0
    print("[OK] 构造校验：重复/畸形/非字符串键对均抛 ValueError")


def test_invalid_updates():
    cc = CycleCount([["a", "b"]], [["b", "c"]], [["c", "a"]])
    ref = Reference([["a", "b"]], [["b", "c"]], [["c", "a"]])
    apply_both(cc, ref, ("R", "a", "b", 2))
    apply_both(cc, ref, ("S", "b", "c", 3))
    apply_both(cc, ref, ("T", "c", "a", 4))  # 总数 24
    invalid_ops = [
        ("r", "a", "b", 1), ("Q", "a", "b", 1), ("", "a", "b", 1),
        (0, "a", "b", 1), (None, "a", "b", 1), (["R"], "a", "b", 1),
        ("R", "a", "b", True), ("R", "a", "b", False),
        ("R", "a", "b", 1.0), ("R", "a", "b", "1"), ("R", "a", "b", None),
        ("R", "a", "c", 1), ("R", "x", "y", 1), ("S", "a", "b", 1),
        ("T", "c", "b", 1), ("R", ["a"], "b", 1),
        ("S", "b", "c", -4),   # 3-4 < 0：负重数
        ("T", "c", "a", -5),   # 4-5 < 0：负重数
    ]
    for op in invalid_ops:
        before = cc.count()
        apply_both(cc, ref, op)  # 两侧都应抛 ValueError
        assert cc.count() == before == 24, f"{op!r} 后状态被改变"
    # 拒绝之后仍可正常更新（状态确实未被污染）
    apply_both(cc, ref, ("S", "b", "c", -1))
    assert cc.count() == 16
    print(f"[OK] 非法更新 {len(invalid_ops)} 种均抛 ValueError 且状态不变")


def test_edge_cases():
    # 空关系
    cc = CycleCount([], [], [])
    assert cc.count() == 0
    apply_both(cc, Reference([], [], []), ("R", "a", "b", 1))  # 未知键对
    # 无三角形的实例：总数恒为 0
    cc = CycleCount([["a1", "b1"]], [["b2", "c1"]], [["c2", "a2"]])
    ref = Reference([["a1", "b1"]], [["b2", "c1"]], [["c2", "a2"]])
    for op in [("R", "a1", "b1", 9), ("S", "b2", "c1", 9), ("T", "c2", "a2", 9)]:
        apply_both(cc, ref, op)
    assert cc.count() == 0
    # delta=0 是合法空操作；大整数可用
    cc = CycleCount([["a", "b"]], [["b", "c"]], [["c", "a"]])
    ref = Reference([["a", "b"]], [["b", "c"]], [["c", "a"]])
    apply_both(cc, ref, ("R", "a", "b", 0))
    apply_both(cc, ref, ("R", "a", "b", 10 ** 30))
    apply_both(cc, ref, ("S", "b", "c", 10 ** 30))
    apply_both(cc, ref, ("T", "c", "a", 1))
    assert cc.count() == 10 ** 60
    print("[OK] 边界：空关系 / 无三角形 / delta=0 / 大整数")


def test_randomized():
    seen = [0]
    rng = random.Random(20261115)
    # 小而密的随机实例（大量三角形碰撞）
    for i in range(4):
        pairs = shape_random(rng, 3, 4, 3, 0.75)
        run_random_case(f"随机稠密 small#{i}", pairs, seeds=range(3), n_ops=300,
                        max_mult_seen=seen)
    # 触发三张热点表的不同形状（度数^2 > M+1）
    run_random_case("完全三部 ST 表 (4,4,10)", shape_complete(4, 4, 10),
                    seeds=range(3), n_ops=250, max_mult_seen=seen)
    run_random_case("完全三部 RS 表 (4,10,4)", shape_complete(4, 10, 4),
                    seeds=range(3), n_ops=250, max_mult_seen=seen)
    run_random_case("完全三部 RT 表 (12,2,4)", shape_complete(12, 2, 4),
                    seeds=range(3), n_ops=250, max_mult_seen=seen)
    run_random_case("单热点星型 d=30", shape_star(30),
                    seeds=range(3), n_ops=300, max_mult_seen=seen)
    run_random_case("稀疏随机 (6,6,6,p=0.3)", shape_random(rng, 6, 6, 6, 0.3),
                    seeds=range(3), n_ops=300, max_mult_seen=seen)
    assert seen[0] > 0, "随机核验未产生任何非零总数，覆盖不足"
    print(f"[OK] 随机核验中出现的最大总数 = {seen[0]}")


def test_complexity_bounds():
    """用诊断计数回归验证：热点场景 O(1)，稠密场景 O(√(M+1))。"""
    # 星型热点：R 更新走 ST 表，访问量应为小常数
    d = 5000
    pairs = shape_star(d)
    cc = CycleCount(*pairs)
    for (x, y) in pairs[1]:
        cc.add("S", x, y, 1)
    for (x, y) in pairs[2]:
        cc.add("T", x, y, 1)
    cc.reset_probe()
    k = 200
    for i in range(k):
        cc.add("R", "a0", "b0", 1 if i % 2 == 0 else -1)
    d_ops, i_ops = cc.probe()
    star_per_update = d_ops // k
    assert star_per_update <= 64, f"热点场景单次更新字典访问过多：{d_ops / k}"
    # 对照：朴素扫描需要 2*d 次访问
    assert 2 * d > 100 * star_per_update, "热点分解未生效？"
    # 稠密无热点：扫描长度 ≈ h ≈ √(M/3) ≤ θ
    h = 40
    pairs = shape_complete(h, h, h)
    cc = CycleCount(*pairs)
    cc.reset_probe()
    k = 200
    for i in range(k):
        cc.add("R", "a0", "b0", 1 if i % 2 == 0 else -1)
    d_ops, _ = cc.probe()
    m = sum(len(p) for p in pairs)
    theta = math.isqrt(m + 1) + 1
    assert d_ops // k <= 4 * theta + 16, (
        f"稠密场景单次更新 {d_ops / k:.0f} 次字典访问，超过 4θ+16={4 * theta + 16}"
    )
    print(f"[OK] 复杂度回归：星型热点 R 更新 {star_per_update} 次访问/次（常数）；"
          f"稠密 h={h} 时 {d_ops // k} 次 ≤ 4θ+16 (θ≈{theta})")


def main():
    print("== 独立三重循环逐步核验 ==")
    test_spec_example()
    test_zero_and_readd()
    test_constructor_validation()
    test_invalid_updates()
    test_edge_cases()
    test_randomized()
    test_complexity_bounds()
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except AssertionError as exc:
        print(f"VERIFY FAILED: {exc}", file=sys.stderr)
        sys.exit(1)
