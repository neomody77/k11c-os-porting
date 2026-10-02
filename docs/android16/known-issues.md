# Android16 待完成项

USB、DNS、传感器已有进一步因果证据，见 [后续排查](followup-usb-dns-sensors.md)。DNS诊断的启动竞争已修复；传感器所需设备节点与驱动仍缺失，HAL误把EBADF显示成权限拒绝，尚未做vendor持久修复。

| 问题 | 当前证据 | 后续验收 |
|---|---|---|
| C→C角色震荡；16曾黑屏失联 | 原版13也反复创建/移除同一OTG host、Mac不枚举，但画面/无线仍正常；临时PHY peripheral停止host循环，尚未建立数据连接；16失联场景无有效panic栈 | 定位角色检测与VBUS/CC电气触发，分别验收连接异常和16失联；临时覆盖已恢复；Mac排查按用户要求暂停，后续修复后验证双方向及热插拔 |
| 传感器注册失败 | HAL声明Accel，但/dev/mma8452_daemon、输入设备和对应DT配置不存在；ioctl的EBADF被HAL以-1误传为PERMISSION_DENIED | 确认真实器件；无器件时移除虚假HAL/feature声明，有器件时补齐DT/驱动，修正错误码后验收真实事件 |
| vendor rild持久修复待完成 | 两层故障：误选VNDK31导致空指针；选对33后版本表不识别16，RIL_VERSION=0导致HIDL中止。精确闭源库副本候选在原init服务/radio用户下稳定120秒，注册IRadio1.5 | 候选未固化；需冷启动、SELinux enforcing及实体modem验证；不支持17，不放宽namespace |
| GPU-work统计能力缺失 | 缺map崩溃已修复，整镜像两次启动与回归稳定；kernel仍无GPU-work map/tracepoint | 如需这些指标，补齐匹配内核的统计支持并验收真实数据 |

蓝牙规则已安装并导入，两次启动权限自动正确、扫描收包通过。默认62Hz RRO跨启动生效，未固定min/peak时绘制61.88FPS，四核负载61.72FPS。GPU-work缺map崩溃修复后整镜像服务稳定；统计仍不可用。见 [改进记录](improvements-20261002.md)。VINTF里的optional声明只让兼容检查认识旧HAL，不保证HAL功能成功。

AVC能力疑点已关闭：旧27.7Mbps样本超过20Mbps声明范围；符合范围的1080p60样本完整查询通过，自动选择硬件decoder并解完180帧。RIL候选和诊断工具改进见 [本轮记录](ril-codec-20261002.md)。

未连接摄像头、以太网、SD、USB-host外设，未进行对应功能/吞吐验收。音频API通过但未验证实体音质。尚未跑CTS/VTS、长时稳定性、功耗或4K播放测试。
