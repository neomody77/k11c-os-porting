# Android16 待完成项

USB、DNS、传感器已有进一步因果证据，见 [后续排查](followup-usb-dns-sensors.md)。DNS诊断的启动竞争已修复；最新GSI已清除无已配置设备时的虚假传感器声明，真实采样仍不可用，未改vendor分区。

| 问题 | 当前证据 | 后续验收 |
|---|---|---|
| C→C角色震荡；16曾黑屏失联 | 原版13也反复创建/移除同一OTG host、Mac不枚举，但画面/无线仍正常；临时PHY peripheral停止host循环，尚未建立数据连接；16失联场景无有效panic栈 | 定位角色检测与VBUS/CC电气触发，分别验收连接异常和16失联；临时覆盖已恢复；Mac排查按用户要求暂停，后续修复后验证双方向及热插拔 |
| 真实传感器采样不可用 | /dev/mma8452_daemon、输入设备和对应DT配置不存在；最新空HAL返回0、feature声明为false，两次启动一致性通过 | 如需真实事件，先确认器件与接线，再补齐匹配DT/驱动；当前不把空HAL当成物理采样通过 |
| RIL长期与断电验证待完成 | 私有只读候选经受限helper核验，在两次Enforcing启动中由原init/radio运行；每轮24/12个样本同PID，vendor分区不变 | 当前只支持已知Android16 userdebug固件，不支持17；断电冷启动和长时验证未做。实体modem/SIM/蜂窝按用户要求排除 |
| GPU-work统计能力缺失 | 缺map崩溃已修复，整镜像两次启动与回归稳定；kernel仍无GPU-work map/tracepoint | 如需这些指标，补齐匹配内核的统计支持并验收真实数据 |

蓝牙规则已安装并导入，两次启动权限自动正确、扫描收包通过。默认62Hz RRO跨启动生效，未固定min/peak时绘制61.88FPS，四核负载61.72FPS。GPU-work缺map崩溃修复后整镜像服务稳定；统计仍不可用。见 [改进记录](improvements-20261002.md)。VINTF里的optional声明只让兼容检查认识旧HAL，不保证HAL功能成功。

AVC能力疑点已关闭：旧27.7Mbps样本超过20Mbps声明范围；符合范围的1080p60样本完整查询通过，自动选择硬件decoder并解完180帧。RIL候选和诊断工具改进见 [本轮记录](ril-codec-20261002.md)。

未连接摄像头、以太网、SD、USB-host外设，未进行对应功能/吞吐验收。音频API通过但未验证实体音质。尚未跑CTS/VTS、长时稳定性、功耗或4K播放测试。

最新enforcing回归17项中16项通过，唯一失败为无加速度计；第二次关键复测5/5通过。旧permissive RTC服务停止，原生替代服务运行，无capabilities；未实测定时关机和硬件唤醒。userdebug su及未运行的厂商RTC类型仍在策略中声明为permissive。详见 [验收记录](enforcing-sensors-20261002.md)。
