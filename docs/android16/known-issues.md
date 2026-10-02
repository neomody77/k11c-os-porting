# Android16 待完成项

USB、DNS、传感器已有进一步因果证据，见 [后续排查](followup-usb-dns-sensors.md)。DNS诊断的启动竞争已修复；传感器所需设备节点与驱动仍缺失，HAL误把EBADF显示成权限拒绝，尚未做vendor持久修复。

| 问题 | 当前证据 | 后续验收 |
|---|---|---|
| C→C角色震荡；16曾黑屏失联 | 原版13也反复创建/移除同一OTG host、Mac不枚举，但画面/无线仍正常；临时PHY peripheral停止host循环，尚未建立数据连接；16失联场景无有效panic栈 | 定位角色检测与VBUS/CC电气触发，分别验收连接异常和16失联；临时覆盖已恢复；Mac排查按用户要求暂停，后续修复后验证双方向及热插拔 |
| 蓝牙权限未持久化 | factory Seekwave节点root:root 0600；HAL为bluetooth用户；临时改为0660与bluetooth属主后开启并收包 | 规则已集成并完成编译/离线检查；待新镜像重启后不用手工chmod仍可开启与扫描 |
| 默认应用渲染率31FPS | 物理62Hz，SurfaceFlinger renderRate31Hz；临时min/peak62Hz后绘制61.99FPS | 已构建config_defaultRefreshRate=62的静态RRO并验证idmap；待新镜像验证实际投票、UI与负载 |
| AVC能力声明与实际不符 | 1080p60样本isFormatSupported=false，指定c2.rk.avc.decoder后Surface和ByteBuffer都解完 | 检查profile/level/尺寸/帧率声明与实际HAL能力，验证应用自动选择行为 |
| 传感器注册失败 | HAL声明Accel，但/dev/mma8452_daemon、输入设备和对应DT配置不存在；ioctl的EBADF被HAL以-1误传为PERMISSION_DENIED | 确认真实器件；无器件时移除虚假HAL/feature声明，有器件时补齐DT/驱动，修正错误码后验收真实事件 |
| vendor rild崩溃 | RIL扫描误选VNDK31 libnetutils，vendor namespace仅允许33；dlopen失败后property_get未初始化，RIL_Init调用空指针 | 修正厂商RIL的VNDK选择与失败处理；未放宽全局namespace，也未把无modem当作此SIGSEGV的根因 |
| GPU-work统计服务中止 | BpfMap(path)在缺map时先abort，原isValid检查走不到；修正init错误返回后板上回归1/1通过 | 候选已构建；待整镜像开机确认服务不再循环中止；当前kernel无统计map，统计仍不可用 |

蓝牙规则已安装到system_ext/etc/ueventd.k11c.rc并由system/etc/ueventd.rc导入；编译、离线验收与临时测试不替代整镜像重启验收。见 [改进记录](improvements-20261002.md)。VINTF里的optional声明只让兼容检查认识旧HAL，不保证HAL功能成功。

未连接摄像头、以太网、SD、USB-host外设，未进行对应功能/吞吐验收。音频API通过但未验证实体音质。尚未跑CTS/VTS、长时稳定性、功耗或4K播放测试。
