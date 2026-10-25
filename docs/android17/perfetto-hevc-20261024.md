# Android17：恢复本地 Perfetto 与核对 HEVC 测试

## Perfetto 的实际失败原因

板端 `traced` 每隔约 5 秒退出重启，错误为创建 `vsock` relay socket 时地址族不受内核支持，随后 `sys.init.updatable_crashing=1`。原厂内核配置为 `# CONFIG_VSOCKETS is not set`；相同配置和重启症状也出现在此前 Android16 基线。

地址来自 Virtualization 的 `build/apex/product_packages.mk`，其通用配置写入 `traced.relay_producer_port`。Perfetto 的 `src/traced/service/service.cc` 在该属性非空时启用 relay endpoint；本地 consumer/producer Unix sockets 与这个 VM relay 是不同通道。

在独立 Android17 DSU 中临时清空该地址并重启 `traced`，服务恢复 running，`persist.traced.enable=1` 仍保留，未关闭 tracing，也未放宽 SELinux。使用专用的 `perfetto-configs` 和 `perfetto-traces` 目录采集 3 秒 CPU/内存计数：实际文件 23,065 字节、45 个 TracePacket、31 组 sys_stats，含 124 个 CPU 项与 1,023 个 meminfo 项，采样跨度约 2.918 秒，PID 保持不变。

新增 `0008-perfetto-local-tracing-without-vsock.patch`：本仓库的 K11C `aosp_arm64` 目标不再写入 VM relay 地址，其他构建目标保留原逻辑。本地 tracing 及 probes 服务继续启用；该修复不意味着原厂内核获得 vsock 或跨 VM tracing 能力。补丁已通过实际固定标签 checkout 的正反向检查，常规 system 已重新编译并验收。

## HEVC：修正测试期望，保留生产计算

原 native 用例 `VideoCapsHevcTest.VideoCaps_HEVC_SupportedFrameRates` 期望下限 0，实际为 1。此 fixture 的 block throughput 下限为正，`updateLimits()` 的全局整数帧率下限取向上舍入，因此结果为 1。

为避免仅调整期望使测试变绿，使用与 native 完全相同的 profile、level、尺寸、block 和性能属性，在设备上通过反射直接构造 Java `CodecCapsLegacyImpl`，绕过可选的 native 后端。实际结果为 `[1,960]`，0fps 不支持、1fps 支持，与 native 计算一致。参考源代码保存在 [HevcFrameRateReference.java](../../tools/reference/HevcFrameRateReference.java)。

`0009-hevc-frame-rate-reference-expectations.patch` 只修改测试：将下限期望改为 1，并补充 0fps 拒绝和 1fps 接受两个断言；不修改 HEVC 生产算法，不调整硬件解码器声明或驱动。arm 与 arm64 测试二进制均已重新编译。

参考程序需在固定标签的 userdebug 设备上以 `app_process` 运行，不作为 APK 安装。先设置 `AOSP_ROOT` 和 `DEVICE_SERIAL`，并在仓库外的私有工作目录复现：

```bash
mkdir -p /path/to/private/classes
javac -source 8 -target 8 \
  -cp "$AOSP_ROOT/prebuilts/sdk/current/public/android.jar" \
  -d /path/to/private/classes tools/reference/HevcFrameRateReference.java
"$AOSP_ROOT/out/host/linux-x86/bin/d8" --min-api 36 \
  --lib "$AOSP_ROOT/prebuilts/sdk/current/public/android.jar" \
  --output /path/to/private/hevc-reference.jar \
  /path/to/private/classes/HevcFrameRateReference.class
adb -s "$DEVICE_SERIAL" push /path/to/private/hevc-reference.jar /data/local/tmp/k11c17-hevc-reference.jar
adb -s "$DEVICE_SERIAL" shell su 0 env CLASSPATH=/data/local/tmp/k11c17-hevc-reference.jar \
  app_process /system/bin HevcFrameRateReference
```

## 集成验收

新常规镜像已通过 ext4、AVB 和最终 product 属性检查，继续包含此前 EXT4 与三键导航修复，没有临时诊断策略。system 为 1,936,048,128 字节，SHA-256 为 `28fa0a90c47992d53ad3254be994ff3c5664a64da10a05af30d8ab98e2248a07`。

独立 DSU 槽保留原 userdata、仅更新 system 后，37.28 秒完成 SDK37 启动。未手工修改 relay 或健康属性：本地 tracing 自动启用，traced/probes 均运行，7 次观察跨度 61.51 秒内 PID 不变，`sys.init.updatable_crashing` 未置位。重新采集实际 trace 为 22,629 字节、45 个包、31 组 sys_stats，CPU 项 124、meminfo 项 1,023，采样跨度 2.981 秒。

新二进制 arm 与 arm64 `CodecCapabilitiesTest` 均 34/34 通过，包含各四项 AVC 回归和新的 HEVC 0/1fps 断言；这些是 native 能力计算测试，不是硬件解码全链路认证。GPU-work 缺 map 用例因 map 存在继续跳过。RIL/蓝牙/RTC 三个 helper、空传感器声明、Mali-G52 / 62 Hz 显示、三键实际点击复核通过；保持 Enforcing。20.10 秒应用切换后亮屏短时样本 CPU 忙 2.72%、MemAvailable 3,015,284 KiB、SoC 52.5℃，崩溃缓冲区为空，不作为长期稳定或游戏帧率结论。

测试程序上传后需要恢复两架构二进制的执行权限；UI 检查先解除无密码锁屏，不能把锁屏下被隐藏的导航按钮误判为故障。Perfetto 客户端在受限域运行，配置和输出使用专用目录并保持原有 SELinux 标签，例如：

```bash
adb -s "$DEVICE_SERIAL" push tools/reference/perfetto-sys-stats.pbtxt /data/local/tmp/k11c17-local-trace.pbtxt
adb -s "$DEVICE_SERIAL" shell su 0 cp /data/local/tmp/k11c17-local-trace.pbtxt /data/misc/perfetto-configs/k11c17-local-trace.pbtxt
adb -s "$DEVICE_SERIAL" shell su 0 restorecon /data/misc/perfetto-configs/k11c17-local-trace.pbtxt
adb -s "$DEVICE_SERIAL" shell su 0 perfetto --txt \
  -c /data/misc/perfetto-configs/k11c17-local-trace.pbtxt \
  -o /data/misc/perfetto-traces/k11c17-local-trace.perfetto-trace
```

完整九补丁在真实固定标签 checkout 重复执行通过，25 项工具测试通过，临时构建沙箱例外已移除。结构化结果见 [JSON](perfetto-hevc-results-20261024.json)。原生 Android16 固件未刷写；Android16 的 tracing 问题未在本轮部署修复。完整外设、长期稳定与 CTS/VTS 不由本次结果推定通过，旧 native super 仍需重新打包和校验。
