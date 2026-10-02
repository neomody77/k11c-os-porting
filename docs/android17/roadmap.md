# Android17：准备中，尚未构建

Android16能运行不代表Android17已可运行。已选定 `android-17.0.0_r1` 并启动独立源码同步，详见 [准备记录](preparation-20261003.md)。当前没有Android17镜像、实际VINTF结论或板上启动结果，也没有宣称更新kernel/vendor。

1. 完成固定标签源码同步并导出逐项目提交锁定清单；AVC 溢出修正仍需携带，GPU-work 缺 map 修正已被上游包含。
2. 用真实factory vendor/kernel captures做FCM、VNDK、HAL、AVB和动态分区兼容检查，记录每一项要求与差异。
3. 在独立源码/输出目录建立GSI构建，不覆盖Android16可恢复基线；完成编译、文件系统和镜像完整性验证。
4. 准备恢复包并审核具体候选，再做可恢复的单次DSU启动；分别记录first-stage、init、system_server与Launcher结果。
5. 重跑同一功能/资源/流畅度矩阵，并增加新版本行为验证；与Android16对比，未测项保持未验证。

实际驱动、旧vendor HAL与kernel功能仍可能成为障碍。不会仅凭RK3566的指令集或内存容量就宣布完整移植可行。进度字段保留在 status.json 的android17下，每个里程碑都需要可追溯源码版本与验收证据。
