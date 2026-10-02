# Android17：计划，尚未构建

Android16能运行不代表Android17已可运行。当前没有Android17镜像、选定源码引用、VINTF结论或板上启动结果，也没有宣称更新kernel/vendor。

1. 选择并记录可复现的AOSP源码引用，检查上游AVC修复是否已包含；不要盲目重复Android16补丁。
2. 用真实factory vendor/kernel captures做FCM、VNDK、HAL、AVB和动态分区兼容检查，记录每一项要求与差异。
3. 在独立源码/输出目录建立GSI构建，不覆盖Android16可恢复基线；完成编译、文件系统和镜像完整性验证。
4. 准备恢复包并审核具体候选，再做可恢复的单次DSU启动；分别记录first-stage、init、system_server与Launcher结果。
5. 重跑同一功能/资源/流畅度矩阵，并增加新版本行为验证；与Android16对比，未测项保持未验证。

实际驱动、旧vendor HAL与kernel功能仍可能成为障碍。不会仅凭RK3566的指令集或内存容量就宣布完整移植可行。进度字段保留在 status.json 的android17下，每个里程碑都需要可追溯源码版本与验收证据。
