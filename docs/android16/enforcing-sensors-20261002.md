# Android16 enforcing 与传感器验收

本轮沿用 android-16.0.0_r4、aosp_arm64-bp4a-userdebug、factory Android13 vendor/API33 与 kernel5.10.157。只支持已知固件哈希；不是 Android17 的验收结论。

## 启动与 SELinux

原 boot 的 androidboot.selinux=permissive 改为 enforcing，只改变 Android boot v2 主 cmdline 字段；kernel、ramdisk、DTB 与此前 DSU/AVB 修复保持逐字节一致。准备工具先检查完整输入哈希，未知或重复修改的镜像拒绝输出。原 boot 备份留在板上。

factory13 的 init 在 security_getenforce 返回1时硬编码调用 security_setenforce(0)，因此即使 cmdline=enforcing，factory13 仍为 Permissive。未修改 factory13 init。Android16 使用 AOSP init，可以从启动阶段进入 Enforcing。

RIL helper 改为独立 k11c_ril_compat enforcing 域。init 将已知原库复制到0700 tmpfs目录；helper只读 staged input、按完整哈希计算候选并与镜像内的私有只读库逐字节核验。成功后才发布init使用的挂载源路径。helper没有 mount 权限、vendor文件访问或Linux capabilities。原radio UID、服务配置、VNDK/linker namespace不变。仓库不包含厂商库，构建者需从自己的精确固件准备私有候选。

首次 enforcing 候选暴露了两个标签问题：system_ext 在 GSI 内是 /system/system_ext，而规则最初只覆盖 /system_ext；默认GSI打包又只使用 platform file_contexts。新增合并规则把 platform/system_ext/product 标签用于同一镜像，并检查 ext4 中实际 security.selinux xattr，避免把“策略编译成功”当成“服务可启动”。

第二候选的准备服务运行成功，但init重标记和bind mount失败。临时提高init日志级别后，确认重标记与挂载返回Permission denied，未建立挂载时remount返回Invalid argument。AOSP禁止init将运行时生成文件重标记为vendor_file_type，不能添加该授权。改为镜像内只读库、独立非可执行配置类型，以及init对vendor_file/vendor_configs_file的文件mounton授权；没有删除neverallow，也没有让helper进入su域。临时日志级别改动不进入最终源码。

旧 rtc_boot_timer 是厂商 permissive shell 域。候选在精确固件检查通过后停止它，使用独立 k11c_rtc_timer enforcing 域的原生服务读取同一个定时属性；只允许写明确标记的 RTC wakealarm。参数必须是有效正整数或正相对时间，RTC写入成功后才向init请求关机。未主动进行定时关机/硬件唤醒测试。

GSI构建期的neverallow检查保持启用。与旧厂商策略的离线链接使用AOSP init原本的secilc参数（含-m/-N）；额外启用跨版本neverallow会撞上旧厂商33.0属性集合与新aconfig类型的既有冲突，不能把该链接称为完整vendor neverallow认证。未修改这些上游规则。userdebug su和旧厂商rtc_boot_timer的permissive类型声明仍在策略中；验收必须同时检查实际运行域与全局模式，不能只看策略里类型名。

## 传感器

原HAL声明加速度计，但 mma8452 设备节点、对应输入设备与DT配置不存在。此前错误码把EBADF误报成权限拒绝，不代表修复SELinux就能产生样本。

对于这组精确固件，且节点确实不存在的情况，新空HAL返回零传感器；将匹配的feature XML中加速度计声明改为unavailable-feature。HAL直接来自只读system_ext，XML在tmpfs中生成并只读绑定，vendor分区未修改。若节点出现、固件哈希变化或目录不安全，保留原HAL并拒绝处理。空HAL不生成模拟样本。

诊断把“HAL/PackageManager声明一致”和“真实物理采样”分为两个测试。零传感器可以通过前者，必须在后者保留不可采样的失败；这不是实体传感器验收通过。

## 蓝牙与 enforcing 兼容

Seekwave厂商策略声明了skwbt_device，却没有给HAL相应节点访问权限；另外HAL枚举/dev、读取旧core数据目录和写未标记属性也被拒绝。新增规则只授权Bluetooth HAL读取/dev目录、访问专用设备类型、自己的vendor数据和单个状态属性，不授予core Bluetooth目录访问。

保留厂商skwbt_device类型，通过CIL的既有-m链接机制合并同名声明。未标记的BTISOC、BTLOG、SKWBT_LOG使用既有hci_attach_dev类型。厂商skwbt.conf的精确哈希检查后，仅重定向BtSnoopFileName到/data/vendor/k11c-bluetooth；地址读取属性也提前改到该目录。原3字节地址后缀由init复制到专用目录，旧数据文件保持原样。未修改Seekwave二进制。

## 已排除的蜂窝功能

当前USB清单只有root hub，没有实体modem；不存在ttyUSB、ttyACM、cdc-wdm或wwan设备。匹配kernel已内建USB serial option/WWAN、QMI WDM、CDC MBIM/NCM/ETHER、RNDIS和PPP支持。RIL进程稳定或radio HAL注册不代表SIM读取、运营商注册、蜂窝数据、短信或通话已经通过。

用户确认板子没有SIM卡槽，已将实体modem、SIM、运营商注册、蜂窝数据、短信和通话测试移出本轮范围。RIL兼容修复仍用于消除厂商进程崩溃；不将其计为蜂窝功能通过。

## 板上结果

候选system.img为1900462080字节，SHA256为`0e90ce5c146004b6ba78ba9b10d049b5fd836d284404190eebef0815adb6bedb`。九补丁首次、重复应用、旧五补丁升级和冲突零修改通过；工具测试19项通过。文件系统、AVB、真实vendor/kernel VINTF、实际镜像文件标签和init语法离线验证通过。

system-only更新前后userdata完整只读哈希一致，未导出userdata或密钥。原版13回退完整启动、原库哈希正确；16两次完整启动均为Enforcing，四处只读bind自动生效。RIL、system_server、GPU和原生RTC第一轮24次、第二轮12次每5秒采样，轮内PID均未变化。RIL仍为radio UID1001及原capabilities，IRadio1.5注册成功。相关helper/HAL/RIL AVC未观察到。

| 测试 | 首次启动 | 第二次启动 |
|---|---|---|
| 传感器声明 | PASS：0个，Accel feature=false | 同样PASS |
| 真实加速度采样 | FAIL：无加速度计 | 未重复，不改写为PASS |
| 功能诊断 | 17项中16项PASS | 关键复测5/5PASS |
| 动画绘制 | 61.92FPS；间隔p95 16.74ms | 61.99FPS；间隔p95 16.40ms |
| 蓝牙扫描 | 770包，25个周边设备 | 646包，26个周边设备 |

完整诊断覆盖存储、Keystore、GPU、DNS/HTTPS、软硬解码、音频API、WebView、传感器声明、动画和1080p60 Surface。动画最大间隔35.04/47.34ms，仍有长帧，不是游戏跑分。第二轮验证时内存快照MemTotal为3993136KiB、MemAvailable为2985672KiB，不作为静置或压力测试。测试APK已卸载，自动熄屏禁用设置保留。

运行中策略分析只列出userdebug su与旧厂商rtc_boot_timer为permissive；旧RTC进程已停止，新RTC在独立enforcing域运行且所有Linux capabilities为0。RTC参数检查2个有效输入和5个无效输入符合预期，未写闹钟、未触发关机。断电冷启动、定时关机/硬件唤醒、CTS/VTS和长时稳定性尚未测试。

脱敏结果见 [JSON](enforcing-sensors-results-20261002.json)。完整原始日志、设备标识、闭源库、加密密钥和userdata不进入本仓库。当前设备留在第二次验证过的Android16；单次DSU正常重启仍回到原版13。
