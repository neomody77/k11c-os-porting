# K11C Android 16 功能、资源与流畅度测试

实测结论：这块板在当前 Android 16 DSU 中能以约 62FPS 渲染连续动画，四核接近满载时仍保持约 61.85FPS。默认刷新率策略则把应用渲染率限制为 31FPS。内存余量充足，核心系统稳定；外设兼容仍有未完成项。

测试日期为 2026-10-02。系统为自编译 Android 16 / API 36，保留原厂 kernel 5.10.157 和 vendor，Mali-G52 / GLES 3.2，显示模式 1024×600 / 62Hz。测试结束 uptime 2084.58 秒，system_server PID 始终为 881，启动次数为 1。这个约 35 分钟的观察不能替代长时间稳定性验证。

## 流畅度

| 场景 | 实测应用绘制 FPS | 帧间隔 P95 | 最大帧间隔 |
|---|---:|---:|---:|
| 默认策略，连续动画 15 秒 | 31.03 | 32.78ms | 33.67ms |
| 临时限制最低/最高刷新率为 62Hz，连续动画 15 秒 | 61.99 | 16.69ms | 31.79ms |
| 同样的 62Hz 设置，四核 SHA256 压力并行运行 | 61.85 | 17.10ms | 38.08ms |

连续动画使用硬件加速 Canvas 绘制 100 个移动矩形及文字，记录实际 onDraw 时间。FPS 按首末绘制时间计算，帧间隔按相邻绘制时间计算。它反映应用渲染节奏，不是 3D 游戏跑分，也没有逐帧验证显示器实际呈现时间。

另外实际滚动 Android 设置页面，每轮 24 次上下滑动：默认负载下 549 帧中 1 帧被 gfxinfo 标记为卡顿，比例 0.18%；四核压力下 637 帧中 0 帧被标记为卡顿。窗口平均约 29.96 / 28.20 帧每秒，包含 ADB 手势间隙与采集开销，不将其当作连续动画 FPS。gfxinfo 总帧耗时 P95 分别为 36 / 18ms，GPU 耗时 P95 为 19 / 7ms；这些管线耗时与相邻帧间隔是不同指标。

SurfaceFlinger 明确报告物理模式 62Hz、renderRate 31Hz；设定 min_refresh_rate / peak_refresh_rate 为 62.0 后实际绘制接近 62FPS。这验证了默认 31FPS 与刷新率策略有关，未进一步定位到具体默认投票规则。实验结束后两个设置均恢复为原始 null，当前设备保持默认策略。

## CPU、内存、温度与存储

| 项目 | 实测 |
|---|---|
| 静置 10 秒 CPU 使用率 | 7.93%，四核总容量归一化为 100% |
| 设置页面滚动 CPU 使用率 | 40.14% |
| 设置页面滚动 + 四核压力 | 99.18% |
| 空闲可用内存 MemAvailable | 2,904,048KiB，约 2.77GiB |
| 压力与滚动后可用内存 | 2,870,560KiB，约 2.74GiB |
| Android 内存账本 Used RAM | 1,247,922KiB，约 1.19GiB，包含 PSS 与内核使用量 |
| 内存压力 | 一分钟压力测试末尾 memory PSI avg10 some/full 均为 0 |
| 静置/普通 UI 温度 | SoC 约 54–57℃，GPU 约 50–53℃ |
| 一分钟四核 SHA256 压力峰值 | SoC 76.25℃，GPU 65.63℃；系统核心没有重启 |
| 应用存储验证 | 64MiB 写入、SHA256 校验与 fsync 约 686ms；读回校验一致 |
| SQLite | 1000 行事务写入，行数及主键总和正确 |
| 设置页冷启动 / 热启动 | TotalTime 973ms / 186ms，单次样本 |

CPU 使用率由 /proc/stat 前后差值计算，排除 idle 与 iowait。静置数据仍包含后台服务和采样开销。内存数据来自 Linux 与 Android 的不同账本，不能简单相加；低 MemFree 也不等于内存不足。存储测试位于 DSU userdata，包含哈希计算和缓存影响，不能当作原始 eMMC 顺序读写峰值。温度采用内核 thermal zone 读数。未测实际电功耗，需外部功率仪。

## 视频与音频

H.264 的 Rockchip 硬件解码和 Android 软件解码均完成 320×240 / 30fps 样本的 60 帧，正常收到 EOS。AAC 软件解码完成 94 个输出缓冲区。

| 1080p60 H.264 测试路径 | 180 帧耗时 | 解码吞吐 |
|---|---:|---:|
| c2.rk.avc.decoder 输出 YUV ByteBuffer | 9.220 秒 | 19.52 帧/秒 |
| 同一解码器直接输出 Surface，临时 62Hz 策略 | 1.650 秒 | 109.09 帧/秒 |

样本为 3 秒、1920×1080 / 60fps、AVC Constrained Baseline Level 4.2，平均码率约 27.7Mbps。直接显示路径能解完这个样本，数据拷贝路径明显慢。这里是无实时节奏限制的解码吞吐，不能将 109FPS 当成显示器帧率，也未做音画同步、长视频或 4K 验收。

还有一个实际兼容问题：isFormatSupported 对这个 1080p60 样本返回 false，但直接指定 c2.rk.avc.decoder 后，ByteBuffer 和 Surface 两条路径均成功解完。自动依赖能力声明选择解码器的应用可能因此选择软件路径；需要继续检查 vendor 的能力声明。

AudioTrack 写入并播放 48,000 个 PCM 采样，播放位置正常推进。AudioRecord 一秒获得 48,000 个采样，RMS 约 19.61。两项验证音频 API 和流推进；未由人耳验证实际扬声器/耳机音质，也未验证外接麦克风的有效声音。

## 联网与外设

| 项目 | 结果与边界 |
|---|---|
| Wi-Fi | 已连接 5GHz / 802.11ax / WPA3；framework 网络已 VALIDATED；网关与公网 ICMP 收包正常 |
| 应用 DNS / HTTPS | 后续两次测试解析 example.com 并获得 HTTPS 200；首轮曾有一次 UnknownHostException，后续复测通过，没有据此声称已定位根因 |
| USB ADB | 本轮始终保持 USB 连接，安装、shell 和截图成功 |
| WebView | HTML 加载与 JavaScript 回传 K11C:42 成功 |
| Android Keystore | AES-GCM 加密/解密一致；security_level=1，inside_secure_hardware=true |
| GPU | Mali-G52 / GLES 3.2；300 次 offscreen 清屏并逐帧验证读回像素，成功 |
| 电源事件 | 连续 3 次 Awake → Asleep → Awake，核心服务未重启，唤醒后网络连通 |
| 蓝牙 | 初始失败；临时修正节点权限后 ON，10 秒 BLE 扫描收到 921 个包、29 个不同设备，未记录对端身份、未配对 |
| 传感器 | 枚举到 Accelerometer，但注册返回 PERMISSION_DENIED；系统自身注册同样失败，未验证采样 |
| 摄像头 | Camera API 和 HAL 均为 0 个设备，无拍摄验证 |
| 以太网、SD、USB host 外设 | 本轮没有相应连接/挂载，未做功能或吞吐验证 |

蓝牙根因有运行时验证：Seekwave 的 BTBOOT、BTCMD、BTDATA、BTAUDIO、BTISOC、BTLOG、SKWBT_LOG 节点原为 root:root 0600，HAL 以 bluetooth 用户运行。把它们临时改为 bluetooth:bluetooth 0660 后，HAL 初始化与实际 BLE 收包成功。当前保留这次 /dev 权限修复，重启会丢失；尚未写入新的镜像或永久 init/ueventd 规则。

仍存在 vendor rild 的 RIL_Init SIGSEGV / 重启，以及 gpuservice 的 GpuWork::initialize SIGABRT。后者属于 GPU-work 统计服务，实际 Mali 渲染测试通过。不能据此宣布整个 Android16 移植已完成，或宣称通过 CTS/VTS。

## 结束状态与复算

自动熄屏关闭：screen_off_timeout=2147483647，接电保持亮屏 stay_on_while_plugged_in=15。诊断 APK 已卸载，压力进程已退出，设备回到可见桌面。刷新率测试设置全部恢复原值。当前仍为 Android16 单次 DSU；正常重启会回原厂 Android13。

公开的机器结果见 [test-results.json](test-results.json)。诊断工具源码位于仓库 diagnostics/。公开仓库不包含原始日志、截图、实际设备标识或私有工作空间路径。可用 tools/run-diagnostics.py --serial 参数在自己的设备上运行；输出保留在 git 忽略的本地目录，审核脱敏后再补充公开指标。

本轮未刷入新镜像，原厂 userdata 与固件分区未因性能测试被替换。
