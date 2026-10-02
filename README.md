# K11C OS 移植进度

记录 KICKPI K11C（RK3566）运行 Android 16，以及后续探索 Android 17 的构建、兼容性修正和板上验证。项目采用 AOSP ARM64 GSI + 原厂 kernel/vendor 的路线。这里保存补丁、配置、诊断工具和脱敏后的进度，不镜像整套 AOSP，也不分发原厂固件或设备数据。

这是社区实验项目，与 KICKPI、Rockchip 或 Google 无官方关联。启动成功不代表完成原生板级移植或通过 CTS/VTS。

当前分支为 `android-17`：官方 Android17 固定标签源码已同步，API37与独立GSI目标已验证，Soong沙箱在精确路径临时例外下通过探测，例外已清理。尚未编译系统镜像或在板上启动。下方 Android16 记录是保留的已验证基线，不能当作 Android17 通过证据。见 [Android17 准备记录](docs/android17/preparation-20261003.md)。

## 分支约定

公开仓库：[neomody77/k11c-os-porting](https://github.com/neomody77/k11c-os-porting)。每个系统版本使用独立分支，命名为 `系统-版本`。

| 分支 | 用途 |
|---|---|
| `main` | 项目总览、通用记录及首次公开时的 Android16 基线 |
| `android-16` | Android16 补丁、构建工具、板上验证与阶段总结；本阶段已结束 |
| `android-17` | Android17 独立开发、补丁审查和验证记录；当前处于准备阶段 |

复现 Android16 时先执行 `git switch android-16`。后续版本的实现与测试结果在对应版本分支维护，不把 Android16 的验证结果当作其他版本的通过证据。

## 当前状态

截至 2026-10-03，记录是一次具体固件组合的测试快照。Android16本阶段已按用户要求结束，见 [总结与原生资源实测](docs/android16/summary-20261003.md)。

| 版本 | 构建与启动 | 完成度 |
|---|---|---|
| Android 16 | android-16.0.0_r4；aosp_arm64-bp4a-userdebug；编译成功，eMMC原生首启与正常重启成功，API36.1 | 网络、GPU、媒体、存储等已有实际测试；仍有外设兼容缺口 |
| Android 17 | android-17.0.0_r1；源码同步完成；aosp_arm64-cp2a-userdebug/API37已验证 | 环境准备完成，AVC补丁在实际checkout检查通过；尚未编译或板测 |

Android16 修正了 factory first-stage 缺少 vbmeta 节点初始化，以及 AVC High10 Level6.2 码率乘法溢出。保留 UBSan/CFI，32/64 位回归测试各 25 项通过。

初版默认绘制31.03FPS；新的默认62Hz配置在两次启动中生效，未固定min/peak时绘制61.88FPS，CPU忙99.31%时61.72FPS。仍有较长帧间隔；这是15秒应用绘制测试。旧完整资源/温度测试与本轮指标分别记录，不作为游戏跑分或长期稳定性认证。

新镜像两次启动验证了蓝牙节点权限与扫描、默认62Hz和GPU-work缺map时不崩溃；安装库原生回归1/1通过。kernel GPU-work统计能力仍未补齐。上述指标来自DSU阶段。当前boot/super已完成原生刷写和板端完整哈希校验，正常重启继续Android16，SELinux Enforcing；原厂userdata保留，完整块级备份已验证。原生亮屏待机63秒CPU平均4.68%、MemAvailable约2.89GiB、SoC约52.5–53.1℃。见 [原生安装记录](docs/android16/native-install-20261002.md)。

后续关闭了AVC能力疑点：原样本超过声明码率，符合范围的1080p60样本自动选择硬件decoder通过。最新候选两次启动均为SELinux Enforcing；受限helper核验私有只读RIL库并由init绑定，保留原radio身份和namespace。旧permissive RTC服务已停止，原生替代服务在独立enforcing域运行。userdebug su仍为permissive，不是生产安全认证。

传感器HAL返回0且系统不再声明加速度计，声明一致性两次通过；真实采样测试保留“无加速度计”的失败。完整17项中16项通过，第二次关键复测5/5通过；绘制61.92/61.99FPS，蓝牙实际收包。原版13回退及system-only更新前后userdata哈希一致均已验证。用户确认本板无SIM卡槽，蜂窝测试移出范围。详见 [enforcing与传感器记录](docs/android16/enforcing-sensors-20261002.md)。

## 导航

| 内容 | 文件 |
|---|---|
| 板卡与移植边界 | [docs/board.md](docs/board.md) |
| 工作时间线 | [docs/progress/timeline.md](docs/progress/timeline.md) |
| 完整会话排障复盘 | [docs/troubleshooting.md](docs/troubleshooting.md) |
| 当前机器状态 | [status.json](status.json) |
| Android16 阶段总结与原生资源 | [总结](docs/android16/summary-20261003.md) / [JSON](docs/android16/native-results-20261003.json) |
| Android16 原生安装与恢复边界 | [记录](docs/android16/native-install-20261002.md) |
| Android16 构建复现 | [docs/android16/build.md](docs/android16/build.md) |
| 启动与崩溃根因 | [docs/android16/boot-and-codec.md](docs/android16/boot-and-codec.md) |
| 功能、性能与流畅度测试 | [docs/android16/test-report.md](docs/android16/test-report.md) / [JSON](docs/android16/test-results.json) |
| USB、DNS、传感器后续定位 | [docs/android16/followup-usb-dns-sensors.md](docs/android16/followup-usb-dns-sensors.md) |
| 持久改进与候选验收 | [docs/android16/improvements-20261002.md](docs/android16/improvements-20261002.md) |
| RIL兼容候选与AVC能力复测 | [docs/android16/ril-codec-20261002.md](docs/android16/ril-codec-20261002.md) |
| RIL启动集成与userdata保留验收 | [docs/android16/ril-integration-20261002.md](docs/android16/ril-integration-20261002.md) |
| Enforcing、传感器声明与回归验收 | [记录](docs/android16/enforcing-sensors-20261002.md) / [JSON](docs/android16/enforcing-sensors-results-20261002.json) |
| 待修问题 | [docs/android16/known-issues.md](docs/android16/known-issues.md) |
| Android17 计划 | [docs/android17/roadmap.md](docs/android17/roadmap.md) |
| Android17 环境与补丁准备 | [docs/android17/preparation-20261003.md](docs/android17/preparation-20261003.md) |
| 上游跟踪 | [docs/upstream.md](docs/upstream.md) |
| 脱敏规则 | [docs/privacy.md](docs/privacy.md) |

## 仓库使用

在 Linux 构建机上准备 Android16 AOSP 源码后，按构建文档应用补丁。补丁应用工具支持重复执行；构建和离线 boot 修补工具均不执行刷机。诊断工具只对显式指定的设备运行，原始输出默认进入被 Git 忽略的 artifacts/ 目录。

```bash
python3 tools/check-publication.py
python3 -m unittest discover -s tools/tests
bash tools/apply-android16.sh /path/to/aosp16
AOSP_ROOT=/path/to/aosp16 JOBS=12 \
  K11C_RIL_LIBRARY=/path/to/private/ril-candidate/librk-ril.so \
  bash tools/build-android16.sh
```

贡献新的进度时请同时更新 status.json、对应版本文档和时间线，写明源码版本、固件组合、验证方法和局限。把“已构建”“已启动”“功能通过”“长期稳定”分别记录；不把未验证项目标成通过。

## 许可

本仓库代码与文档采用 Apache-2.0，详见 [LICENSE](LICENSE) 和 [NOTICE](NOTICE)。上游来源文件保留原有许可；此许可不授予原厂固件、vendor blobs 或第三方商标的使用权。
