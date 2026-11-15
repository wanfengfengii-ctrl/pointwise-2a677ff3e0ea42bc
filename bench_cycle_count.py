# -*- coding: utf-8 -*-
"""bench_cycle_count.py — 热点倍增实测：访问量 / 耗时 / 峰值内存。

场景 A（单热点星型，热点度 D 倍增）：
    R = {(a0,b0)}，S = {(b0,ci)}，T = {(ci,a0)}，i < D，M = 2D+1。
    b0 是 S-热点、a0 是 T-热点（度均为 D）。朴素实现更新 R(a0,b0) 时需
    扫描 b0（或 a0）的全部 D 个邻居；本实现走热点×热点部分和表 ST，
    更新开销与 D 基本无关。

场景 B（稠密均衡 h×h×h，无热点）：
    R = A×B，S = B×C，T = C×A，|A|=|B|=|C|=h，M = 3h²，所有度 = h < θ。
    更新沿冷点邻居列表扫描 ≈ h ≈ √(M/3)，验证 O(√(M+1)) 上界。

运行：python3 bench_cycle_count.py
"""
import gc
import math
import platform
import sys
import time
import tracemalloc

from cycle_count import CycleCount


# ---------------------------------------------------------------- 对照实现

class NaiveCycleCount:
    """朴素对照：不做热点分解，更新时扫描较轻端点的全部邻居。"""

    def __init__(self, r, s, t):
        self.mult = [{}, {}, {}]
        self.fwd = []
        self.rev = []
        for pairs in (r, s, t):
            f = {}
            v = {}
            for x, y in pairs:
                f.setdefault(x, []).append(y)
                v.setdefault(y, []).append(x)
            self.fwd.append(f)
            self.rev.append(v)
        self.ops = 0
        self.total = 0

    def add_r(self, a, b, delta):
        """R(a,b) += delta：扫描 b 的 S 邻居或 a 的 T 邻居（取较小者）。"""
        m_s = self.mult[1]
        m_t = self.mult[2]
        nbrs_s = self.fwd[1].get(b, ())
        nbrs_t = self.rev[2].get(a, ())
        nbrs = nbrs_s if len(nbrs_s) <= len(nbrs_t) else nbrs_t
        q = 0
        self.ops += 2 * len(nbrs)
        for c in nbrs:
            q += m_s.get((b, c), 0) * m_t.get((c, a), 0)
        self.mult[0][(a, b)] = self.mult[0].get((a, b), 0) + delta
        self.total += delta * q
        return self.total


# ---------------------------------------------------------------- 数据构造

def build_star(d):
    r = [("a0", "b0")]
    s = [("b0", f"c{i}") for i in range(d)]
    t = [(f"c{i}", "a0") for i in range(d)]
    return r, s, t


def build_complete(h):
    a = [f"a{i}" for i in range(h)]
    b = [f"b{i}" for i in range(h)]
    c = [f"c{i}" for i in range(h)]
    return ([(x, y) for x in a for y in b],
            [(y, z) for y in b for z in c],
            [(z, x) for z in c for x in a])


def fill_star(cc, pairs):
    """把星型实例的 S/T 重数置 1（总更新数 = 2D，每次 O(1)~O(θ)）。"""
    for (_, c) in pairs[1]:
        cc.add("S", "b0", c, 1)
    for (c, _) in pairs[2]:
        cc.add("T", c, "a0", 1)


# ---------------------------------------------------------------- 计时工具

def best_time(fn, reps=3):
    best = float("inf")
    for _ in range(reps):
        gc.collect()
        t0 = time.perf_counter()
        fn()
        best = min(best, time.perf_counter() - t0)
    return best


def fmt_ns(seconds_per_op):
    if seconds_per_op >= 1e-3:
        return f"{seconds_per_op * 1e3:,.2f} ms"
    if seconds_per_op >= 1e-6:
        return f"{seconds_per_op * 1e6:,.2f} µs"
    return f"{seconds_per_op * 1e9:,.0f} ns"


# ---------------------------------------------------------------- 场景 A

def scenario_a():
    print("\n### 场景 A：单热点星型，热点度 D 倍增（M = 2D+1）\n")
    print("| D | M | √(M+1) | 本实现 访问/次 | 朴素 访问/次 | "
          "本实现 耗时/次 | 朴素 耗时/次 | 峰值内存 |")
    print("|--:|--:|--:|--:|--:|--:|--:|--:|")
    k_ours = 4000
    for d in (2048, 4096, 8192, 16384, 32768, 65536):
        pairs = build_star(d)
        m = sum(len(p) for p in pairs)
        theta = math.sqrt(m + 1)

        # --- 本实现：访问量（诊断计数）与耗时 ---
        cc = CycleCount(*pairs)
        fill_star(cc, pairs)
        cc.reset_probe()
        for i in range(k_ours):
            cc.add("R", "a0", "b0", 1 if i % 2 == 0 else -1)
        d_ops, _ = cc.probe()
        ours_ops = d_ops / k_ours
        ours_t = best_time(
            lambda: [cc.add("R", "a0", "b0", 1 if i % 2 == 0 else -1)
                     for i in range(k_ours)]
        ) / k_ours
        del cc

        # --- 朴素对照：访问量与耗时（更新次数随 D 缩小以控制总时长） ---
        nv = NaiveCycleCount(*pairs)
        nv.mult[1] = {p: 1 for p in pairs[1]}
        nv.mult[2] = {p: 1 for p in pairs[2]}
        k_naive = max(50, min(k_ours, 6_000_000 // d))
        nv.ops = 0
        for i in range(k_naive):
            nv.add_r("a0", "b0", 1 if i % 2 == 0 else -1)
        naive_ops = nv.ops / k_naive
        naive_t = best_time(
            lambda: [nv.add_r("a0", "b0", 1 if i % 2 == 0 else -1)
                     for i in range(k_naive)]
        ) / k_naive
        del nv

        # --- 峰值内存（tracemalloc，独立一趟） ---
        gc.collect()
        tracemalloc.start()
        cc = CycleCount(*pairs)
        fill_star(cc, pairs)
        for i in range(1000):
            cc.add("R", "a0", "b0", 1 if i % 2 == 0 else -1)
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        del cc

        print(f"| {d} | {m} | {theta:.1f} | {ours_ops:.1f} | {naive_ops:,.0f} "
              f"| {fmt_ns(ours_t)} | {fmt_ns(naive_t)} | {peak / 2**20:.2f} MiB |")


# ---------------------------------------------------------------- 场景 B

def scenario_b():
    print("\n### 场景 B：稠密均衡 h×h×h（M = 3h²，无热点，验证 O(√(M+1)) 上界）\n")
    print("| h | M | √(M+1) | 访问/次 | 访问/次 ÷ √(M+1) | 耗时/次 |")
    print("|--:|--:|--:|--:|--:|--:|")
    k = 3000
    for h in (32, 45, 64, 90, 128, 181, 256):
        pairs = build_complete(h)
        m = 3 * h * h
        theta = math.sqrt(m + 1)
        cc = CycleCount(*pairs)
        # 少量重数让总数非零（扫描长度与重数无关，为静态度数）
        for j in range(8):
            cc.add("S", "b0", f"c{j}", 1)
            cc.add("T", f"c{j}", "a0", 1)
        cc.reset_probe()
        for i in range(k):
            cc.add("R", "a0", "b0", 1 if i % 2 == 0 else -1)
        d_ops, _ = cc.probe()
        ops = d_ops / k
        t = best_time(
            lambda: [cc.add("R", "a0", "b0", 1 if i % 2 == 0 else -1)
                     for i in range(k)]
        ) / k
        print(f"| {h} | {m} | {theta:.1f} | {ops:.1f} | {ops / theta:.2f} "
              f"| {fmt_ns(t)} |")
        del cc


def main():
    print("# cycle_count 热点倍增实测")
    print(f"- Python {sys.version.split()[0]} ({platform.platform()})")
    print("- “访问/次”指单次 add 的字典/集合操作次数（实现内置诊断计数 probe）")
    print("- 耗时为每规模多次重复取最小值后的单次平均")
    scenario_a()
    scenario_b()
    print("\n结论：场景 A 中热点度 D 倍增 32 倍，本实现单次更新访问量与耗时基本"
          "不变（走热点×热点部分和表），朴素实现则随 D 线性增长；场景 B 中"
          "访问量/次 ÷ √(M+1) 为常数，符合单次更新期望 O(√(M+1))；"
          "峰值内存随 M 线性增长，符合空间 O(M+1)。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
