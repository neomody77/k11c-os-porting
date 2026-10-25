# Android 17 与 Android 16 性能、资源和流畅度对比

测试于 2026-10-24 晚至 2026-10-25 凌晨完成，时区 Asia/Singapore。这是当前两套 K11C 移植镜像在同一块板上的对照，不是 Android 版本的通用排名。

同一APK的普通与四核压力动画都保持约62FPS；固定62Hz动画的CPU忙碌比例为16的53.46%、17的33.06%，空闲可用内存则接近（2.83/2.84GiB）。设置进程冷启动中位数为1022.0/957.5ms。Surface解码路径接近；Buffer出队路径17明显更快，但本测试没有逐像素读取，不能推广成播放器或图像处理速度。设置页也不能直接按gfxinfo超期比例排名：17记录的帧期限更紧，中位软件呈现延迟较低。

## 固件与控制条件

同一块 RK3566 / 4GB 板、同一屏幕、供电和 USB 主机；原厂 kernel 5.10.157 与 vendor。Android16 为 android-16.0.0_r4 / SDK36，原生 eMMC 安装，含已验收的导航 Launcher 更新；Android17 为 android-17.0.0_r1 / SDK37 的修复版单次 DSU，含 EXT4 APEX、导航和 tracing 修复。两者全局 SELinux 均为 Enforcing；测试采样通过 userdebug su 执行。

Android16 原生基线保留已知 traced / VM relay 重启问题，实测状态为 restarting 且 relay 已配置；Android17 已集成不依赖 VSOCK 的 tracing 修复。本轮不临时修正16的服务，比较的是当前两套镜像的实际表现。流畅度采集使用 APK 和 gfxinfo，不依赖 Perfetto。

显示统一为 1024×600 / density 200 / 三键导航 / 物理 62Hz；亮度设置 102，三项窗口动画倍率 1。HDMI 屏幕实际背光和电功耗没有外部测量。先测 min/peak 均为 null 的默认刷新策略，再临时固定 min/peak=62。全部结束后恢复各系统原设置并卸载测试 APK。

测试使用同一 APK，SHA256：`eeb52e3b1d1923e05ff0a8162961e1febd1fd2a30a95d565e4931d91d7a29599`。GPU/设置预热后采集 60 秒空闲资源；每种连续动画测三轮，每轮预热 1 秒、统计 30 秒；设置页每轮 24 次上下滑动，共三轮，压力场景再重复。冷启动与已有任务恢复分别 10 轮；CPU、存储、GPU、媒体各三轮。常规与压力测试顺序一致，资源每约 3 秒采样。

冷却目标为 SoC ≤56.5°C，最多等待 240 秒，实际压力起始温度记录在 JSON。固定先17后16，未随机化且板上存在前轮余热；温度条件并非恒温，不能由温度差推断系统功耗。四个 sha256sum 进程读取 /dev/zero 形成持续四核负载；85°C 停止压力。未修改 CPU/GPU governor、频率或内核热保护阈值。内核 passive 阈值为 75/85°C，critical 为 115°C。

## 实测结果

注意：两版本 gfxinfo 的 frame deadline 分布不同，表中的卡顿率来自各自预算，不能直接作为跨版本流畅度排名。

除明确标为合计或比例的项目外，数值为各轮中位数；完整范围、样本数和分子分母见 [机器结果](performance-comparison-20261025.json)。CPU 以四核总容量为 100%。

| 项目 | Android 16 原生 | Android 17 DSU |
|---|---:|---:|
| 默认策略连续动画 | 62.05 FPS | 62.05 FPS |
| 固定 62Hz 连续动画 | 62.04 FPS | 62.05 FPS |
| 四核压力连续动画 | 62.04 FPS | 62.05 FPS |
| 普通动画帧间隔 P99 | 17.43 ms | 17.21 ms |
| 压力动画帧间隔 P99 | 18.97 ms | 16.76 ms |
| 动画间隔 >50ms（普通 / 压力，合计） | 0 / 0 | 0 / 0 |
| 设置页滚动卡顿率 | 0.77% | 16.42% |
| 压力下设置页滚动卡顿率 | 2.45% | 11.43% |
| 设置页滚动总帧耗时 P95 | 38 ms | 38 ms |
| 压力下设置页滚动总帧耗时 P95 | 40 ms | 38 ms |
| 设置进程冷启动 TotalTime 中位数 | 1022.0 ms | 957.5 ms |
| 设置已有任务恢复 TotalTime 中位数 | 179.0 ms | 161.0 ms |
| 空闲 CPU 忙碌比例 | 5.75% | 4.75% |
| 固定 62Hz 动画 CPU 忙碌比例 | 53.46% | 33.06% |
| 设置页滚动 CPU 忙碌比例 | 60.21% | 43.80% |
| 空闲 MemAvailable | 2.830 GiB | 2.840 GiB |
| 全程最小 MemAvailable | 2.020 GiB | 2.623 GiB |
| Java SHA256 单线程吞吐 | 670.2 MiB/s | 680.1 MiB/s |
| Java SHA256 四线程总吞吐 | 2044.1 MiB/s | 2294.0 MiB/s |
| 64MiB 写入 + SHA256 + fsync | 1094 ms | 872 ms |
| 64MiB 缓存读取 + SHA256 | 191 ms | 186 ms |
| SQLite 1000 行事务验证 | 27 ms | 28 ms |
| 1080p60 AVC Surface 解码 180 帧 | 1562 ms | 1528 ms |
| 1080p60 有界码率 AVC Buffer 解码 180 帧 | 10519 ms | 1789 ms |
| 320x240 AVC 软件解码 60 帧 | 294 ms | 295 ms |
| AAC 解码 94 个缓冲区 | 270 ms | 309 ms |
| 持续压力 CPU 忙碌比例 | 98.15% | 98.18% |
| 全程 SoC 峰值 | 83.89°C | 83.33°C |
| 全程 GPU 温度峰值 | 73.33°C | 72.78°C |

本轮另记录单次软件重启：从ADB reboot到boot_completed，Android16约49.83秒，恢复Android17约38.82秒，包含ADB轮询和重连时间。两者启动模式不同、均非首次开机，仅作为本轮观测，不作通用启动速度排名。

## 如何理解流畅度

连续动画使用同一硬件加速 Canvas，绘制 100 个移动矩形及文字，统计 onDraw 的实际时间。它可以对照相同应用工作负载下的绘制节奏；P99 比平均 FPS 更能暴露长帧。这里没有把平均 FPS 当作游戏性能，也没有把 onDraw 时间当作面板实际呈现时间。

设置页来自各系统自带 Settings，界面实现和负载可能随版本不同。卡顿率按 gfxinfo 的 Janky frames / Total frames rendered 汇总三轮，不使用带 legacy 的另一计数。P95 是各轮 framework 总帧耗时分位数的中位数，包含流水线延迟，与相邻绘制间隔不同。尾部帧的 FrameDeadline - IntendedVsync 已额外统计；16通常给出更宽期限，17通常更紧，同时17的中位软件呈现延迟较低。较高的17超期比例不能直接解释为等比例更差的体感；这与排队和时序预算差异一致，但具体调度机制尚未单独定位；不能由这些样本归因到单一系统组件。DisplayPresentTime 是软件记录，不是外部测量的触摸到像素延迟。ADB 手势间隙影响总帧数，因此不从滚动总时长推算“实际 FPS”。压力场景的卡顿率未必单调变差；CPU/GPU 频率响应和渲染帧数变化也会影响分母。

额外核对了每轮 framestats 保留的最后 120 帧：这些是尾部样本，不覆盖全部滚动帧。DisplayPresentTime 有有效记录；原始 GPU 直方图存在 4950ms 饱和桶、部分 GpuCompleted 早于 SwapBuffers，因此不把 GPU 直方图尾值当作真实 GPU 停顿。原始字段留在私有目录，公开 JSON 仅保留质量计数与尾部时间戳汇总。

普通滚动的尾部样本，每轮保留最后120帧，以下取三轮对应分位数的中位数；不表示全部滚动过程或物理触摸延迟。

| 尾部软件时间戳指标 | Android 16 | Android 17 |
|---|---:|---:|
| 记录中的 deadline 预算 P50 | 48.41 ms | 32.29 ms |
| 流水线完成耗时 P50 | 36.28 ms | 19.06 ms |
| 软件呈现延迟 P50 | 63.49 ms | 47.33 ms |
| 软件呈现延迟 P95 | 65.10 ms | 63.64 ms |

## 资源、温度与稳定性边界

MemAvailable 是 Linux 对可用内存的估算，不能与 Android Used RAM 或 PSS 简单相加；SwapTotal/Free 包括系统 zram。内存压力 PSI、最小可用内存、压力起止温度与采样频率范围见 JSON。

CPU SHA256 吞吐包含 Java、密码提供者和 ARM 指令实现，不是通用 CPU 跑分。四线程测试沿用相同流程、没有逐轮恢复恒定芯片温度，之前的 UI 负载和热降频也会影响结果；不要将多线程差值全部归因于平台算力。GPU 探针每轮 EGL 离屏清屏并校验 300 次像素，共 900 次，验证两套系统渲染正确；它不是复杂 3D GPU 吞吐测试。

Android17 的 userdata 是 4GiB DSU，Android16 使用保留的原生 userdata，容量、已用空间、缓存与历史应用状态不同。存储测试包含哈希、缓存、fsync 和 DSU 映射开销，读测试是写入后的缓存读取；不能据此判断原始 eMMC 峰值或将差异全部归因于 Android 版本。设置冷启动指 force-stop 后进程 COLD，未清除全机页缓存；“热”测试实测 LaunchState 为 HOT，即恢复已有任务。

Buffer路径只统计解码输出缓冲区的出队、字节数、释放和EOS，没有额外调用getOutputBuffer逐像素读取或校验画面；同一硬件decoder、180帧和559872000输出字节在两系统一致。该路径的显著耗时差异可能包含framework缓冲区处理方式变化，尚未定位具体机制；不能直接推广到CPU图像算法或播放器速度。

Surface 视频路径使用三秒 1080p60 AVC 样本，无实时播放节奏限制，因此报告的是解码吞吐而非实际屏幕帧率。旧 Surface 样本约 27.7Mbps，超过 vendor 声明 20Mbps，上限外显式指定 decoder 能完成解码不扩大厂商能力声明；有界码率 Buffer 样本另测并保留通过结果。未测长视频音画同步、4K、3D 游戏、外部电功耗或长时间老化。

两套系统的 system_server、SurfaceFlinger、zygote64 PID 在各自测试前后保持不变，未触发温度停止阈值。Android16 的已知 traced 服务重启单独保留，不把“核心进程稳定”写成“全部服务无崩溃”。这个十余分钟级别的观察只证明本次负载期间核心进程稳定，不能代替 CTS/VTS 或长时间稳定性验收。

## 复现与结束状态

在 Linux AOSP 工作空间构建 diagnostics/，分别在两个已启动的 userdebug 系统执行同一命令：

```bash
AOSP_ROOT=/path/to/aosp16 bash diagnostics/build.sh
python3 tools/run-performance.py --serial "$SERIAL" --sdk 37 \
  --apk diagnostics/build/diagnostics.apk --out artifacts/performance-17
# Android16 已启动后，用同一 APK，将 --sdk 改为 36、输出目录另取名。
# Linux 使用 root ADB server 时添加 --sudo-adb。
```

驱动不会切系统或刷机；本轮的系统切换单独执行。原始日志、截图、设备标识、网络端点与用户路径不进入公开结果。

结束后已经恢复Android17的既有单次DSU，SDK37、boot_completed=1、SELinux Enforcing。两套系统的临时刷新率、亮度与动画设置都已恢复，诊断APK已卸载，压力进程已结束，桌面已唤醒。原生Android16固件分区未刷写，既有DSU镜像与userdata沿用；回到17后vendor指纹与16基线一致。本轮没有向公开仓库上传原始日志或设备数据。
