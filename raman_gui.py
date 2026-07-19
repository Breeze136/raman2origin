#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
raman_gui.py — Raman 合并工具 GUI（双击即用）

依赖：numpy、matplotlib；解析逻辑复用同目录下的 raman_merge.py（两文件须放在一起）。
运行：python raman_gui.py   （Windows 可双击 raman_gui.bat）
"""

import json
import os
import subprocess
import sys
import tkinter as tk
from itertools import cycle
from tkinter import filedialog, messagebox, ttk

import numpy as np

from raman_merge import (DEFAULT_XLABEL, DEFAULT_YLABEL, ORIGIN_COLORS,
                         check_axis_title, merge_datasets, natural_key,
                         parse_txt, write_merged)

CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".raman_gui.json")

# -------------------------------------------------- 界面文案（中/英）

LANG = {
    "zh": {
        "title": "Raman 合并工具",
        "lang_btn": "EN",
        "folder": "文件夹:", "browse": "浏览...",
        "col_use": "选用", "col_name": "文件", "col_info": "解析状态",
        "all": "全选", "none": "全不选", "up": "上移", "down": "下移",
        "remove": "移除选中",
        "params": " 绘图参数 ", "output": " 输出 ",
        "offset": "偏移:", "xrange": "X范围:", "yrange": "Y范围:",
        "xscale": "横长比:", "xtitle": "X标题:", "ytitle": "Y标题:",
        "outname": "输出名:", "savepng": "同存预览图", "todir": "存到数据文件夹",
        "choosedir": "指定位置...", "open_dir": "打开位置",
        "preview": "预览", "save": "保存",
        "st_ready": "浏览：选中数据文件夹内任意一个 txt 即可（对话框可切换只显示 txt）",
        "st_scan": "扫描完成: {n} 个 txt, {ok} 个可解析",
        "st_removed": "已移除 {name}（重新扫描可恢复）",
        "st_pick_first": "先在列表中点选要移除的文件",
        "st_preview": "预览: {n} 条曲线, 偏移步长 = {step:.0f}",
        "st_savedir": "保存位置: {d}",
        "st_saved": "已保存 {path}  ({n} 条曲线)",
        "st_extra": "；X 不一致已作 xn+样品名列: {names}",
        "st_png": "；预览图 {name}",
        "dlg_warn": "提示", "dlg_nosel": "没有勾选可解析的文件",
        "dlg_nodir": "保存位置不存在",
        "dlg_preview_fail": "预览失败", "dlg_save_fail": "保存失败",
        "dlg_png_fail": "预览图保存失败",
        "err_ylim": "已取消 Y 范围 auto，请填写完整的 Y 最小值和最大值",
        "browse_title": "选择 txt 追加到当前列表（可跨文件夹分批加；要整个文件夹就 Ctrl+A 全选）",
        "filetype_txt": "Raman 数据 txt", "filetype_all": "所有文件",
        "choose_title": "选择保存位置",
        "st_added": "已追加 {n} 个文件（{m} 个重复已跳过）",
        "st_cleared": "已清空列表",
        "clear": "全部移除",
    },
    "en": {
        "title": "Raman Merge Tool",
        "lang_btn": "中",
        "folder": "Folder:", "browse": "Browse...",
        "col_use": "Use", "col_name": "File", "col_info": "Parse status",
        "all": "All", "none": "None", "up": "Up", "down": "Down",
        "remove": "Remove",
        "params": " Plot parameters ", "output": " Output ",
        "offset": "Offset:", "xrange": "X range:", "yrange": "Y range:",
        "xscale": "W-ratio:", "xtitle": "X label:", "ytitle": "Y label:",
        "outname": "Filename:", "savepng": "Also save preview PNG",
        "todir": "Save to data folder",
        "choosedir": "Choose dir...", "open_dir": "Open folder",
        "preview": "Preview", "save": "Save",
        "st_ready": "Browse: pick any txt inside the data folder to scan it "
                    "(dialog can filter txt only)",
        "st_scan": "Scan done: {n} txt, {ok} parsed",
        "st_removed": "Removed {name} (re-scan to restore)",
        "st_pick_first": "Select a file in the list first",
        "st_preview": "Preview: {n} curves, offset step = {step:.0f}",
        "st_savedir": "Save to: {d}",
        "st_saved": "Saved {path}  ({n} curves)",
        "st_extra": "; mismatched X appended as xn+name columns: {names}",
        "st_png": "; preview {name}",
        "dlg_warn": "Note", "dlg_nosel": "No checked, parseable files",
        "dlg_nodir": "Save folder does not exist",
        "dlg_preview_fail": "Preview failed", "dlg_save_fail": "Save failed",
        "dlg_png_fail": "Preview PNG save failed",
        "err_ylim": "Y-range auto is off: fill in both Y min and max",
        "browse_title": "Pick txt files to APPEND (batch from any folders; Ctrl+A for whole folder)",
        "filetype_txt": "Raman data txt", "filetype_all": "All files",
        "choose_title": "Choose save folder",
        "st_added": "Appended {n} file(s) ({m} duplicate(s) skipped)",
        "st_cleared": "List cleared",
        "clear": "Remove all",
    },
}


# -------------------------------------------------- 纯逻辑（与界面无关，可独立测试）

def items_from_paths(paths):
    """由明确的文件路径列表构建信息项（自然序）。解析失败的标记 ok=False。"""
    items = []
    for p in sorted(paths, key=natural_key):
        f = os.path.basename(p)
        try:
            x, y = parse_txt(p)
            items.append(dict(name=f, path=p, label=os.path.splitext(f)[0],
                              x=x, y=y, ok=True,
                              msg=f"n={len(x)}   x: {x[0]:.1f}–{x[-1]:.1f}"))
        except Exception as e:
            items.append(dict(name=f, path=p, label=os.path.splitext(f)[0],
                              x=None, y=None, ok=False, msg=f"跳过: {e}"))
    return items


def scan_folder(folder):
    """扫描文件夹内 txt，返回文件信息列表（自然序）。"""
    paths = [os.path.join(folder, f)
             for f in os.listdir(folder) if f.lower().endswith(".txt")]
    return items_from_paths(paths)


def do_merge(items, out_path):
    """items: 已勾选且排好序的文件信息。写合并 txt，返回 (列名, X不一致的文件)。"""
    datasets = [(it["label"], it["x"], it["y"]) for it in items]
    columns, col_names, extra = merge_datasets(datasets)
    write_merged(out_path, columns, col_names)
    return col_names, extra


def unique_path(path):
    """重名自动加尾部编号：name_1.ext, name_2.ext ...（已存在才编号）。"""
    if not os.path.exists(path):
        return path
    base, ext = os.path.splitext(path)
    n = 1
    while os.path.exists(f"{base}_{n}{ext}"):
        n += 1
    return f"{base}_{n}{ext}"


def build_figure(series, offset="auto", xlim=(50, 600), xscale=1.0,
                 ylim=None, xlabel=None, ylabel=None):
    """构造 waterfall 预览 Figure（不依赖显示后端）。返回 (fig, step, ylim, auto_ylim)。

    series: [(label, x, y), ...]，每条曲线带自己的 X（X 网格不同的也能同图绘制）。
    xscale: 横向缩放比例，1.0 为默认；标签/图例边距（英寸）保持不变，
            只拉伸绘图区横向长度。
    ylim: None → 按曲线数自动计算；给定 (ymin, ymax) 则使用之。
    xlabel/ylabel: 坐标轴标题；None 或空串 → 用默认标题。
    """
    from matplotlib.figure import Figure

    xlabel = (xlabel or "").strip() or DEFAULT_XLABEL
    ylabel = (ylabel or "").strip() or DEFAULT_YLABEL
    check_axis_title(xlabel)
    check_axis_title(ylabel)

    ys = [y for _, _, y in series]
    hmax = max(float(y.max() - np.median(y)) for y in ys)   # 最大峰高（峰-基线差）
    s = str(offset or "").strip().lower()
    if s in ("", "auto"):
        step = 1.05 * hmax                      # auto = 105%
    elif s in ("0", "重叠", "overlap"):           # 完全重叠，无错开（"0" 为现行写法）
        step = 0.0
    elif s.endswith("%"):                       # 百分比：相对最大峰高
        try:
            v = float(s[:-1])
        except ValueError:
            raise ValueError(f"偏移格式无法识别: {offset!r}（支持 auto / 0 / 数值 / 百分比如 110%）")
        if v <= 0:
            raise ValueError("偏移百分比需大于 0")
        step = v / 100.0 * hmax
    else:                                       # 绝对数值
        try:
            step = float(s)
        except ValueError:
            raise ValueError(f"偏移格式无法识别: {offset!r}（支持 auto / 0 / 数值 / 百分比如 110%）")
        if step <= 0:
            raise ValueError("偏移需大于 0")

    try:
        xscale = min(max(float(xscale), 0.5), 3.0)
    except (TypeError, ValueError):
        xscale = 1.0

    W = 7.2 * xscale
    L_IN, R_IN = 0.86, 1.58            # 左标签边距 / 右图例区（英寸，固定）
    fig = Figure(figsize=(W, 5.2), dpi=100)
    ax = fig.add_axes((L_IN / W, 0.13, (W - L_IN - R_IN) / W, 0.83))
    for i, ((label, x, y), c) in enumerate(zip(series, cycle(ORIGIN_COLORS))):
        ax.plot(x, y + i * step, color=c, lw=1.0, label=label)
    ax.set_xlim(*xlim)
    top = step * (len(series) - 1) + max(float(y.max()) for y in ys)
    auto_ylim = (0, top * 1.05)
    if ylim is None:
        ylim = auto_ylim
    ax.set_ylim(*ylim)
    ax.set_xlabel(xlabel, fontsize=13)
    ax.set_ylabel(ylabel, fontsize=13)
    ax.tick_params(direction="out", labelsize=11, top=False, right=False)
    # 四边黑色边框组成方框（顶/右侧无刻度），对齐 Origin 风格
    for side in ("left", "bottom", "top", "right"):
        ax.spines[side].set_visible(True)
        ax.spines[side].set_color("black")
    # 图例外置在坐标区右侧，无黑框
    leg = ax.legend(loc="center left", bbox_to_anchor=(1.02, 0.5),
                    frameon=False, fontsize=10)
    # 样品名过长时图例会超出画布右缘被裁：实测图例宽度，不够就把画布向右
    # 加宽（坐标框与左边距的绝对尺寸不变，只加图例所需空间）
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    FigureCanvasAgg(fig).draw()
    bb = leg.get_window_extent(fig.canvas.get_renderer())
    over = bb.x1 / fig.dpi + 0.12 - W          # 图例右缘+余量 超出画布（英寸）
    if over > 0:
        ax.set_position((L_IN / (W + over), 0.13,
                         (W - L_IN - R_IN) / (W + over), 0.83))
        fig.set_size_inches(W + over, 5.2)
    return fig, step, ylim, auto_ylim


def save_figure_png(fig, path):
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    FigureCanvasAgg(fig)
    fig.savefig(path, dpi=150)


# -------------------------------------------------- GUI

class RamanApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.geometry("1320x720")
        self.lang = "zh"
        self.items = []          # 与 tree 行顺序一致
        self._item_of = {}       # iid → item（同名文件跨文件夹追加时按 iid 绑定，不靠 name）
        self.folder = ""
        self.save_dir = None     # 上次选择的保存目录（None = 跟随数据文件夹）
        self._canvas = None
        self._fig = None
        self._status = ("st_ready", {})
        self._build_ui()
        self._apply_lang()
        self._load_config()

    # ---------- 文案 ----------

    def _t(self, key, **kw):
        return LANG[self.lang][key].format(**kw) if kw else LANG[self.lang][key]

    def _set_status(self, key, **kw):
        """记录当前状态消息（key + 参数），语言切换时可原样重渲染。"""
        self._status = (key, kw)
        self.status_var.set(self._render_status())

    def _render_status(self):
        key, kw = self._status
        if key == "st_saved":
            msg = self._t("st_saved", path=kw["path"], n=kw["n"])
            if kw.get("extra"):
                msg += self._t("st_extra", names=kw["extra"])
            if kw.get("png"):
                msg += self._t("st_png", name=kw["png"])
            return msg
        return self._t(key, **kw)

    def on_lang_toggle(self):
        self.lang = "en" if self.lang == "zh" else "zh"
        self._apply_lang()
        self._save_config()

    def _apply_lang(self):
        t = LANG[self.lang]
        self.title(t["title"])
        self.lang_btn.configure(text=t["lang_btn"])
        self.lbl_folder.configure(text=t["folder"])
        self.browse_btn.configure(text=t["browse"])
        self.tree.heading("use", text=t["col_use"])
        self.tree.heading("name", text=t["col_name"])
        self.tree.heading("info", text=t["col_info"])
        self.btn_all.configure(text=t["all"])
        self.btn_none.configure(text=t["none"])
        self.btn_up.configure(text=t["up"])
        self.btn_down.configure(text=t["down"])
        self.btn_remove.configure(text=t["remove"])
        self.btn_clear.configure(text=t["clear"])
        self.ctl.configure(text=t["params"])
        self.ctl2.configure(text=t["output"])
        self.lbl_offset.configure(text=t["offset"])
        self.lbl_xrange.configure(text=t["xrange"])
        self.lbl_yrange.configure(text=t["yrange"])
        self.lbl_xscale.configure(text=t["xscale"])
        self.lbl_xtitle.configure(text=t["xtitle"])
        self.lbl_ytitle.configure(text=t["ytitle"])
        self.lbl_outname.configure(text=t["outname"])
        self.savepng_cb.configure(text=t["savepng"])
        self.todir_cb.configure(text=t["todir"])
        self.choosedir_btn.configure(text=t["choosedir"])
        self.open_dir_btn.configure(text=t["open_dir"])
        self.preview_btn.configure(text=t["preview"])
        self.save_btn.configure(text=t["save"])
        self.status_var.set(self._render_status())
        self._sync_left_block()        # 按钮文案变宽/窄后重算半宽矩形

    def _sync_left_block(self):
        """三行左组右缘对齐到行内容宽的一半：左组贴左成半宽矩形；
        输入框列不拉伸，右侧弹簧列吸收剩余，预览/打开位置仍钉输出行最右。"""
        if not hasattr(self, "_block_rows"):
            return
        for row, cols, _last in self._block_rows:
            for col, _w, _p in cols:
                row.columnconfigure(col, minsize=0)   # 先恢复自然宽再测量
        self.update_idletasks()
        target = self._block_rows[0][0].winfo_width() // 2
        if target < 200:      # 窗口尚未映射，跳过（build 末尾的 after 兜底会再算）
            return
        for row, cols, last in self._block_rows:
            extra = target - (last.winfo_x() + last.winfo_width())
            if extra <= 0:
                continue
            per = extra // len(cols)
            for col, w, pads in cols:
                row.columnconfigure(col, minsize=w.winfo_reqwidth() + pads + per)

    # ---------- 界面 ----------

    def _build_ui(self):
        top = ttk.Frame(self)
        top.pack(fill="x", padx=8, pady=6)
        self.lbl_folder = ttk.Label(top)
        self.lbl_folder.pack(side="left")
        self.folder_var = tk.StringVar()
        ttk.Entry(top, textvariable=self.folder_var).pack(
            side="left", fill="x", expand=True, padx=6)
        self.browse_btn = ttk.Button(top, command=self.on_browse)
        self.browse_btn.pack(side="left")
        # 中/英切换（右上角小按钮，显示目标语言）
        self.lang_btn = ttk.Button(top, width=4, command=self.on_lang_toggle)
        self.lang_btn.pack(side="right", padx=(6, 0))

        mid = ttk.Frame(self)
        mid.pack(fill="both", expand=True, padx=8)

        left = ttk.Frame(mid)
        left.pack(side="left", fill="both", expand=False)
        self.tree = ttk.Treeview(left, columns=("use", "name", "info"),
                                 show="headings", height=18, selectmode="browse")
        self.tree.column("use", width=45, anchor="center")
        self.tree.column("name", width=110)
        self.tree.column("info", width=230)
        self.tree.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(left, orient="vertical", command=self.tree.yview)
        sb.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.bind("<space>", self.on_toggle)
        self.tree.bind("<Double-1>", self.on_toggle)

        btns = ttk.Frame(mid)
        btns.pack(side="left", fill="y", padx=6)
        self.btn_all = ttk.Button(btns, command=lambda: self._set_all(True))
        self.btn_all.pack(pady=2)
        self.btn_none = ttk.Button(btns, command=lambda: self._set_all(False))
        self.btn_none.pack(pady=2)
        self.btn_up = ttk.Button(btns, command=lambda: self._move(-1))
        self.btn_up.pack(pady=2)
        self.btn_down = ttk.Button(btns, command=lambda: self._move(1))
        self.btn_down.pack(pady=2)
        self.btn_remove = ttk.Button(btns, command=self._remove_selected)
        self.btn_remove.pack(pady=2)
        self.btn_clear = ttk.Button(btns, command=self.on_clear)
        self.btn_clear.pack(pady=2)

        right = ttk.Frame(mid)
        right.pack(side="left", fill="both", expand=True)
        self.preview_frame = ttk.Frame(right)
        self.preview_frame.pack(fill="both", expand=True)

        # ---- 参数行：任一输入框回车即刷新预览（框内文字居中，含输入的数字）----
        # grid 布局：输入框列不拉伸，右侧弹簧列吸收剩余；左组右缘由 _sync_left_block
        # 对齐到行内容宽一半（半宽矩形贴左）
        self.ctl = ttk.LabelFrame(self)
        self.ctl.pack(fill="x", padx=8, pady=(4, 2))
        row1 = ttk.Frame(self.ctl)
        row1.pack(fill="x")
        self.lbl_offset = ttk.Label(row1)
        self.lbl_offset.grid(row=0, column=0, padx=(4, 0))
        self.offset_var = tk.StringVar(value="auto")
        self.offset_cb = ttk.Combobox(
            row1, textvariable=self.offset_var, width=8, justify="center",
            values=["auto", "0"] + [f"{p}%" for p in range(10, 201, 10)])
        self.offset_cb.grid(row=0, column=1, padx=(2, 10))
        self.lbl_xrange = ttk.Label(row1)
        self.lbl_xrange.grid(row=0, column=2)
        self.xmin_var = tk.StringVar(value="50")
        self.xmax_var = tk.StringVar(value="600")
        self.xmin_ent = ttk.Entry(row1, textvariable=self.xmin_var, width=7,
                                  justify="center")
        self.xmin_ent.grid(row=0, column=3, padx=2, sticky="ew")
        ttk.Label(row1, text="–").grid(row=0, column=4)
        self.xmax_ent = ttk.Entry(row1, textvariable=self.xmax_var, width=7,
                                  justify="center")
        self.xmax_ent.grid(row=0, column=5, padx=(2, 10), sticky="ew")
        self.lbl_yrange = ttk.Label(row1)
        self.lbl_yrange.grid(row=0, column=6)
        self.ymin_var = tk.StringVar(value="")
        self.ymax_var = tk.StringVar(value="")
        self.ymin_ent = ttk.Entry(row1, textvariable=self.ymin_var, width=8,
                                  justify="center",
                                  state="disabled")   # 首次绘图后才可编辑
        self.ymin_ent.grid(row=0, column=7, padx=2, sticky="ew")
        ttk.Label(row1, text="–").grid(row=0, column=8)
        self.ymax_ent = ttk.Entry(row1, textvariable=self.ymax_var, width=8,
                                  justify="center", state="disabled")
        self.ymax_ent.grid(row=0, column=9, padx=(2, 2), sticky="ew")
        # auto 勾选：默认自动（输入框禁用但实时显示当前 Y 范围），取消勾选才可手改
        self.yauto_var = tk.BooleanVar(value=True)
        self.yauto_cb = ttk.Checkbutton(row1, text="auto", variable=self.yauto_var,
                                        command=self._on_yauto_toggle)
        self.yauto_cb.grid(row=0, column=10, padx=(0, 6))
        # 输入框列不拉伸（宽度由 _sync_left_block 的 minsize 补足到半宽）
        row1.columnconfigure(11, weight=1)   # 右侧弹簧：吸收剩余，左组贴左成半宽矩形

        # 第二行：坐标轴标题 + 横长比（标题留空回车 = 恢复默认；上下标用成对 $...$）
        row2 = ttk.Frame(self.ctl)
        row2.pack(fill="x", pady=(2, 2))
        self.lbl_xtitle = ttk.Label(row2)
        self.lbl_xtitle.grid(row=0, column=0, padx=(4, 0))
        self.xlabel_var = tk.StringVar(value=DEFAULT_XLABEL)
        self.xlabel_ent = ttk.Entry(row2, textvariable=self.xlabel_var, width=31,
                                    justify="center")
        self.xlabel_ent.grid(row=0, column=1, padx=(2, 10), sticky="ew")
        self.lbl_ytitle = ttk.Label(row2)
        self.lbl_ytitle.grid(row=0, column=2)
        self.ylabel_var = tk.StringVar(value=DEFAULT_YLABEL)
        self.ylabel_ent = ttk.Entry(row2, textvariable=self.ylabel_var, width=26,
                                    justify="center")
        self.ylabel_ent.grid(row=0, column=3, padx=(2, 10), sticky="ew")
        self.lbl_xscale = ttk.Label(row2)
        self.lbl_xscale.grid(row=0, column=4)
        self.xscale_var = tk.StringVar(value="1.0")
        self.xscale_ent = ttk.Entry(row2, textvariable=self.xscale_var, width=6,
                                    justify="center")
        self.xscale_ent.grid(row=0, column=5, padx=(2, 6))
        # 标题输入框列不拉伸（同 row1，由 _sync_left_block 补足到半宽）
        row2.columnconfigure(6, weight=1)     # 右侧弹簧

        # 回车 / 下拉选择 即时刷新预览
        for w in (self.offset_cb, self.xmin_ent, self.xmax_ent,
                  self.ymin_ent, self.ymax_ent, self.xscale_ent,
                  self.xlabel_ent, self.ylabel_ent):
            w.bind("<Return>", self._on_enter)
        self.offset_cb.bind("<<ComboboxSelected>>", self._on_enter)

        # ---- 输出行：左侧输出设置（…指定位置/打开位置），最右 预览/保存 ----
        # 弹簧列55吸收剩余 → 左组与上面两行对齐成半宽矩形，右按钮组钉在最右
        self.ctl2 = ttk.LabelFrame(self)
        self.ctl2.pack(fill="x", padx=8, pady=(2, 4))
        self.lbl_outname = ttk.Label(self.ctl2)
        self.lbl_outname.grid(row=0, column=0, padx=(4, 0))
        self.outname_var = tk.StringVar(value="merged_raman.txt")
        self.outname_ent = ttk.Entry(self.ctl2, textvariable=self.outname_var,
                                     width=20, justify="center")
        self.outname_ent.grid(row=0, column=1, padx=(2, 8), sticky="ew")
        self.savepng_var = tk.BooleanVar(value=True)
        self.savepng_cb = ttk.Checkbutton(self.ctl2, variable=self.savepng_var)
        self.savepng_cb.grid(row=0, column=2)
        self.todir_var = tk.BooleanVar(value=True)
        self.todir_cb = ttk.Checkbutton(self.ctl2, variable=self.todir_var,
                                        command=self._on_todir_toggle)
        self.todir_cb.grid(row=0, column=3, padx=(4, 0))
        self.choosedir_btn = ttk.Button(self.ctl2, command=self.on_choose_dir,
                                        state="disabled")
        self.choosedir_btn.grid(row=0, column=4, padx=(4, 0))
        self.open_dir_btn = ttk.Button(self.ctl2, command=self.on_open_dir)
        self.open_dir_btn.grid(row=0, column=5, padx=(8, 4))
        # 最右按钮组：预览 在左，保存 在最右（c6 弹簧把它们顶到最右）
        self.preview_btn = ttk.Button(self.ctl2, command=self.on_preview)
        self.preview_btn.grid(row=0, column=7, padx=(4, 2))
        self.save_btn = ttk.Button(self.ctl2, command=self.on_save)
        self.save_btn.grid(row=0, column=8, padx=(2, 6))
        self.ctl2.columnconfigure(6, weight=1)   # 弹簧列（打开位置c5与预览c7之间）：
                                                 # 吸收剩余 → 左组贴左半宽，右按钮组钉最右

        # 三行左组右缘对齐到行内容宽一半（半宽矩形）：(行容器, [(列,控件,padx和)], 左组末控件)
        self._block_rows = [
            (row1, [(3, self.xmin_ent, 4), (5, self.xmax_ent, 12),
                    (7, self.ymin_ent, 4), (9, self.ymax_ent, 4)], self.yauto_cb),
            (row2, [(1, self.xlabel_ent, 12), (3, self.ylabel_ent, 12)],
             self.xscale_ent),
            (self.ctl2, [(1, self.outname_ent, 10)], self.open_dir_btn),
        ]
        self._sync_left_block()
        self.after(120, self._sync_left_block)   # 窗口映射后按实际宽度校准一次

        self.status_var = tk.StringVar()
        ttk.Label(self, textvariable=self.status_var, anchor="w",
                  relief="sunken").pack(fill="x", side="bottom")

    # ---------- 事件 ----------

    def on_browse(self):
        # 选文件对话框（右下角可切换只显示 txt）：
        # 单选/多选都 = 把选中 txt【追加】到当前列表（按路径去重）——
        # 可分批把不同文件夹的文件加进来；要整个文件夹就在对话框里 Ctrl+A 全选
        paths = filedialog.askopenfilenames(
            title=self._t("browse_title"),
            initialdir=self.folder or os.getcwd(),
            filetypes=[(self._t("filetype_txt"), "*.txt"),
                       (self._t("filetype_all"), "*.*")])
        if not paths:
            return
        self.folder = os.path.dirname(paths[0])
        self.folder_var.set(self.folder)
        self._add_items(items_from_paths(list(paths)))

    def _add_items(self, items):
        """追加文件项（按路径去重），插在列表末尾。"""
        have = {it["path"] for it in self.items}
        new = [it for it in items if it["path"] not in have]
        for it in new:
            self.items.append(it)
            iid = self.tree.insert("", "end",
                                   values=("✔" if it["ok"] else "",
                                           it["name"], it["msg"]))
            self._item_of[iid] = it
        self._set_status("st_added", n=len(new), m=len(items) - len(new))
        self._save_config()

    def on_clear(self):
        """全部移除：清空列表（配合追加语义，从空列表开始跨文件夹挑选）。"""
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        self.items = []
        self._item_of = {}
        self._set_status("st_cleared")

    def _scan(self):
        out_name = self.outname_var.get().strip()
        items = [it for it in scan_folder(self.folder)
                 if it["name"] != out_name]
        self._load_items(items)

    def _load_items(self, items, scan_status=True):
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        self.items = items
        self._item_of = {}
        self.yauto_var.set(True)            # 换数据后 Y 范围回到自动
        self._set_y_entries(False)
        for it in self.items:
            iid = self.tree.insert("", "end",
                                   values=("✔" if it["ok"] else "",
                                           it["name"], it["msg"]))
            self._item_of[iid] = it
        if scan_status:
            n_ok = sum(it["ok"] for it in self.items)
            self._set_status("st_scan", n=len(self.items), ok=n_ok)
        self._save_config()

    def _current_iid(self):
        iid = self.tree.focus()
        if not iid:
            sel = self.tree.selection()
            iid = sel[0] if sel else ""
        return iid

    def on_toggle(self, event=None):
        iid = self._current_iid()
        if iid:
            use, name, info = self.tree.item(iid, "values")
            self.tree.item(iid, values=("" if use == "✔" else "✔", name, info))

    def _set_all(self, v):
        for iid in self.tree.get_children():
            use, name, info = self.tree.item(iid, "values")
            self.tree.item(iid, values=("✔" if v else "", name, info))

    def _move(self, delta):
        iid = self.tree.focus()
        if not iid:
            return
        idx = self.tree.index(iid)
        new = idx + delta
        if 0 <= new < len(self.tree.get_children()):
            self.tree.move(iid, "", new)

    def _remove_selected(self):
        iid = self._current_iid()
        if not iid:
            self._set_status("st_pick_first")
            return
        it = self._item_of.get(iid)
        name = self.tree.item(iid, "values")[1]
        self.tree.delete(iid)
        self._item_of.pop(iid, None)
        if it is not None and it in self.items:
            self.items.remove(it)           # 按对象删：跨文件夹同名文件不误删
        self._set_status("st_removed", name=name)

    def _selected_items(self):
        """按 tree 当前顺序取勾选的、可解析的文件。"""
        out = []
        for iid, it in zip(self.tree.get_children(), self._tree_items_by_iid()):
            if self.tree.item(iid, "values")[0] == "✔" and it["ok"]:
                out.append(it)
        return out

    def _tree_items_by_iid(self):
        """tree 行 → items（按 iid 绑定，重排后 tree 顺序为准；同名文件不串）。"""
        return [self._item_of[iid] for iid in self.tree.get_children()]

    def _build_current_fig(self, sel):
        """按当前界面设置构建预览 Figure。返回 (fig, step, ylim, auto_ylim, n, manual)。

        所有勾选曲线都绘制（X 网格不同的 x2y2 曲线用各自 X）。
        """
        series = [(it["label"], it["x"], it["y"]) for it in sel]
        # Y 范围：auto 勾选 → 自动（跟随曲线数量变化）；取消勾选 → 用输入框手动值
        ylim, manual = None, False
        if not self.yauto_var.get():
            cur = (self.ymin_var.get().strip(), self.ymax_var.get().strip())
            if not all(cur):
                raise ValueError(self._t("err_ylim"))
            ylim = (float(cur[0]), float(cur[1]))
            manual = True
        # 坐标标题：留空 → 恢复默认并回显到输入框
        if not self.xlabel_var.get().strip():
            self.xlabel_var.set(DEFAULT_XLABEL)
        if not self.ylabel_var.get().strip():
            self.ylabel_var.set(DEFAULT_YLABEL)
        fig, step, ylim, auto_ylim = build_figure(
            series, self.offset_var.get().strip(),
            (float(self.xmin_var.get()), float(self.xmax_var.get())),
            xscale=self.xscale_var.get().strip(), ylim=ylim,
            xlabel=self.xlabel_var.get().strip(),
            ylabel=self.ylabel_var.get().strip())
        return fig, step, ylim, auto_ylim, len(series), manual

    def _set_y_entries(self, editable, ylim=None):
        """editable=True 允许手动编辑；=False 禁用。ylim 不为空则填入显示值
        （auto 模式下输入框禁用但仍实时显示当前 Y 范围）。"""
        st = "normal" if editable else "disabled"
        self.ymin_ent.configure(state=st)
        self.ymax_ent.configure(state=st)
        if ylim is not None:
            self.ymin_var.set(f"{ylim[0]:.0f}")
            self.ymax_var.set(f"{ylim[1]:.0f}")
        elif not editable:
            self.ymin_var.set("")
            self.ymax_var.set("")

    def _on_yauto_toggle(self):
        if self.yauto_var.get():
            self._set_y_entries(False)     # 禁用编辑，自动值由预览刷新后填入
            if self.tree.get_children():
                self.on_preview()          # 立即按自动范围重绘
        else:
            self._set_y_entries(True)      # 放开编辑，当前显示值作为修改起点

    def _on_enter(self, event=None):
        # 参数输入框回车 / 偏移下拉选择 → 即时刷新预览（无数据时静默忽略）
        if self.tree.get_children():
            self.on_preview()
        return "break"

    def on_preview(self):
        sel = self._selected_items()
        if not sel:
            messagebox.showwarning(self._t("dlg_warn"), self._t("dlg_nosel"))
            return
        try:
            self._fig, step, ylim, auto_ylim, n_main, manual = self._build_current_fig(sel)
        except Exception as e:
            messagebox.showerror(self._t("dlg_preview_fail"), str(e))
            return
        self._draw()
        if manual:
            self._set_y_entries(True)                  # 保留用户的手动值
        else:
            self._set_y_entries(False, auto_ylim)      # 禁用但实时显示最新自动值
        self._set_status("st_preview", n=n_main, step=step)
        self._save_config()

    def _draw(self):
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
        if self._canvas is not None:
            self._canvas.get_tk_widget().destroy()
        self._canvas = FigureCanvasTkAgg(self._fig, master=self.preview_frame)
        self._canvas.draw()
        # 不拉伸填充，让画布在预览区中保持原始尺寸并居中
        self._canvas.get_tk_widget().pack(expand=True)

    def _on_todir_toggle(self):
        self.choosedir_btn.configure(
            state="disabled" if self.todir_var.get() else "normal")

    def on_choose_dir(self):
        d = filedialog.askdirectory(initialdir=self.save_dir or self.folder,
                                    title=self._t("choose_title"))
        if d:
            self.save_dir = d
            self.todir_var.set(False)      # 选了指定位置就切过去
            self._on_todir_toggle()
            self._set_status("st_savedir", d=d)
            self._save_config()

    def on_open_dir(self):
        path = self.folder if self.todir_var.get() else (self.save_dir or self.folder)
        if not os.path.isdir(path):
            messagebox.showwarning(self._t("dlg_warn"), self._t("dlg_nodir"))
            return
        if sys.platform.startswith("win"):
            os.startfile(path)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])

    def on_save(self):
        sel = self._selected_items()
        if not sel:
            messagebox.showwarning(self._t("dlg_warn"), self._t("dlg_nosel"))
            return
        # 保存路径由"存到数据文件夹 / 指定位置"控件决定，本按钮不弹窗
        save_dir = self.folder if self.todir_var.get() else (self.save_dir or self.folder)
        # 重名自动加尾部编号（merged_raman_1.txt ...），预览图跟随同一编号
        out_path = unique_path(os.path.join(save_dir, self.outname_var.get().strip()))
        try:
            col_names, extra = do_merge(sel, out_path)
        except Exception as e:
            messagebox.showerror(self._t("dlg_save_fail"), str(e))
            return
        kw = dict(path=out_path, n=len(sel),
                  extra=[e[0] for e in extra] if extra else None, png=None)
        if self.savepng_var.get():
            try:
                # 新建独立 Figure 保存（与屏幕显示同源同参数、互不干扰），
                # 保证 PNG 与当前设置严格一致
                fig, *_ = self._build_current_fig(sel)
                png = os.path.splitext(out_path)[0] + "_preview.png"
                save_figure_png(fig, png)
                kw["png"] = os.path.basename(png)
            except Exception as e:
                messagebox.showerror(self._t("dlg_png_fail"), str(e))
        self._set_status("st_saved", **kw)
        self._save_config()

    # ---------- 配置 ----------
    # 记忆的键：folder, outname, xscale, xmin, xmax, xlabel, ylabel, save_dir, lang。
    # 偏移量每次启动默认 auto；存到数据文件夹每次启动默认勾选；Y 范围和 yauto 不记忆。

    def _load_config(self):
        try:
            cfg = json.load(open(CONFIG_PATH, encoding="utf-8"))
            self.folder = cfg.get("folder", "")
            self.folder_var.set(self.folder)
            self.outname_var.set(cfg.get("outname", "merged_raman.txt"))
            self.xscale_var.set(cfg.get("xscale", "1.0"))
            self.xmin_var.set(cfg.get("xmin", "50"))
            self.xmax_var.set(cfg.get("xmax", "600"))
            self.xlabel_var.set(cfg.get("xlabel", DEFAULT_XLABEL))
            self.ylabel_var.set(cfg.get("ylabel", DEFAULT_YLABEL))
            self.save_dir = cfg.get("save_dir") or None
            lang = cfg.get("lang", "zh")
            if lang in LANG and lang != self.lang:
                self.lang = lang
                self._apply_lang()
            self._on_todir_toggle()
            if self.folder and os.path.isdir(self.folder):
                self._scan()
        except Exception:
            pass

    def _save_config(self):
        try:
            json.dump({"folder": self.folder,
                       "outname": self.outname_var.get(),
                       "xscale": self.xscale_var.get(),
                       "xmin": self.xmin_var.get(),
                       "xmax": self.xmax_var.get(),
                       "xlabel": self.xlabel_var.get(),
                       "ylabel": self.ylabel_var.get(),
                       "save_dir": self.save_dir or "",
                       "lang": self.lang},
                      open(CONFIG_PATH, "w", encoding="utf-8"))
        except Exception:
            pass


if __name__ == "__main__":
    RamanApp().mainloop()
