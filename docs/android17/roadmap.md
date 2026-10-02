# Android17：离线原生候选已就绪

Android16能运行不代表Android17已可运行。`android-17.0.0_r1` 已独立同步，lunch/API37与临时例外下的Soong沙箱探测通过，详见 [准备记录](preparation-20261003.md)。AVC回归模块已编译，板级补丁和17专用RIL候选已集成；完整镜像、ext4/AVB/标签、真实vendor/kernel静态VINTF和原生super验收通过；尚无板上启动结果，也没有宣称更新kernel/vendor。

1. 已完成固定标签源码同步并导出逐项目提交锁定清单；AVC回归模块编译已通过、运行待测；完整系统与GPU-work测试模块编译通过，GPU-work 缺 map 修正已被上游包含。
2. 用真实factory vendor/kernel captures做FCM、VNDK、HAL、AVB和动态分区兼容检查，记录每一项要求与差异。
3. 已在独立源码/输出目录完成GSI与原生super候选，不覆盖Android16可恢复基线；完成文件系统、镜像完整性及全部逻辑分区解包哈希验证。
4. Android16恢复super哈希已复核；具体17候选尚未授权写入。按用户后续选定的原生安装或DSU验证方式，先复核当前userdata备份和恢复方案，再记录first-stage、init、system_server与Launcher结果。
5. 重跑同一功能/资源/流畅度矩阵，并增加新版本行为验证；与Android16对比，未测项保持未验证。

实际驱动、旧vendor HAL与kernel功能仍可能成为障碍。不会仅凭RK3566的指令集或内存容量就宣布完整移植可行。进度字段保留在 status.json 的android17下，每个里程碑都需要可追溯源码版本与验收证据。
