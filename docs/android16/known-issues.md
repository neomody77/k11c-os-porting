# Android16 待完成项

USB、DNS、传感器已有进一步因果证据，见 [后续排查](followup-usb-dns-sensors.md)。DNS诊断的启动竞争已修复；传感器所需设备节点与驱动仍缺失，HAL误把EBADF显示成权限拒绝，尚未做vendor持久修复。

| 问题 | 当前证据 | 后续验收 |
|---|---|---|
| 蓝牙权限未持久化 | factory Seekwave节点root:root 0600；HAL为bluetooth用户；临时改为0660与bluetooth属主后开启并收包 | 把最小规则放到实际导入的init/ueventd配置，重新构建；重启后不用手工chmod仍可开启与扫描 |
| 默认应用渲染率31FPS | 物理62Hz，SurfaceFlinger renderRate31Hz；临时min/peak62Hz后绘制61.99FPS | 定位默认refresh-rate投票/配置，验证正常UI和负载下流畅度，再决定默认策略 |
| AVC能力声明与实际不符 | 1080p60样本isFormatSupported=false，指定c2.rk.avc.decoder后Surface和ByteBuffer都解完 | 检查profile/level/尺寸/帧率声明与实际HAL能力，验证应用自动选择行为 |
| 传感器注册失败 | HAL声明Accel，但/dev/mma8452_daemon、输入设备和对应DT配置不存在；ioctl的EBADF被HAL以-1误传为PERMISSION_DENIED | 确认真实器件；无器件时移除虚假HAL/feature声明，有器件时补齐DT/驱动，修正错误码后验收真实事件 |
| vendor rild崩溃 | RIL_Init SIGSEGV与连续重启；旧VNDK库访问有兼容问题 | 确认是否存在需支持的蜂窝硬件，修复依赖与初始化或在正确产品配置中排除未使用服务 |
| GPU-work统计服务中止 | GpuWork::initialize SIGABRT；实际Mali渲染通过 | 检查kernel/BPF与统计功能要求，消除循环中止，不用禁用图形渲染来绕过 |

device/kickpi/k11c-gsi/ueventd.bluetooth.fragment只是准备好的规则片段，未集成进已验证镜像。VINTF里的optional声明只让兼容检查认识旧HAL，不保证HAL功能成功。

未连接摄像头、以太网、SD、USB-host外设，未进行对应功能/吞吐验收。音频API通过但未验证实体音质。尚未跑CTS/VTS、长时稳定性、功耗或4K播放测试。
