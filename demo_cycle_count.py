# -*- coding: utf-8 -*-
"""demo_cycle_count.py — CycleCount 更新演示。

演示内容：
1. 题目规格示例（返回值依次为 0、0、24、16）；
2. 归零与重加；
3. 多三角形实例上的三表交错修改；
4. 各类非法更新被拒绝且状态不变；
5. 热点实例上单次更新访问量的直观展示（不扫描热点全部邻居）。

运行：python3 demo_cycle_count.py
"""
from cycle_count import CycleCount


def show(desc, value):
    print(f"  {desc:<44} -> {value}")


def demo_spec_example():
    print("== 1. 规格示例：r=[['a','b']], s=[['b','c']], t=[['c','a']] ==")
    cc = CycleCount([["a", "b"]], [["b", "c"]], [["c", "a"]])
    show("count()  [初始]", cc.count())
    show("add('R','a','b', 2)", cc.add("R", "a", "b", 2))
    show("add('S','b','c', 3)", cc.add("S", "b", "c", 3))
    show("add('T','c','a', 4)", cc.add("T", "c", "a", 4))
    show("add('S','b','c',-1)", cc.add("S", "b", "c", -1))
    assert [cc.count()] == [16]
    return cc


def demo_zero_and_readd(cc):
    print("== 2. 归零与重加（接上面的实例，当前总数 16） ==")
    show("add('S','b','c',-2)  [S 归零]", cc.add("S", "b", "c", -2))
    show("add('S','b','c', 2)  [S 重加]", cc.add("S", "b", "c", 2))
    show("add('R','a','b',-2)  [R 归零]", cc.add("R", "a", "b", -2))
    show("add('R','a','b', 1)  [R 重加]", cc.add("R", "a", "b", 1))
    assert cc.count() == 8


def demo_interleaved():
    print("== 3. 多三角形实例上的三表交错修改 ==")
    r = [["a1", "b1"], ["a1", "b2"], ["a2", "b1"]]
    s = [["b1", "c1"], ["b2", "c1"], ["b1", "c2"]]
    t = [["c1", "a1"], ["c2", "a1"], ["c1", "a2"]]
    cc = CycleCount(r, s, t)
    ops = [
        ("R", "a1", "b1", 2),
        ("S", "b1", "c1", 3),
        ("T", "c1", "a1", 1),   # 三角形 a1-b1-c1：2·3·1 = 6
        ("R", "a1", "b2", 1),
        ("S", "b2", "c1", 1),   # 三角形 a1-b2-c1：+1·1·1 = 7
        ("T", "c2", "a1", 2),
        ("S", "b1", "c2", 1),   # 三角形 a1-b1-c2：+2·1·2 = 11
        ("R", "a2", "b1", 1),
        ("T", "c1", "a2", 5),   # 三角形 a2-b1-c1：+1·3·5 = 26
        ("S", "b1", "c1", -1),  # 影响共享边 (b1,c1) 的两个三角形：-2·1·1 -1·1·5 = 19
    ]
    for op in ops:
        show(f"add{op}", cc.add(*op))
    show("count()", cc.count())
    assert cc.count() == 19


def demo_invalid():
    print("== 4. 非法更新：抛 ValueError 且状态不变 ==")
    cc = CycleCount([["a", "b"]], [["b", "c"]], [["c", "a"]])
    cc.add("R", "a", "b", 2)
    cc.add("S", "b", "c", 3)
    cc.add("T", "c", "a", 4)
    print(f"  当前总数：{cc.count()}")
    attempts = [
        ("非法 table", lambda: cc.add("r", "a", "b", 1)),
        ("布尔 delta", lambda: cc.add("R", "a", "b", True)),
        ("浮点 delta", lambda: cc.add("R", "a", "b", 1.5)),
        ("未知键对", lambda: cc.add("R", "a", "c", 1)),
        ("负重数", lambda: cc.add("S", "b", "c", -4)),
    ]
    for desc, fn in attempts:
        try:
            fn()
        except ValueError as exc:
            print(f"  {desc:<12} -> ValueError: {exc}")
        else:
            raise AssertionError(f"{desc} 未被拒绝")
    print(f"  拒绝后总数仍为：{cc.count()}")
    assert cc.count() == 24


def demo_hotspot():
    print("== 5. 热点实例：单次更新不扫描热点的全部邻居 ==")
    d = 20000
    r = [["a0", "b0"]]
    s = [["b0", f"c{i}"] for i in range(d)]   # b0 是 S-热点（度 d）
    t = [[f"c{i}", "a0"] for i in range(d)]   # a0 是 T-热点（度 d）
    cc = CycleCount(r, s, t)
    for (_, c) in s:
        cc.add("S", "b0", c, 1)
    for (c, _) in t:
        cc.add("T", c, "a0", 1)
    cc.reset_probe()
    cc.add("R", "a0", "b0", 1)
    d_ops, i_ops = cc.probe()
    print(f"  热点度 d = {d}（朴素实现需扫描 {2 * d} 次字典访问）")
    print(f"  本实现一次 R 更新：字典/集合访问 {d_ops} 次，整数乘加 {i_ops} 次")
    show("count()", cc.count())
    assert cc.count() == d


def main():
    cc = demo_spec_example()
    demo_zero_and_readd(cc)
    demo_interleaved()
    demo_invalid()
    demo_hotspot()
    print("DEMO DONE")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
