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
AOSP_ROOT=/path/to/aosp16 JOBS=12 bash tools/build-android16.sh
```

apply 工具校验目标两个项目的 HEAD 对应指定标签，先检查所有补丁，再复制 VINTF 模块和应用补丁。检测到已应用的同一补丁会跳过；不一致的 overlay 会报错。它不清理他人的源码修改。

| 文件 | AOSP 目标项目 |
|---|---|
| patches/android16/0001-avc-high10-overflow-and-tests.patch | frameworks/av |
| patches/android16/0002-k11c-framework-matrix.patch | build/make |
| device/kickpi/k11c-gsi/{Android.bp,compatibility_matrix.k11c.xml} | device/kickpi/k11c-gsi |

构建过程不刷机。镜像位于 AOSP out/target/product/generic_arm64/system.img，不进入本仓库。每次构建单独记录源码引用、补丁版本、镜像哈希及验证状态；不要把一次成功构建当作适合任意 K11C 固件。

## 构建后的验收

镜像进入设备前，离线检查文件系统、AVB签名/hashtree、VINTF对比真实vendor/kernel、解压完整性、容量与恢复路径。本次对应组合这些检查通过，但不公开原厂VINTF captures或分区镜像。

首次 boot 修补使用 tools/prepare-boot.py，在副本上处理 gzip/newc ramdisk，要求原始boot基线重打包字节一致、只改两条 system fstab、kernel/second/DTB与header参数保持一致。工具不写设备：

```bash
python3 tools/prepare-boot.py \
  --factory-boot /path/to/private/factory-boot.img \
  --mkbootimg-dir /path/to/aosp16/system/tools/mkbootimg \
  --out /path/to/private/patched-boot
```

不能假定另一批次镜像也符合这些约束。fstab已变化、ramdisk压缩格式不同或基线不一致时停止，不继续生成“近似”候选。

本仓库不提供自动刷机脚本。准备与验证候选后，再对具体镜像、目标分区和恢复方式逐项确认。单次DSU会在正常重启后回到原厂系统，持久boot修改不会自动回滚。
