# Android16 RIL 启动集成

将已通过运行时验证的 RIL 兼容候选集成到 GSI。镜像只包含自行编译的 helper 与 init rc，不包含厂商二进制；厂商原库保持在 vendor 分区。

## 启动实现与边界

`post-fs-data` 阶段同步执行 helper，早于原厂 RIL 的 class main 启动。helper 同时检查 DSU、API36、release16、vendor API33、板型、userdebug 和原库大小/SHA256。只匹配已验证固件时，复现四处共84字节修改，再核对完整候选 SHA256。副本位于 tmpfs，保持原 vendor_file 标签、0444权限，通过只读 bind 供原 init/radio 服务加载；不写 vendor 分区、不改 Android 版本属性或 linker namespace。

每次 DSU 启动自动重建副本。正常退出 DSU 回原版13时，tmpfs 和 bind 自动消失。重复执行已激活 helper 不增加 bind。其它固件、Android17及非调试构建不在支持范围内。

当前 helper 使用 AOSP userdebug 的 `su` SELinux 域，板上仍为 Permissive。这是调试镜像集成，尚未验证 enforcing 策略；不能直接宣称适合正式发布。厂商源码修复或支持新版 Android 的厂商库仍是长期方案。没有实体 modem，HAL 注册不等于蜂窝数据/通话通过。

## 镜像和离线验证

| 产物 | 字节数 | SHA256 |
|---|---:|---|
| system.img | 1899573248 | 9fb8cbe763aaad4420c82a1f7ac951297fc3941c4a0c2be7f88661a13679d244 |
| gzip 传输副本 | 990768904 | 443cc9f942455b778ac2336c3b229e44b0f7d6bf7384391f31070756fd1720d6 |

helper 编译2分05秒，增量 system 镜像构建32秒。文件系统、AVB签名/hashtree、真实厂商 vendor/kernel VINTF、gzip完整性、镜像内 helper/rc 一致性与 init verifier 均通过。五补丁的精确标签 fixture 首次应用、重复应用、实际源码一致性、末补丁冲突前零修改检查通过。工具单测15/15通过。

## DSU 数据保留方法

此前完整 `gsi_tool install` 会重新建立 userdata，不能用于保留数据升级。本轮检查实际源码后使用 `create-partition --partition-name system`，只重新建立 system backing image。

启动前在板上建立 userdata extents 的只读映射；将其8GiB原始块视图备份到板上宿主 userdata，核对备份和原映射哈希一致。备份及密钥均留在板上。更新后再比较 userdata backing inode/大小/时间、LP extents、密钥文件元数据及全部只读块哈希；通过后删除临时只读映射再启动。设备内 canary 和设置用于启动后的保留检查。

这里备份的是映射设备原始块视图，不能与旧文件层副本混淆。恢复仍依赖保留的板上加密密钥；未执行恢复演练，不宣称这是可移植的完整灾备包。不公开原始块数据、密钥、分区抓取、设备标识或厂商库。

## 板上结果

新镜像从原版13进入16、再次独立启动16，两轮均完成启动并自动激活 helper，没有手动运行兼容程序。IRadio1.0–1.5注册；原 radio 用户和 capabilities 保持不变，VNDK33 netutils/cutils加载正确；副本标签、0444权限和只读 bind 均正确。首轮24次、每5秒采样，第二轮12次、每5秒采样，RIL/GPU/system_server分别保持同一PID。两轮无新 crash buffer 或 tombstone。它们是重启验证，未进行断电冷启动。

system-only 更新前后的全部 userdata 原始块哈希、backing inode/大小/时间、LP extents 和四个密钥文件元数据一致。两次16启动的 canary 哈希一致，自动熄屏关闭、充电保持唤醒、Wi-Fi和蓝牙设置保留。

完整诊断初次16项中网络、GPU300帧、存储64MiB校验/SQLite1000行、硬件Keystore、音频API、WebView、符合声明范围的硬件解码180帧和蓝牙RF收包通过。传感器仍为已知注册失败。启动后普通锁屏 `showing=true/secure=false` 导致绘制和Surface窗口未出现；解除锁屏后这两项均通过，保留初次失败与重测结果。不能把屏幕 Awake 当作窗口已经可见。

可见窗口绘制929帧、61.92FPS，帧间隔p95为17.40ms、最长52.58ms，显示62Hz；仍有长帧，不能用短时FPS宣称长期流畅。符合声明码率的1080p60硬件 ByteBuffer 解码180帧/EOS、1786ms。旧超声明码率的Surface样本也解完180帧/EOS、1607ms，其能力查询false仍符合声明上限。音频API通过不等于实体音质通过。

具体脱敏数据见 [结果JSON](ril-integration-results.json)。正常重启退出DSU后原版13完整启动，原库哈希恢复、boot哈希未变、tmpfs覆盖消失；再进入16也完整启动并自动激活，最终运行API36。测试APK已卸载，板上userdata备份保留；不公开测试数据或固件。
