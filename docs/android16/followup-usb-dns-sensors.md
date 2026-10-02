# USB、DNS、传感器继续排查（2026-10-02）

本次保留原始日志、运行设备树和实际加载的ARM64 HAL副本，再做控制变量实验。私有 captures 与 vendor 二进制不进入公开仓库。原有功能/性能报告保留为当时的快照，本页记录后续查明的原因。

## DNS：冷启动时的UID网络策略竞争

同一份诊断APK每轮由instrumentation冷启动，最先读取active network并立即查询example.com。10轮中4次成功、6次失败；所有10轮的HTTPS仍返回200，失败轮使用example.org作为另一域名对照。

对应失败的resolver日志明确为 `GetAddrInfoHandler::run: network access blocked`。同一UID在网络策略中处于缓存进程状态，blocked/effective为APP_BACKGROUND；设备没有开启Data Saver、全局省电或Doze，网络本身已验证。resolver的UDP查询统计也没有对应的超时或传输错误。Private DNS在自动模式下DoT探测失败并回退UDP，与这次UID拦截不能混为一谈。

匹配本次构建的源码在 [DnsProxyListener.cpp](https://android.googlesource.com/platform/packages/modules/DnsResolver/+/refs/tags/android-16.0.0_r4/DnsProxyListener.cpp) 中先调用isUidNetworkingBlocked，再决定是否实际发送查询。这些失败发生在查询发出前，不是已经证明DNS服务器不可靠。

第二份APK只改测试时序，三个条件交替运行，网络配置不变：

| 条件 | 通过/总数 | 查询前active network |
|---|---|---|
| 冷启动立即查询 | 3/6 | 全部null |
| 等待1.5秒再查询 | 6/6 | 全部存在 |
| 启动前台Activity并等待1.5秒 | 6/6 | 全部存在 |

随后修正公开诊断工具：注册默认网络回调，等待INTERNET、VALIDATED以及onBlockedStatusChanged(false)，最长5秒；条件不满足会明确报网络未就绪/UID受限，不重试DNS来掩盖失败。保留network-cold入口用于复现旧时序。

同一新APK交替测试：正常network 12/12通过，网络就绪等待10–17ms；network-cold对照0/4通过。没有修改DNS、关闭系统网络限制或给测试应用加入永久白名单。

结论：已定位并修复诊断工具在instrumentation启动阶段过早查询网络的竞争。没有修改Android网络策略实现，也不据此宣称所有应用后台联网都正常。onAvailable不代表UID已解除限制，固定sleep仅用于对照，实际工具依赖网络回调。

## 传感器：不存在的设备被HAL声明出来，错误码又被误传

实际运行的vendor ARM64 sensors.rk30board.so声明一个Accelerometer。内核输入设备只有电源键、触摸、耳机、CEC和ADC键；IIO为SAR ADC；运行设备树没有相应加速度计节点；/dev/mma8452_daemon不存在。

两次实际注册都得到同一条链路：

```text
Couldn't open /dev/mma8452_daemon (No such file or directory)
fail to perform GSENSOR_IOCTL_APP_SET_RATE, result = -1, error is 'Bad file descriptor'
sensor registration failed / PERMISSION_DENIED
```

对实际加载HAL的离线反汇编确认：MmaSensor构造时固定使用该设备路径和gsensor输入名；update_delay在open失败后继续ioctl，直接返回libc的-1，没有转成-errno。HIDL结果与framework将-1当成PERMISSION_DENIED，错误显示因此具有误导性。失败在batch/setDelay阶段，尚未走到成功激活或采样。

这是当前factory vendor/kernel组合中未提供设备却声明传感器、以及HAL错误码处理的问题，不是给普通应用补一个Android权限就能解决。没有通过chmod、建立假节点或返回伪造采样来“修复”。

持久修复需要匹配真实硬件：没有搭载加速度计的板型应从HAL列表与feature声明中移除；确有器件的变体则需要确认型号、启用对应DT/驱动并提供真实输入与设备节点，再回归采样。当前证据证明固件没有配置可用设备，不足以证明所有K11C批次物理上都不存在该芯片。尚未修改vendor或刷入候选。

## USB：当前Type-C数据口正常为USB2.0，C→C需要实物对照

[厂商硬件表](https://www.kickpi.com/product/k11C/)分别列出USB3.0 Type-A host与USB2.0 Type-C OTG。运行设备树的fcc00000.dwc3仅连接usb2-phy，maximum-speed为high-speed，dr_mode为otg。

当前USB-A主机连接下：UDC=configured，current_speed=high-speed；控制器实际角色device；OTG对应extcon为USB=1、USB-HOST=0、SDP=1、DCP=0。连续诊断安装、运行和卸载均成功。因此480Mbps不是这条Type-C口从USB3退化的证据。

另一个extcon属于独立host PHY，其USB-HOST=1与OTG处于device可以同时成立。读取多个extcon时必须保留所属控制器，不能把不同端口状态合成“同一端口角色冲突”。

C→C历史未枚举的原因仍需重现：保持独立DC供电，通过无线ADB保留板端日志，比较两种插头方向、已知数据线及主机USB树与同一个OTG PHY。当前设备树未显示独立Type-C/CC控制器，但被动CC电阻不需要Linux节点；这不能单独证明CC电阻缺失、线缆故障或硬件不合规。厂商原理图下载未能从公开页面直接取得，暂不据此编造电路结论。

## 清理与可追溯结果

三份诊断APK均在结束后卸载，临时主机APK副本已删除；没有刷机、重启或改变DNS/USB角色。USB仍configured，Android16 boot complete，system_server仍为此前同一进程。聚合结果见 [followup-results.json](followup-results.json)。
