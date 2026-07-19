@echo off
rem Raman 合并工具启动器 —— 与 raman_gui.py、raman_merge.py 放在同一文件夹，双击运行
cd /d %~dp0
start "" pythonw raman_gui.py
