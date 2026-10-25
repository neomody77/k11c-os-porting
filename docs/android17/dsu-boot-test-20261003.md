# Android17 DSU 启动测试

截至 2026-10-24，Android17 原始 system 候选和诊断版均未能完成启动。原生 Android16 分区没有刷写；最近一次物理断电重启后，设备已恢复原生 Android16，核验 SDK36、SELinux Enforcing、`sys.boot_completed=1`，USB ADB 正常。

## 首次启动

测试使用新建的单次 DSU 槽，分配候选 system（1,910,353,920 字节）和独立空 userdata（8 GiB）；原生 userdata与原有 `android17`、`dsu` 两个槽均未作为目标。

候选 system SHA-256 为 `a9c446041375331ebb829d5a8e214bb0c3ad1ee10c1ea0c31181e07da7e4a379`。板端 `gsi_tool status` 成功映射该 system 并读取到 AVB 公钥 SHA-1 `2597c218aae470a130f61162feaae70afd97f011`，与离线候选一致。Fiemap backing file 的物理文件哈希不同于候选原始字节；AOSP ImageManager 源码确认该 backing 路径使用 dm-crypt 或 FBE/dm-default-key，因此物理文件哈希不能作为传输损坏证据。

pstore 显示 first-stage 已继续到 apexd：约 8.34 秒启动 `apexd --bootstrap`，约 8.98 秒 init 因该服务退出执行 `reboot,bootloader,bootstrap-apexd-failed`。日志列出了 system APEX 扫描和若干 loop mount，但 kernel printk rate limit 丢掉了 57 行 apexd 输出；实际 APEX 失败项和原因尚未确定。设备进入 Rockchip fastboot/bootloader。执行普通 `fastboot reboot` 后，Android16 原生系统恢复并完成启动；新测试槽自动禁用。

## 诊断版复测

为读取更完整的用户态错误，在 AOSP17 `apexd.rc` 的 `apexd` 和 `apexd-bootstrap` 服务上临时移除 `reboot_on_failure`，构建仅用于 DSU 的诊断 system。候选 SHA-256 为 `0b4fa6959bb9b2fb40e6e62bd4d0aec8163d9e19c71ada7e8445cb8b4ef7d5ad`，大小仍为 1,910,353,920 字节；离线 ext4 检查通过，AVB 公钥与原候选相同。构建后源码已恢复，临时 nsjail AppArmor 例外已卸载并删除。

诊断版写入同一专用 DSU 槽，并重建空 8 GiB userdata 后单次启动。tower 曾枚举到 Android AOSP USB gadget，随后约 17 分钟后 USB 断开；ADB、fastboot 和先前无线 ADB 地址均不可达。2026-10-24 物理断电重启后，设备回到原生 Android16。检查时 `/sys/fs/pstore` 为空，因此第二次诊断启动的崩溃原因无法从本次残留日志确定。没有执行原生 boot、super、vbmeta 或 userdata 分区写入。

为了替换专用槽的诊断 system，先前使用 `gsi_tool wipe` 清理了第一次失败的专用 DSU 槽及其空 userdata。诊断版启动后该槽再次占用 `/data`，可用空间降至约 372 MiB。恢复 Android16 后确认 `/metadata/gsi/dsu/active` 指向本轮专用槽 `k11c17trial-20261003`，且 `gsi_tool status` 显示 DSU 未启用；随后再次执行 `gsi_tool wipe`。清理后 `/data` 可用空间恢复到约 10 GiB，`gsi_tool status` 只列出原有 `android17` 和 `dsu` 两个槽，二者 backing images 均仍在。ADB daemon 已恢复为非 root，板端 Android16 正常启动。

## 下一步

1. Android16 已恢复并通过 USB ADB 确认；保留 `android17`、`dsu` 原有 DSU 槽，专用诊断槽已清理。
2. 第二次诊断启动的 pstore 未留下内容，实际故障点仍未知。下次重试前应先准备可在启动失败后读取的串口/持续日志采集，再定位 APEX 或后续阶段故障。
3. 2026-10-24 后续重试已捕获 virt APEX 的 EROFS 不兼容，并在修复后完成 SDK37 DSU 启动，见 [后续修复与实测](dsu-ext4-fix-20261024.md)。本文件保留早期尝试的历史事实，不代表最新运行状态；仍未刷写 Android17 native 镜像。
