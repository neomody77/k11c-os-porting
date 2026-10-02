# 工作时间线

## 2026-09-30：原厂系统与 ADB

板子从初次启动画面进入 Android13。完成开发选项与无线 ADB 调试，比较 USB 线、端口和不同主机上的枚举；后续 USB-A 主机直连可进行 USB ADB。调试中也遇到 Linux libusb 权限不足，属于主机设备访问权限问题，不把它当成 Android 固件崩溃。

配对码、网络端点、设备串号、主机名与原始日志不公开。

## 2026-10-02 凌晨（Asia/Singapore）：主机权限与Android16构建

USB-A对照证明数据线与主机端口能传数据，后续K11C也成功枚举；Linux无seat的SSH用户缺少设备访问权限。持久udev规则修复后普通用户ADB shell成功。

在 Linux 虚拟机中建立 AOSP 构建工作空间，使用 CPU 绑定限制编译对主机的干扰。分配24 vCPU、40GiB内存、32GiB swap，构建并行度12；首次完整构建约1小时49分。CPU编号属于具体主机，公开文档只保留拓扑策略。部分原始构建日志使用UTC并显示前一日，本文统一用新加坡日期。

repo launcher不可写的新版本提示经更新到2.65处理，已有同步继续；编译成功后仍需检查 VINTF、镜像完整性和板上启动。构建阶段出现 nsjail sandbox warning，不将其当作运行时启动失败的根因。

## 2026-10-02：DSU 与启动修正

首次 DSU 在约4.18秒回到 bootloader，定位到 factory first-stage 未创建 vbmeta 节点。对 ramdisk 两条 system fstab 记录添加 avb=vbmeta，保留 kernel/DTB/其他载荷，并验证基线重打包字节一致。修改后的 boot 先成功启动原版 Android13，再继续 DSU。

随后 Android16 的 system_server 遇到 AVC High10 Level6.2 码率乘法溢出。原始32/64位实现均复现，修正中间值类型并限制最终 int32 范围，保留 UBSan/CFI。板上32/64位回归各25项通过。

新 Android16 GSI 在约90秒完成启动，API36、Launcher和显示正常。完成联网、GPU、存储、Keystore、媒体、WebView、电源事件和性能测试。蓝牙节点权限调整后开启并收包；其余待修问题见 [known-issues](../android16/known-issues.md)。

本日默认31FPS与临时62Hz策略分别测得31.03/61.99FPS；62Hz并行四核压力为61.85FPS。诊断APK与压力任务已清理，刷新率临时设定已恢复。自动熄屏关闭。公开指标经过脱敏，原始证据另存。

## 2026-10-02：USB、DNS、传感器继续排查

保留原始设备树、内核/应用日志与实际HAL副本。DNS冷启动10轮中6次失败对应resolver的UID网络拦截；延迟与前台对照各6/6通过。改为等待真实网络回调后12/12通过，同一APK的冷启动对照0/4通过，没有修改网络配置。传感器确认所需设备不存在，HAL的EBADF被-1返回值误显示为权限拒绝；仍未提供真实采样或修改vendor。

USB-A主机连接保持configured/high-speed；运行设备树与厂商规格确认Type-C OTG为USB2.0，不将480Mbps称降速。后续C→C重测中同一个OTG控制器两次切换host，随后黑屏与无线失联，接回USB-A仍不恢复。保留日志与pstore，用户重新上电后原版13与USB-A恢复，未取得可确认panic栈。原版13相同C→C也角色震荡且Mac不枚举，但画面/无线仍正常；临时PHY peripheral停止host循环，数据连接仍待查。详见 [后续记录](../android16/followup-usb-dns-sensors.md)。

## 2026-10-02：Android16持久改进候选

按用户要求暂停Mac C→C排查，接回USB-A后恢复PHY otg。把Seekwave蓝牙权限规则、默认62Hz framework RRO和GPU-work缺map时的错误处理集成到GSI。增量构建2分33秒成功，文件系统/AVB/VINTF与实际packaged规则、资源检查通过；独立GPU-work native回归在板上1/1通过，未替换运行中系统库。

四个源码补丁在精确标签fixture首次与重复应用通过；末项目冲突时验证前三个项目和overlay均未修改。实际厂商RIL反汇编与radio日志定位到误选VNDK31、dlopen被VNDK33 namespace拒绝、property_get空指针调用；这项未修复。新候选安装后发现原厂工具重建userdata，且宿主metadata加密使文件层备份不能直接恢复；已在新镜像重启前停止，DSU disabled，原版13正常。旧文件层副本及extent元数据私有保留。用户明确允许干净DSU后清理测试数据，完成新镜像首次与第二次启动；蓝牙权限自动正确并收包、默认62Hz生效、GPU服务稳定，安装库原生回归1/1通过。默认绘制61.88FPS、四核CPU忙99.31%时61.72FPS；诊断和压力任务已清理。新候选的整镜像验收状态见 [改进记录](../android16/improvements-20261002.md)。

## 2026-10-02：RIL兼容与AVC能力复测

AVC逐项能力查询确认原27.7Mbps测试片超过20Mbps声明范围，符合范围的1080p60样本完整查询、自动选择c2.rk.avc.decoder、180帧解码均通过，关闭能力声明错误的疑点。修复诊断读取Integer帧率的异常，并让runner按probe JSON判断结果。

RIL隔离实验确认第二层故障：VNDK33加载成功后，厂商库仍不识别Android16，RIL版本0触发HIDL中止。准备精确哈希限制的厂商库副本候选，使用SONAME解析并只为release160选择原有RIL协议12。原init/radio服务连续120秒同PID、IRadio1.5注册成功；卸载临时bind后原库哈希恢复、原重启循环返回，因果对照成立。未写入固件分区或重新安装DSU。候选仍需持久集成、enforcing与实体modem验证，见 [本轮记录](../android16/ril-codec-20261002.md)。

## 2026-10-02：RIL启动集成与保留数据更新

将RIL精确候选转换移入原生helper，构建到system_ext并由post-fs-data同步运行。原库/vendor保持不变，每次Android16 DSU启动在tmpfs生成只读副本；保留原init/radio权限和VNDK namespace。源码、原指令、输出哈希和运行环境均有约束，镜像不包含闭源厂商库。五补丁应用、离线镜像及init检查通过。

使用system-only分区更新，板上只读块备份与更新前后全部userdata哈希一致，backing身份、extents和密钥元数据不变；密钥与完整数据未导出。两次16启动自动集成通过，canary/设置保留，原版13回退启动及原库/boot哈希核验通过。RIL/GPU/system_server首轮24次、第二轮12次均无重启。解锁后绘制61.92FPS、Surface180帧通过；符合声明码率自动硬解180帧、网络、蓝牙和存储回归通过。保留普通锁屏导致的初次显示测试失败及重测证据。enforcing、断电冷启动、实体modem仍待测，详见 [集成记录](../android16/ril-integration-20261002.md)。

## 后续：Android17

尚未选择源码引用、构建或刷入Android17。先完成Android16剩余兼容问题并保持可恢复基线，再按 [roadmap](../android17/roadmap.md)推进。
