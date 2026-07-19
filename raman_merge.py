#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
raman_merge.py — Raman 多曲线合并工具（LabRAM/LabSpec txt → Origin-ready txt + waterfall 预览）

功能
----
1. 扫描输入文件夹中的 .txt 数据文件，按文件名自然序（数值序）排序；
2. 自动跳过仪器表头，提取两列数据（Raman shift, Intensity）；
3. X 网格一致的曲线共用第一列 X，其余依次为 Y（顺序 = 文件排序）；
   X 网格不一致的文件追加在最后，各自成对 x2 y2 / x3 y3 ...；
4. 首行为标签行（样品编号 = 文件名去后缀），对应 Origin 的 Long Name；
5. 可选：输出 Origin 样板风格的 waterfall 预览 PNG（曲线纵向错开不重叠）。

用法
----
    python raman_merge.py -i ./data -o merged.txt
    python raman_merge.py -i ./data -o merged.txt --preview preview.png
    python raman_merge.py -i ./data -o merged.txt --preview p.png --offset 3500 --xlim 50 600 --ylim 0 20000
    python raman_merge.py -i ./data -o merged.txt --preview p.png --xlabel "Wavenumber (cm$^{-1}$)" --ylabel "Counts"

依赖：numpy（必需）；matplotlib（仅 --preview 需要）。
"""

import argparse
import os
import re
import sys

import numpy as np


# ---------------------------------------------------------------- 解析

def natural_key(name):
    """自然序排序键：1, 2, 3, 5, 11, 12, 14（而非 1, 11, 12, 14, 2 ...）"""
    stem = os.path.splitext(os.path.basename(name))[0]
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", stem)]


def _try_parse(line):
    """尝试把一行解析为 (x, y) 两个浮点数；容忍 tab/空格/逗号分隔与小数逗号。"""
    parts = line.replace(",", ".").split("\t")
    if len(parts) < 2:
        parts = line.replace(",", ".").split()
    if len(parts) < 2:
        return None
    try:
        return float(parts[0]), float(parts[1])
    except ValueError:
        return None


def parse_txt(path, run_len=5):
    """读取 LabRAM/LabSpec 导出 txt：自动跳过表头，返回 (x, y) 两个 ndarray。

    表头行数每次可能不同，因此不数行号，按内容定位：
    - 数据起点 = 首个"连续 run_len 行都是两列数字"的位置
      （防止表头中混入个别看似数字的行被误判为数据）；
    - 起点之后只收集数字行，尾部一律视为真实数据、绝不修剪；
    - 表头中可能含 latin-1 特殊字符（µ、¹），用 errors='replace' 容忍；
    - 自动保证 x 升序。
    """
    with open(path, encoding="utf-8-sig", errors="replace") as fh:
        lines = fh.read().splitlines()

    parsed = [_try_parse(ln.strip()) if ln.strip() else None for ln in lines]

    start = None
    for i in range(len(parsed) - run_len + 1):
        if all(p is not None for p in parsed[i:i + run_len]):
            start = i
            break
    if start is None:
        raise ValueError(f"未找到连续 {run_len} 行的数据区: {path}")

    xs, ys = [], []
    for p in parsed[start:]:
        if p is not None:
            xs.append(p[0])
            ys.append(p[1])
    x, y = np.asarray(xs), np.asarray(ys)

    # 仅修剪头部：紧贴数据区起点的假数字行（步长/方向与主体不一致）剥掉。
    # 末端一定是真实数据，不做任何尾部检查或修剪。
    # Raman x 网格步长均匀，中位步长由数百个真实点决定，个别垃圾点不影响。
    while len(x) > 2:
        m = np.median(np.diff(x))
        if m == 0:
            break
        d = x[1] - x[0]
        if (d > 0) != (m > 0) or abs(d) > 3 * abs(m):
            x, y = x[1:], y[1:]
        else:
            break

    if x[0] > x[-1]:                       # 降序则翻转
        x, y = x[::-1], y[::-1]
    return x, y


# ---------------------------------------------------------------- 合并

def merge_datasets(datasets, rtol=1e-9):
    """datasets: [(label, x, y), ...] 已排序。

    返回 (columns, col_names, outliers)：
    - X 与首个文件一致的进主组：columns = [X, Y1, Y2, ...]
    - 不一致的按原顺序追加为 x2 <样品名> / x3 <样品名> ... 列对，并记录在 outliers。
    """
    ref_x = datasets[0][1]
    main, extra = [], []
    for label, x, y in datasets:
        if len(x) == len(ref_x) and np.allclose(x, ref_x, rtol=rtol, atol=1e-9):
            main.append((label, y))
        else:
            extra.append((label, x, y))

    columns = [ref_x] + [y for _, y in main]
    col_names = ["Raman shift"] + [label for label, _ in main]

    for k, (label, x, y) in enumerate(extra, start=2):
        columns += [x, y]
        col_names += [f"x{k}", label]      # X 列编为 xn，Y 列保留样品名
    return columns, col_names, extra


def _fmt(v):
    """保留源精度地格式化数值：51.1972 / 998.555 / 374"""
    s = f"{v:.6f}".rstrip("0").rstrip(".")
    return s if s else "0"


def write_merged(path, columns, col_names):
    """不等长列用空字符串补齐，tab 分隔，首行为标签行。"""
    n = max(len(c) for c in columns)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\t".join(col_names) + "\n")
        buf = []
        for i in range(n):
            row = [_fmt(c[i]) if i < len(c) else "" for c in columns]
            buf.append("\t".join(row))
        fh.write("\n".join(buf) + "\n")


# ---------------------------------------------------------------- 预览

# 从 Origin 样板图取样得到的默认配色（按曲线顺序循环）
ORIGIN_COLORS = ["#000000", "#F14040", "#1A6FDF", "#37AD6B",
                 "#B177DE", "#CC9900", "#16A3A3", "#E97132"]

# 默认坐标轴标题（GUI 与 CLI 共用；$...$ 为 matplotlib mathtext）
DEFAULT_XLABEL = "Raman shift (cm$^{-1}$)"
DEFAULT_YLABEL = "Intensity (a.u.)"


def check_axis_title(title):
    """坐标标题预检：$ 不配对会在绘图时抛 mathtext 错误，提前给出中文提示。"""
    if title and title.count("$") % 2:
        raise ValueError(
            f"坐标标题中 $ 不配对: {title!r}（上下标需写成成对的 $...$，如 cm$^{{-1}}$）")


def make_preview(series, out_png, offset="auto",
                 xlim=(50, 600), ylim=None,
                 xlabel=None, ylabel=None):
    """按 Origin 样板风格绘制 waterfall 预览图。

    series: [(label, x, y), ...]，每条曲线带自己的 X（x2y2 曲线也绘制）。
    offset: "auto" → 1.05 × 最大峰高（峰-基线差）；或给定数值步长。
    ylim: None → 按曲线数自动扩展，保证最上面的曲线完整可见。
    xlabel/ylabel: 坐标轴标题；None 或空串 → 用默认标题。
    """
    xlabel = xlabel or DEFAULT_XLABEL
    ylabel = ylabel or DEFAULT_YLABEL
    check_axis_title(xlabel)
    check_axis_title(ylabel)
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import font_manager

    # 优先用 Arial 度量兼容字体（不改动全局 rcParams）
    avail = {f.name for f in font_manager.fontManager.ttflist}
    font = next((f for f in ("Liberation Sans", "Arial", "Helvetica") if f in avail), None)
    fp = {"fontfamily": font} if font else {}

    ys = [y for _, _, y in series]
    hmax = max(float(y.max() - np.median(y)) for y in ys)
    s = str(offset or "").strip().lower()
    if s in ("", "auto"):
        step = 1.05 * hmax                      # auto = 105%
    elif s in ("0", "重叠", "overlap"):           # 完全重叠，无错开（"0" 为现行写法，其余兼容旧值）
        step = 0.0
    elif s.endswith("%"):                       # 百分比：相对最大峰高
        step = float(s[:-1]) / 100.0 * hmax
    else:
        step = float(s)

    fig, ax = plt.subplots(figsize=(10.0, 7.4), dpi=150)
    for i, ((label, x, y), c) in enumerate(zip(series, ORIGIN_COLORS)):
        ax.plot(x, y + i * step, color=c, lw=1.2, label=label)

    ax.set_xlim(*xlim)
    if ylim is None:                       # 自动：最顶曲线完整可见 + 5% 余量
        top = step * (len(series) - 1) + max(float(y.max()) for y in ys)
        ylim = (0, top * 1.05)
    ax.set_ylim(*ylim)
    ax.set_xticks([200, 400, 600])
    ax.set_xlabel(xlabel, fontsize=22, **fp)
    ax.set_ylabel(ylabel, fontsize=22, **fp)
    ax.tick_params(axis="both", which="major", labelsize=20,
                   direction="out", length=6, width=1.2)
    for side in ("left", "bottom", "top", "right"):   # 四边方框，顶/右无刻度
        ax.spines[side].set_visible(True)
        ax.spines[side].set_linewidth(1.2)
        ax.spines[side].set_color("black")
    ax.tick_params(top=False, right=False)
    # 图例外置在坐标区右侧，无黑框；set_in_layout(False) 防止 tight_layout
    # 为容纳长名图例把坐标框压扁（外挂图例不参与布局）
    leg = ax.legend(loc="center left", bbox_to_anchor=(1.02, 0.5),
                    frameon=False, fontsize=16, handlelength=1.6,
                    borderpad=0.6, labelspacing=0.45)
    leg.set_in_layout(False)
    fig.tight_layout(rect=(0, 0, 0.87, 1))
    # 样品名过长时图例会超出画布右缘被裁：实测图例宽度，不够就把画布向右
    # 加宽（rect 右界按比例收缩，坐标框绝对宽度不变）；量测须用 Agg 画布
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    FigureCanvasAgg(fig).draw()
    bb = leg.get_window_extent(fig.canvas.get_renderer())
    W, H = fig.get_size_inches()
    over = bb.x1 / fig.dpi + 0.15 - W
    if over > 0:
        fig.set_size_inches(W + over, H)
        fig.tight_layout(rect=(0, 0, 0.87 * W / (W + over), 1))
    fig.savefig(out_png)
    plt.close(fig)
    return step


# ---------------------------------------------------------------- 主流程

def main():
    ap = argparse.ArgumentParser(description="Raman txt 合并 + waterfall 预览")
    ap.add_argument("-i", "--input-dir", required=True, help="txt 文件所在文件夹")
    ap.add_argument("-o", "--output", required=True, help="合并输出 txt 路径")
    ap.add_argument("--preview", metavar="PNG", help="输出预览图路径（可选）")
    ap.add_argument("--offset", default="auto",
                    help='错开步长: "auto"(=105%%)、0(完全重叠)、百分比(如 110%%) 或绝对数值')
    ap.add_argument("--xlim", nargs=2, type=float, default=[50, 600])
    ap.add_argument("--ylim", nargs=2, type=float, default=None,
                    help="Y 轴范围（默认自动按曲线数扩展）")
    ap.add_argument("--xlabel", default=None,
                    help=f'X 轴标题（默认 "{DEFAULT_XLABEL}"）')
    ap.add_argument("--ylabel", default=None,
                    help=f'Y 轴标题（默认 "{DEFAULT_YLABEL}"）')
    args = ap.parse_args()

    out_base = os.path.basename(args.output)
    txts = [f for f in os.listdir(args.input_dir)
            if f.lower().endswith(".txt") and f != out_base]  # 排除上次输出
    txts.sort(key=natural_key)
    if not txts:
        sys.exit("输入文件夹中没有 .txt 文件")

    datasets = []
    for f in txts:
        label = os.path.splitext(f)[0]
        try:
            x, y = parse_txt(os.path.join(args.input_dir, f))
        except ValueError as e:
            print(f"  跳过 {f}: {e}")
            continue
        datasets.append((label, x, y))
        print(f"  读取 {f:<10s} n={len(x)}  x: {x[0]:.4f} -> {x[-1]:.4f}")
    if not datasets:
        sys.exit("没有可解析的数据文件")

    columns, col_names, extra = merge_datasets(datasets)
    write_merged(args.output, columns, col_names)
    print(f"\n合并完成 -> {args.output}")
    print(f"  列: {col_names}")
    if extra:
        print(f"  注意: {len(extra)} 条曲线 X 网格不一致，已追加为 xn + 样品名列对: "
              f"{[e[0] for e in extra]}")

    if args.preview:
        # 所有曲线都绘制（x2y2 曲线用各自 X）
        series = [(l, x, y) for (l, x, y) in datasets]
        step = make_preview(series, args.preview,
                            offset=args.offset,
                            xlim=tuple(args.xlim),
                            ylim=tuple(args.ylim) if args.ylim else None,
                            xlabel=args.xlabel, ylabel=args.ylabel)
        print(f"预览图 -> {args.preview}  (offset step = {step:.0f})")


if __name__ == "__main__":
    main()
