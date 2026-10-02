# Android16 构建复现

## 基线

源码标签 android-16.0.0_r4，目标 aosp_arm64-bp4a-userdebug，输出 ARM64 GSI。Linux x86_64 构建机，本次使用 -j12；CPU绑定到完整物理核心及其SMT线程，给宿主机与虚拟机模拟器预留独立核心。公开仓库不固定某台主机的 CPU 编号、IP 或 SSH 别名。

先按 AOSP 官方要求准备 repo 和编译依赖：[构建环境](https://source.android.com/docs/setup/start/requirements)。工具不会帮忙修改宿主机虚拟化配置。

```bash
mkdir -p /path/to/aosp16
cd /path/to/aosp16
repo init -u https://android.googlesource.com/platform/manifest -b android-16.0.0_r4
repo sync -c -j8
```

repo launcher 的新版本提示与构建失败不是同一个问题；不要因为 /usr/bin/repo 不可写而忽略真正的同步错误。

## 应用本地适配

```bash
cd /path/to/k11c-android
bash tools/apply-android16.sh /path/to/aosp16
python3 tools/prepare-vendor-ril.py \
  --factory-library /path/to/private/factory-librk-ril.so \
  --out /path/to/private/ril-candidate
AOSP_ROOT=/path/to/aosp16 JOBS=12 \
  K11C_RIL_LIBRARY=/path/to/private/ril-candidate/librk-ril.so \
  bash tools/build-android16.sh
```

apply 工具校验目标四个项目的 HEAD 对应指定标签，先检查全部九个补丁，再复制板级模块和应用补丁。检测到已应用的同一补丁会跳过；不一致的 overlay 会报错。只允许精确SHA256匹配的已提交旧版Android.bp/RIL helper/rc升级；其它差异仍拒绝。它不清理他人的源码修改。

| 文件 | AOSP 目标项目 |
|---|---|
| patches/android16/0001-avc-high10-overflow-and-tests.patch | frameworks/av |
| patches/android16/0002-k11c-framework-matrix.patch | build/make |
| patches/android16/0003-k11c-ueventd-import.patch | system/core |
| patches/android16/0004-gpuwork-missing-map-and-test.patch | frameworks/native |
| patches/android16/0005-k11c-ril-integration.patch | build/make：安装原生 RIL 兼容 helper 与 init rc |
| patches/android16/0006-k11c-enforcing-domain.patch | build/make：安装system_ext私有SELinux策略 |
| patches/android16/0007-k11c-no-device-sensors.patch | build/make：安装空传感器HAL与原生RTC服务 |
| patches/android16/0008-k11c-gsi-image-labels.patch | build/make：合并镜像中的platform/system_ext/product标签 |
| patches/android16/0009-k11c-immutable-ril-payload.patch | build/make：安装私有验证过的只读RIL库 |
| device/kickpi/k11c-gsi/ | VINTF、ueventd、framework overlay、受限helper、空HAL、RTC和策略 |

构建过程不刷机。镜像位于 AOSP out/target/product/generic_arm64/system.img，不进入本仓库。每次构建单独记录源码引用、补丁版本、镜像哈希及验证状态；不要把一次成功构建当作适合任意 K11C 固件。

仓库不包含厂商库。构建工具只接收精确SHA256匹配的私有候选，放入AOSP板级目录的private子目录并打包为只读system_ext库；已验证的相同副本可以复用。生成的系统镜像含厂商代码，不能仅因源码仓库公开就默认可以分发镜像。

启动时helper核验已知 Android16 DSU/userdebug、vendor API33、原厂库完整哈希和私有候选逐字节一致，才发布给init的挂载源路径。未知固件不发布路径，init不能建立对应bind。空传感器HAL同样直接来自只读镜像；非可执行的XML和蓝牙配置使用专用tmpfs类型。helper使用独立enforcing域，无mount权限或capabilities，init只有两种vendor目标类型的文件mounton权限。AOSP禁止将运行时生成文件重标记为vendor代码，该neverallow保持不变。构建脚本检查实际镜像中的两个可执行文件及两个库的标签。先前使用su域的历史验收见 [RIL集成](ril-integration-20261002.md)，本轮状态见 [enforcing与传感器](enforcing-sensors-20261002.md)。

GPU-work 回归程序单独构建，不进入系统镜像的安装文件列表：

```bash
cd /path/to/aosp16
source build/envsetup.sh
lunch aosp_arm64-bp4a-userdebug
m -j12 k11c_gpuwork_regression_test
```

测试需要 root、bpf.progs_loaded=1 且 GPU-work map 缺失的设备；map 已存在会明确跳过，不能计为通过。初始化等待约30秒。板上执行方法与本次结果见 [改进验收](improvements-20261002.md)。

## 构建后的验收

镜像进入设备前，离线检查文件系统、AVB签名/hashtree、VINTF对比真实vendor/kernel、解压完整性、容量与恢复路径。本次对应组合这些检查通过，但不公开原厂VINTF captures或分区镜像。

首次 boot 修补使用 tools/prepare-boot.py，在副本上处理 gzip/newc ramdisk，要求原始boot基线重打包字节一致、只改两条 system fstab、kernel/second/DTB与header参数保持一致。工具不写设备：

```bash
python3 tools/prepare-boot.py \
  --factory-boot /path/to/private/factory-boot.img \
  --mkbootimg-dir /path/to/aosp16/system/tools/mkbootimg \
  --out /path/to/private/patched-boot
```

enforcing boot候选在上述已知DSU/AVB修补boot上，只替换cmdline中的SELinux模式：

```bash
python3 tools/prepare-enforcing-boot.py \
  --boot /path/to/private/patched-boot.img \
  --out /path/to/private/enforcing-boot
```

工具要求精确完整输入哈希，并验证其它字节不变；不会写设备。factory13 init自身强制Permissive，不能把cmdline修改当成13也已enforcing。

不能假定另一批次镜像也符合这些约束。fstab已变化、ramdisk压缩格式不同或基线不一致时停止，不继续生成“近似”候选。

本仓库不提供自动刷机脚本。准备与验证候选后，再对具体镜像、目标分区和恢复方式逐项确认。单次DSU会在正常重启后回到原厂系统，持久boot修改不会自动回滚。
