# Android 16 原生安装准备与验收

## 为什么从 DSU 转为原生安装

此前 Android16 在原厂 kernel/vendor 上通过单次 DSU 启动；正常重启回 Android13。这证明了兼容修复能运行，但没有验证永久安装、断电启动和原生 userdata 升级。用户于本轮授权原生刷写，当前方案先保留原厂 userdata。

直接把旧 GSI 写入 system 不够：原厂 boot 的 fstab 会挂载 Android13 的 system_ext/product，遮住 GSI 内嵌内容；旧兼容 helper 和 init rc 又要求 ro.gsid.image_running=1，原生启动时不会启用修复。

## 候选改动

第十个补丁在内嵌 system_ext 的属性中设置 ro.k11c.compat.enabled=1。init 和 helper 使用这个只读镜像属性，同时保留 Android16/API36、vendor API33、板型、userdebug 和厂商内容精确哈希检查；不把未知固件当成已支持设备。去掉 helper 对 gsid_prop 的读取许可。

原生 boot 从已验证的 Enforcing boot 派生：保留两条 system 的 avb=vbmeta 修复、kernel、second、DTB 和 cmdline，仅删除原厂 system_ext/product 的四条 first-stage 挂载。内嵌的 Android16 system_ext/product 因而可见。它们的原厂逻辑分区仍保留在 super 内，用于回退。

新 super 使用原有 3,263,168,512 字节容量、两个 metadata slot 和 rockchip_dynamic_partitions 分组。只替换 system 内容；其余七个逻辑分区拆包读回后的大小、SHA256 与原厂一致。逻辑镜像共 2,683,682,816 字节，分组剩余 575,291,392 字节。

| 镜像 | 字节 | SHA256 |
| --- | ---: | --- |
| 原生 boot | 41,943,040 | a3e9620f0938450d67b9f2a047422efc1f6f129ada0c3253b8af5ef012caf0f5 |
| Android16 system | 1,900,462,080 | 812238d8e1de9788ff92e514b5754641010ea6b739850feda8590af28dfcb50a |
| 原生 super | 3,263,168,512 | 2f294a89b863bd857ae3d0de3cee275e078574dcfcda2e05ea5474491289f7a4 |

准备工具仅处理离线文件，不连接设备：

```sh
python3 tools/prepare-boot.py --boot-mode native \
  --factory-boot /path/to/current-enforcing-boot.img \
  --mkbootimg-dir /path/to/aosp16/system/tools/mkbootimg \
  --out /path/to/new-native-boot

python3 tools/prepare-native-super.py \
  --factory-super /path/to/factory-super.img \
  --system /path/to/validated-system.img \
  --system-sha256 '<full-validated-system-sha256>' \
  --tools-dir /path/to/aosp16/out/host/linux-x86/bin \
  --out /path/to/new-native-super
```

原生 boot 工具拒绝未知输入、缺失/重复的挂载条目和重复修改。super 工具拒绝未知原厂镜像、错误 system 哈希及容量超限；生成后重新拆包核对全部八个分区。25 项工具测试通过。

## 备份、刷写边界与当前状态

原厂 super、当前 boot、vbmeta、recovery、dtbo、uboot、trust 已在私有空间保存，并与板端完整哈希核对。首次尝试通过 RockUSB 读取 userdata 和 metadata 时，工具虽然报告成功，内容却为重复的 0xCC，已判定为无效备份，未用于回退。中断读操作后软件重启未响应，重新上电后进入 fastboot，再由 fastboot reboot 恢复原厂 Android13。实际设备树显示 mode-bootloader 与 mode-loader 同值，mode-fastboot 为另一值；不能把 adb reboot bootloader 等同于标准 fastboot 入口。已更换为 Android 下冻结 /data 与 /metadata 后读取原始块的备份路径。刷写前必须取得一致的完整 userdata 和 metadata 备份；加密数据及密钥相关原始块不公开。备份用于同一板子的回退，不声称可迁移到另一块板子。停止界面服务并冻结文件系统时画面可能暂停；备份期间保持供电和 USB，不能同时运行 CTS/VTS。ADB exec-out 的原始 dd 输出必须将板端 stderr 重定向到 /dev/null，否则 dd 统计文本也会混入镜像。每个镜像必须核对精确字节数及冻结状态下的板端完整哈希，失败时解冻并恢复服务，拒绝用于刷写前的回退保障。userdata/metadata 的镜像及其设备特定哈希均仅保存在私有空间。

授权写入范围为 boot 和 super。userdata/metadata 先保留，不主动格式化；Android16 首次启动可能升级原厂 userdata，因此回退不能只恢复 system，需核对是否要恢复离线 userdata/metadata。uboot/trust/DTBO/vbmeta/GPT 不在候选写入范围。

状态：候选构建、boot 和 super 离线校验已完成；原厂 Android13 已恢复并完成启动。27,012,857,856 字节 userdata 和 16,777,216 字节 metadata 的冻结备份均已与板端完整哈希匹配，已解冻并恢复服务。原生镜像尚未写入：旧 U-Boot 的 getvar all 未完成，后续 flash 停在镜像打开前的查询阶段（进程虚拟内存仅约 9.5 MB，无 boot 文件打开或映射、无 Sending/Writing）。软件 USB 重置后设备描述符出现 -71，需重新上电恢复，然后使用单项查询。该观察不能单独归因为线材或硬件损坏。此记录不构成原生启动成功声明。

## CTS/VTS 前置结果

设备 full API 是36.1，官方 CTS 选用16.1 R4 ARM，未把它当成36.0测试。Sensors 1.0 VTS 同源16.1 R1一轮完整结束：36项通过、0失败、1/1模块完成；它验证 HAL 行为，不证明板子存在物理传感器。首次运行有主机依赖缺失；另一次主机隧道中断的未完成结果保留，不能计为板子兼容性结论。

完整 VTS 编译起初在 构建虚拟机 的 AppArmor/nsjail 条件处受阻。用户批准精确程序路径的临时例外，原生候选完成后恢复构建。最后的打包冲突来自此前局部测试临时建立的 JAR 链接；移除这些链接后完整 VTS ZIP 构建成功。临时 AppArmor 例外已卸载并删除。测试改动的三个全局验证设置已按事先保存快照恢复原值。官方完整 CTS ZIP 已展开，完整 VTS ZIP 已构建；这不等于测试通过。完整 CTS/VTS 尚未通过；原生启动验收后继续，SIM/实体 modem 相关功能按用户要求排除。

官方参考：[K11C 安装说明](https://doc.kickpi.com/products/beginner_guide/kickpi_k11c/)、[CTS 下载](https://source.android.com/docs/compatibility/cts/downloads)、[VTS 设置](https://source.android.com/docs/core/tests/vts/setup11)。
