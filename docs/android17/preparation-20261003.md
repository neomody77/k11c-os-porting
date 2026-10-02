# Android17 准备记录

截至 2026-10-03，已建立独立 `android-17` 分支、确定官方源码基线、检查构建环境并启动源码同步。尚未编译 Android17，尚未生成可刷镜像，尚未运行 Android17 的 VINTF/CTS/VTS 或板测。Android16 阶段结果保留在 `android-16` 分支。

## 固定基线

| 项目 | 已核对的值 |
|---|---|
| 官方源码标签 | `android-17.0.0_r1` |
| manifest 标签对象 | `7a9e46ba6ed424f922a3457f4964e67e0b966201` |
| manifest 提交 | `5bc9a7ce1cd78dd53613bbfd0ebf506e1e4adb0f` |
| 平台版本 | Android17，API37 |
| 候选 GSI 目标 | `aosp_arm64-cp2a-userdebug`；release 配置源码确认，实际 lunch 尚未验证 |
| 内核/vendor 路线 | 先评估现有原厂 kernel 5.10.157 / vendor API33；并未升级内核 |

官方依据：[版本与源码标签](https://source.android.com/docs/setup/reference/build-numbers)、[固定 manifest](https://android.googlesource.com/platform/manifest/+/android-17.0.0_r1/default.xml)、[cp2a release](https://android.googlesource.com/platform/build/release/+/android-17.0.0_r1/release_configs/cp2a.textproto)、[构建环境要求](https://source.android.com/docs/setup/start/requirements)。不使用浮动 `android-latest-release` 代替可复现版本。

## 构建环境与源码同步

自有 Linux x86_64 构建虚拟机现有 24 vCPU / 约40GiB RAM，保留12个完整物理核心的SMT配对绑定，模拟器线程有独立核心；本轮核对配置未漂移。启动检查约913GiB可用空间，内存可用约37GiB，未发现正在运行的编译或兼容测试任务。内存低于官方推荐配置，Android16曾以 `-j12` 完成编译，Android17是否需要降低并行度仍需实测。

Git、Python3、repo 2.65 launcher、Java21、GCC/G++、make、bison、flex、zip/unzip、rsync 均可用。Android构建使用源码内的固定工具链，系统Java版本不等于最终构建所用版本。

本轮 `unshare -Ur true` 返回权限错误。此前临时 nsjail AppArmor 例外已清理；正式构建前需要验证该源码树的 nsjail 精确路径并处理沙箱权限，不把“源码同步完成”写成“编译环境全部通过”，也不默默禁用沙箱。

```bash
bash tools/prepare-android17.sh /path/to/aosp17
```

工具要求独立目录、至少400GiB可用空间，使用文件锁防止重复任务；验证 manifest 精确提交后进行 `repo sync -c -j8 --fail-fast`，完成时导出 `.repo/k11c/android17-pinned-manifest.xml`。未完成的同步可以在同一已验证目录重跑。工具不应用补丁、不编译、不刷机，源码和逐项目锁定清单不上传此仓库。

首次尝试引用 Android16 对象缓存时，旧 manifest 为浅克隆，缺失基础 Git 对象，导致 `unresolved deltas`。失败目录与日志已在私有环境保留，改用独立 `--depth=1` 克隆后 manifest 初始化成功并进入项目抓取。工具拒绝以浅克隆 manifest 为引用，避免复现该故障。没有修改 Android16 源码或镜像。

## Android16 适配的逐项审查

| 适配 | Android17 源码证据与下一步 |
|---|---|
| AVC High10 Level6.2 码率溢出 | 官方标签仍使用32位 `BR` 累乘；新增版本专用补丁 `patches/android17/0001-avc-high10-overflow-and-tests.patch`。新版测试文件增加了其他用例，旧补丁不能原样应用；重新定位后，两个官方源文件的 `git apply --check` 通过，4个回归用例尚未编译或运行 |
| GPU-work 缺 BPF map 导致 abort | 官方 `GpuWork.cpp` 已改用默认构造与 `init()`，并注明有参构造失败会 abort。本地旧生产修正无需重复携带；旧内核仍缺统计能力，启动稳定性和统计缺失需分别验证 |
| FCM / 旧 vendor | 官方 GSI 仍包含 VNDK31–34、`hwservicemanager`、HIDL内存组件以及旧设备的 `wificond`。这是静态兼容基础，不是本板 VINTF 通过结果；仍需用实际 vendor captures 比对 |
| ARM64 / 页大小 | `generic_arm64` 仍为 `armv8-a`；GSI声明最大支持页大小16384。最大支持值不等于本板kernel已改为16KiB，仍需核对实际ELF布局、kernel页大小和旧vendor库 |
| RIL、蓝牙、传感器兼容 helper | 现有 `SupportedBoot()` 精确限制 Android16/API36，不能直接用于17。需要针对17重新审查版本条件、只读候选库和init绑定；不先放宽到任意版本 |
| SELinux / RTC / 传感器声明 | 重审17的策略兼容、neverallow、执行文件标签、init触发和framework声明。保持Enforcing验收；本板没有已配置传感器，不凭版本升级宣称存在硬件 |
| 62Hz默认值、媒体与绘制 | 检查overlay资源和新版本行为，并重跑同一功能、资源和绘制矩阵；旧DSU或原生16的数据只作比较基线 |
| AVB、first-stage、super容量 | 内核仍沿用原厂时，既有修正可作候选输入；必须按新system实际内容与大小重验，不能复用16的完整哈希作为17通过证据 |

源码依据：[AVC](https://android.googlesource.com/platform/frameworks/av/+/android-17.0.0_r1/media/libmedia/VideoCapabilities.cpp)、[GPU-work](https://android.googlesource.com/platform/frameworks/native/+/android-17.0.0_r1/services/gpuservice/gpuwork/GpuWork.cpp)、[GSI兼容配置](https://android.googlesource.com/platform/build/+/android-17.0.0_r1/target/product/gsi_release.mk)、[ARM64配置](https://android.googlesource.com/platform/build/+/android-17.0.0_r1/target/board/generic_arm64/BoardConfig.mk)。

## 验收顺序与恢复基线

1. 同步完成、导出全部项目提交清单，并验证 `lunch`、API37与独立输出路径。
2. 验证编译沙箱，完成基线构建和AVC回归；逐项移植板级模块，避免原样执行 `apply-android16.sh`。
3. 对候选做VINTF、SELinux标签、文件系统、容量、AVB与恢复包离线检查。
4. 对明确镜像获得刷机授权后进行可恢复的首次启动，再测试正常重启、功能、资源及绘制。
5. 独立记录17的兼容测试和稳定性结果，不能继承16的“通过”。本板无SIM卡槽，实体modem/SIM功能继续不作为验收范围。

现有板子仍保留已原生启动验证的Android16。本轮没有向板子写入任何固件或改变userdata。Android16的完整块级备份和已验证boot/super仍在私有环境保留，不能因准备17而删除。设备端旧DSU和备份占用较大，后续试启动前需复核空间和恢复方案。
