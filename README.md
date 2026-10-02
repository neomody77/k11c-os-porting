# K11C Android 移植进度

记录 KICKPI K11C（RK3566）运行 Android 16，以及后续探索 Android 17 的构建、兼容性修正和板上验证。项目采用 AOSP ARM64 GSI + 原厂 kernel/vendor 的路线。这里保存补丁、配置、诊断工具和脱敏后的进度，不镜像整套 AOSP，也不分发原厂固件或设备数据。

这是社区实验项目，与 KICKPI、Rockchip 或 Google 无官方关联。启动成功不代表完成原生板级移植或通过 CTS/VTS。

## 当前状态

截至 2026-10-02，公开记录是一次具体固件组合的测试快照。

| 版本 | 构建与启动 | 完成度 |
|---|---|---|
| Android 16 | android-16.0.0_r4；aosp_arm64-bp4a-userdebug；编译成功，K11C DSU 启动成功，API 36 | 网络、GPU、媒体、存储等已有实际测试；仍有外设兼容缺口 |
| Android 17 | 尚未选择具体源码版本；尚未构建或板测 | 调研与验证计划已建立，不复用 Android16 成功结论 |

Android16 修正了 factory first-stage 缺少 vbmeta 节点初始化，以及 AVC High10 Level6.2 码率乘法溢出。保留 UBSan/CFI，32/64 位回归测试各 25 项通过。

连续动画默认 31.03FPS；临时将刷新率上下限设为 62Hz 后为 61.99FPS，CPU 满载时为 61.85FPS。空闲可用内存约 2.77GiB，一分钟四核压力最高 SoC 76.25℃。这些是短时应用绘制测试，不是游戏跑分或长期稳定性认证。

蓝牙权限、默认62Hz刷新率和GPU-work缺map处理已集成新候选并完成离线验收；GPU-work独立板测1/1通过，整镜像效果待验收。传感器注册和vendor rild仍未修复。Android16 当前是单次 DSU，正常重启回原厂 Android13。

## 导航

| 内容 | 文件 |
|---|---|
| 板卡与移植边界 | [docs/board.md](docs/board.md) |
| 工作时间线 | [docs/progress/timeline.md](docs/progress/timeline.md) |
| 完整会话排障复盘 | [docs/troubleshooting.md](docs/troubleshooting.md) |
| 当前机器状态 | [status.json](status.json) |
| Android16 构建复现 | [docs/android16/build.md](docs/android16/build.md) |
| 启动与崩溃根因 | [docs/android16/boot-and-codec.md](docs/android16/boot-and-codec.md) |
| 功能、性能与流畅度测试 | [docs/android16/test-report.md](docs/android16/test-report.md) / [JSON](docs/android16/test-results.json) |
| USB、DNS、传感器后续定位 | [docs/android16/followup-usb-dns-sensors.md](docs/android16/followup-usb-dns-sensors.md) |
| 持久改进与候选验收 | [docs/android16/improvements-20261002.md](docs/android16/improvements-20261002.md) |
| 待修问题 | [docs/android16/known-issues.md](docs/android16/known-issues.md) |
| Android17 计划 | [docs/android17/roadmap.md](docs/android17/roadmap.md) |
| 上游跟踪 | [docs/upstream.md](docs/upstream.md) |
| 脱敏规则 | [docs/privacy.md](docs/privacy.md) |

## 仓库使用

在 Linux 构建机上准备 Android16 AOSP 源码后，按构建文档应用补丁。补丁应用工具支持重复执行；构建和离线 boot 修补工具均不执行刷机。诊断工具只对显式指定的设备运行，原始输出默认进入被 Git 忽略的 artifacts/ 目录。

```bash
python3 tools/check-publication.py
python3 -m unittest discover -s tools/tests
bash tools/apply-android16.sh /path/to/aosp16
AOSP_ROOT=/path/to/aosp16 JOBS=12 bash tools/build-android16.sh
```

贡献新的进度时请同时更新 status.json、对应版本文档和时间线，写明源码版本、固件组合、验证方法和局限。把“已构建”“已启动”“功能通过”“长期稳定”分别记录；不把未验证项目标成通过。

## 许可

本仓库代码与文档采用 Apache-2.0，详见 [LICENSE](LICENSE) 和 [NOTICE](NOTICE)。上游来源文件保留原有许可；此许可不授予原厂固件、vendor blobs 或第三方商标的使用权。
