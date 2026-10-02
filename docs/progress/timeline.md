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

## 后续：Android17

尚未选择源码引用、构建或刷入Android17。先完成Android16剩余兼容问题并保持可恢复基线，再按 [roadmap](../android17/roadmap.md)推进。
