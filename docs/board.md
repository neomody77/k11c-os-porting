# 板卡与实验边界

测试对象是 KICKPI K11C / Rockchip RK3566，4GB 内存、32GB eMMC 的实验板。厂商入口：[K11C 产品页](https://www.kickpi.com/product/k11C/)。以下软件组合来自本项目板上读取，不能代表所有 K11C 批次。

| 项目 | 实验组合 |
|---|---|
| 原厂系统 | Android13 / API33，userdebug |
| 原厂 kernel | 5.10.157 |
| Treble / VNDK / first API | Treble，VNDK33，first API33 |
| 分区 | 非 A/B，动态分区，userdata F2FS |
| GPU | Mali-G52 / OpenGL ES3.2 |
| 当前显示 | 1024×600，物理模式62Hz |
| 安全状态 | 实验固件为 unlocked / orange，SELinux Permissive；未作为生产固件验收 |

本路线替换 DSU system，保留厂商 kernel、vendor 和板级驱动。可运行更高版本 userspace，不代表 kernel/vendor 已升级，也不代表所有旧 HAL 在新版本完全兼容。

第一次修改 boot 前保存了原始分区数据，并验证原版 Android13 能在修改后的 boot 上启动。原厂 super/vendor/vbmeta 与原厂 userdata 未被本轮 Android16 DSU 替换。不同批次应自行检查分区、fstab、AVB、VINTF 和恢复路径，不照抄扇区地址。

原始 captures、设备唯一标识、厂商分区镜像和真实网络环境不在此仓库中。
