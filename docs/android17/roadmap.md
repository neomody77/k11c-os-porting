# Android17：已通过 DSU 启动

`android-17.0.0_r1`、`aosp_arm64-cp2a-userdebug`、SDK37 已在 K11C 以独立单次 DSU 完成启动。保留原厂 5.10.157 kernel/vendor 和原生 Android16。2026-10-24 捕获完整 pstore，确认首次启动阻塞是 virt APEX 的 EROFS 载荷与未启用 EROFS 的原厂内核不兼容；改用 EXT4 后，诊断版和去除诊断改动的常规版均启动成功。详见 [实机修复记录](dsu-ext4-fix-20261024.md) / [JSON](boot-results-20261024.json)。

1. 固定源码及逐项目清单、完整构建、镜像完整性、初始真实 vendor/kernel 静态 VINTF 检查已完成；旧原生 super 已因后续修复过时，需重新打包后才能用于 native 验证。
2. 新增 virt APEX EXT4 补丁与最终镜像载荷检查，旧 EROFS 镜像拒绝测试、修复镜像接受测试均通过。
3. 实机确认 SDK37、桌面、Mali-G52、62 Hz、Enforcing，以及 RIL/蓝牙/RTC helper 和空传感器声明；保留原有 DSU 槽与独立 4 GiB 测试 userdata。
4. HEVC 断言与同输入 Java legacy 参考对齐后，arm/arm64 codec 各 34/34 通过，四项 AVC 回归均通过；缺 map GPU-work 用例因 map 存在而跳过。本地 Perfetto 在去除不适用 VM relay 后跨重启验收通过。自然横屏三键导航修复已独立适配 Android16/17，并经显示和实际点击验证。见 [最新验收](perfetto-hevc-20261024.md)。
5. 2026-10-25 已完成同一 APK、相同显示设置下与原生 Android16 的性能和流畅度对照，涵盖三轮普通/满载动画、滚动、十轮启动及 CPU、内存、存储、GPU 和媒体路径；见 [性能对比](performance-comparison-20261025.md)。完整外设、长时间稳定、复杂 3D 游戏及 CTS/VTS 尚未完成，不能由本轮测试推定通过。

当前仍使用单次 DSU；普通重启返回原生 Android16。没有把 Android17 写入 boot/super/vbmeta。下一阶段依据本轮运行记录逐项验证，不将 Android16 的外设测试结果当作 Android17 证据。
