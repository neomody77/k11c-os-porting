# 已验证的两个启动根因

## Factory first-stage 缺少 vbmeta 节点

初次DSU已安装，但约4.18秒时 reboot bootloader，随后USB枚举为Rockchip Loader。它是真正的早期重启，不是首次编译耗时。

factory ramdisk的两条 system fstab只有 wait,logical,first_stage_mount；DT也没有提供vbmeta初始化请求。原始init二进制的静态分析验证了这个路径：GetDmVerityDevices没有avb条件，因此未请求vbmeta节点；DSU fstab转换添加avb_keys，SetUpDmVerity继而调用InitAvbHandle，缺失的vbmeta设备让早期挂载路径失败。初始捕获没有保留最终失败syscall的errno，不将该errno作为已证事实。

改动仅为这两条fstab增加 avb=vbmeta，强制first-stage先准备vbmeta节点。factory vbmeta本身有效，flags=2，保留原厂已有验证策略，没有通过关闭新GSI的UBSan或修改vendor来规避问题。

实际修改文件为 ramdisk 内的 fstab.rk30board。两条 system /system 记录分别覆盖 erofs 与 ext4；保留设备名、挂载点、文件系统和挂载选项，只将 fs_mgr flags 从 `wait,logical,first_stage_mount` 改为 `wait,logical,first_stage_mount,avb=vbmeta`。不修改 vendor 等其他条目。工具发现条目数、已有 flags 或基线重打包不符合预期时会停止。

离线验证：原始基线重打包字节一致；14个ramdisk条目只修改fstab；kernel、second、DTB保持一致；header参数保持一致。板上先验证修改后的boot仍能启动原版Android13，再继续Android16 DSU。此后早期Loader重启消失。

参考AOSP机制：[first_stage_mount.cpp](https://android.googlesource.com/platform/system/core/+/refs/tags/android-13.0.0_r1/init/first_stage_mount.cpp)、[block_dev_initializer.cpp](https://android.googlesource.com/platform/system/core/+/refs/tags/android-13.0.0_r1/init/block_dev_initializer.cpp)、[fs_avb.cpp](https://android.googlesource.com/platform/system/core/+/refs/tags/android-13.0.0_r1/fs_mgr/libfs_avb/fs_avb.cpp)。代码参考与原厂二进制分析分开验证。

## AVC High10 Level6.2 的 int32 乘法溢出

Android16到达userspace后，system_server在libmedia_codeclist_capabilities.so中因UBSan的有符号码率乘法溢出中止。源位置为 frameworks/av/media/libmedia/VideoCapabilities.cpp 的applyLevelLimits。

High10 Level6.2计算 800000×3000=2400000000，超过INT32_MAX。两个架构的独立native测试均能复现，因此不是必须依赖Rockchip驱动才能发生的算术错误。

补丁把AVC码率中间值BR改为int64_t，并在写入公共int32码率范围时clamp到INT32_MAX。保留UBSan/CFI。四项新增边界测试覆盖High10 Level6.2限制、Level6.1不变、厂商码率范围保留、Baseline Level4不变。板上32/64位各25项回归通过，系统不再因此重启。

补丁见 patches/android16/0001-avc-high10-overflow-and-tests.patch；上游已有同类修复记录，见 [upstream](../upstream.md)。不要为相同算术修复重复提交未经查重的PR。
