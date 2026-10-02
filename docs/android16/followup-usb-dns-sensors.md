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

USB实验重新上电回到原版13后，再只读核对sensorservice与设备节点：原版同样声明Accelerometer，/dev/mma8452_daemon与/dev/gsensor仍不存在，输入列表也无对应设备。这进一步确认声明与设备缺失存在于factory系统本身；原版这一步没有重复APK注册实验，不把它记录为另一次采样验收。

持久修复需要匹配真实硬件：没有搭载加速度计的板型应从HAL列表与feature声明中移除；确有器件的变体则需要确认型号、启用对应DT/驱动并提供真实输入与设备节点，再回归采样。当前证据证明固件没有配置可用设备，不足以证明所有K11C批次物理上都不存在该芯片。尚未修改vendor或刷入候选。

## USB：Type-C数据口为USB2.0；C→C重测出现角色切换后整板失联

[厂商硬件表](https://www.kickpi.com/product/k11C/)分别列出USB3.0 Type-A host与USB2.0 Type-C OTG。运行设备树的fcc00000.dwc3仅连接usb2-phy，maximum-speed为high-speed，dr_mode为otg。

重测前USB-A主机连接下：UDC=configured，current_speed=high-speed；控制器实际角色device；OTG对应extcon为USB=1、USB-HOST=0、SDP=1、DCP=0。连续诊断安装、运行和卸载均成功。因此480Mbps不是这条Type-C口从USB3退化的证据。

另一个extcon属于独立host PHY，其USB-HOST=1与OTG处于device可以同时成立。读取多个extcon时必须保留所属控制器，不能把不同端口状态合成“同一端口角色冲突”。

随后保持独立DC供电，通过现有无线ADB持续记录dmesg，把板子接到Mac直连C→C。两端证据如下：

| 阶段 | 观察 |
|---|---|
| 离开USB-A | 板端记录fcc00000.dwc3 device disconnect，主机记录USB断开 |
| 接入C→C | 同一个fcc00000 OTG控制器两次创建并移除xHCI host；同时ADB gadget绑定UDC报Device or resource busy |
| 最后可收到的日志 | uptime约5791.241秒，read descriptors / read strings；此后无线日志停止 |
| 主机和实体画面 | Mac未枚举板子；用户确认黑屏；无线地址失去响应 |
| 接回USB-A而不重启 | 仍未枚举且无法执行无线shell；adb devices保留的device条目已失效，不能证明系统存活 |
| 供电确认 | 用户确认DC一直插着，POWER绿灯一直亮；绿灯不能证明CPU/Android正常运行 |

该结果把可见异常定位到同一OTG控制器的角色切换阶段，但没有捕获可确认的panic、Oops或重启栈，不能把相关性写成已证明的内核崩溃原因。也未证明CC电路、ID检测、VBUS电气异常或线缆中的哪一项触发了切换。

保存现场后由用户断开USB、断DC约10秒，再接DC与USB-A。原版Android13/API33正常启动，boot complete=1，UDC重新configured/high-speed，控制器device，PHY模式otg。Android16使用single-boot DSU，重新上电回到13符合此前的启动配置，没有重新刷写分区。

恢复后只读导出console-ramoops-0与pmsg-ramoops-0（分别524276、327668字节），板端与本地SHA256一致。内容已有明显损坏，console尾部仍可辨认同一段USB事件，但没有可确认的panic记录。缺少dmesg-ramoops记录、损坏的console和旧bootreason均不能证明未发生panic，也不能单独证明硬件内存损坏。原始文件留在私有证据目录，不公开。

### 原版13对照与临时PHY隔离

原版13接入相同Mac C→C后，用户确认画面仍正常，无线shell持续响应，但Mac依然不枚举。同一OTG extcon显示USB=0、USB-HOST=1、USB_VBUS_EN=1，UDC暂时消失；控制器在host/device之间变化。持续内核输出中，uptime约151.897–235.277秒出现628条同一xHCI的Host Controller启动消息（每次创建两条bus消息，对应314次创建），反复创建/移除host，并报gadget绑定UDC忙。

因此C→C角色震荡不是Android16 GSI独有；原版13这轮未重现整板黑屏失联，不能把16那次失联也直接归为同一个已确定根因。

随后仅通过运行时sysfs，将fe8a0000.usb2-phy/otg_mode从otg写为peripheral。[Rockchip USB2 PHY参考源码](https://github.com/rockchip-linux/kernel/blob/develop-5.10/drivers/phy/rockchip/phy-rockchip-inno-usb2.c)中的该路径通过GRF强制ID指示device并关闭VBUS供电；公开分支未确认与factory二进制逐行一致，实际效果以板端状态为准。写入后host创建循环停止，USB-HOST与USB_VBUS_EN均为0，UDC重新出现，但USB=0、UDC=not attached、speed=UNKNOWN，Mac仍未枚举。

此时DWC3 runtime_status=suspended，debugfs mode读取UNKNOWN 00000000，不能把休眠时读到的零寄存器当成一个有效新角色。仅固定PHY角色还没有修好C→C数据连接。保持Mac端不动，板端按原方向拔出约3秒再插入，仍USB=0、UDC=not attached，Mac无USB ADB；用户确认画面正常。还需反向插头与USB-A相同临时模式对照，确认主机是否供VBUS以及板端检测是否变化。未手动写DWC3 debugfs角色，未改DT/镜像。此临时PHY覆盖仍在原版13运行中，需在结束实验时恢复otg；重启也会恢复。

运行设备树未显示独立Type-C/CC控制器，但被动CC电阻不需要Linux节点，不能据此认定CC电阻缺失或硬件不合规。厂商原理图下载未能从公开页面直接取得，暂不编造电路结论。

## 清理与可追溯结果

三份诊断APK均在结束后卸载，临时主机APK副本已删除；DNS实验结束时Android16与USB仍正常。后续C→C引发失联，由用户重新上电后恢复原版13与USB-A ADB。原版C→C对照进行了可恢复的PHY peripheral覆盖，没有刷机或改变DNS。聚合结果见 [followup-results.json](followup-results.json)。
