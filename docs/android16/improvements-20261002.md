# Android16 持久改进与候选验收（2026-10-02）

本轮停止Mac C→C排查，恢复OTG模式后通过USB-A主机继续。补丁以android-16.0.0_r4为基线，在原厂kernel/vendor上构建GSI；不修改boot、vendor或设备树。原始日志、二进制和DSU数据备份保留在私有工作空间。

## 三项修正

### Seekwave蓝牙节点权限

factory创建的BTBOOT、BTCMD、BTDATA、BTAUDIO、BTISOC、BTLOG、SKWBT_LOG为root:root 0600，bluetooth HAL无法访问。候选通过prebuilt_etc把七条0660 bluetooth:bluetooth规则安装到system_ext。system/etc/ueventd.rc在vendor/odm规则后导入该文件；解析时后导入的匹配规则生效，重启无需手工chmod/chown。

最初把规则装到system/etc受到generic_system的artifact path检查拒绝，最终放到system_ext并正常通过构建；没有放宽该检查。权限仅覆盖这七个Seekwave节点，修正的是DAC。板上沿用现有bring-up的SELinux Permissive，本轮不据此宣称Enforcing兼容。

### 默认刷新率与62Hz物理模式一致

原GSI的config_defaultRefreshRate为60，而唯一物理模式为62Hz；默认应用renderRate为31Hz。临时min/peak设62Hz时已测得约62FPS，但固定上下限不是本轮最终策略。候选添加一个静态product RRO，只把默认值设为62；不固定min/peak，不禁用系统对应用和负载的刷新率选择。

APK的实际编译资源为62，在板上用idmap2按product策略创建映射成功，没有使用ignore-overlayable。一次fabricated shell overlay能使lookup返回62，但DisplayModeDirector仍保留60，且该临时overlay未跨重启保留；因此不用这次试验宣称修复已生效。持久效果以新镜像启动后的lookup、display投票和实际帧率为准。

### GPU-work缺map时返回不可用，避免统计服务abort

旧GpuWork::getBpfMap使用BpfMap(path)构造器。当前kernel缺少GPU-work BPF map，该构造器先进入abortOnMismatch；后面的isValid检查没有机会执行。匹配原二进制的符号栈明确落在这条链上。

补丁改为默认构造再调用init，检查返回的错误后返回false。正常map的类型/大小检查仍由原实现处理；UBSan/CFI保留。缺少统计所需map和tracepoint的内核仍不提供GPU-work指标，不能把“服务不崩溃”写成“统计功能可用”。Mali渲染不依赖这一统计map。

独立native回归在实际板上通过：1项、0跳过、约30.003秒；条件为root、bpf.progs_loaded=1、GPU-work map不存在，断言dump返回不可用。测试程序和候选libgpuwork放在临时目录，通过LD_LIBRARY_PATH加载；没有替换正在运行的系统库。该结果证明修正库处理缺map成功，整镜像服务稳定性另行验收。

## 构建与离线检查

最后一次增量构建成功，耗时2分33秒（不含前面的依赖修正和完整首次构建）。原测试模块编译先缺bpf_headers，随后缺libstatssocket提供的头文件，补齐显式依赖后通过；没有关闭编译检查。

四个补丁在精确标签的干净稀疏checkout上首次应用通过，重复应用全部识别为已应用。额外制造最后一个项目的冲突，确认失败前没有修改前三个项目或复制overlay。该fixture只用于补丁验收，不清理真实AOSP工作目录。

| 检查 | 结果 |
|---|---|
| e2fsck -fn | 通过 |
| AVB hashtree/签名验证 | 通过 |
| 对照实际factory vendor/kernel的checkvintf | 通过 |
| 解压完整性及主机传输哈希 | 通过 |
| 镜像内ueventd import与七条规则 | 存在 |
| 镜像内RRO资源/idmap映射 | 默认值62，映射成功 |
| 独立缺map native板测 | 1/1通过，无跳过 |
| 新候选整镜像启动 | 待验收 |

镜像为raw ext4，共1899532288字节；gzip共990764179字节。system.img SHA256为54b9b621ee801070398ef61a08a5cf17d544e0e9c5b10727ffe47b0df9c207b9；gzip SHA256为eb9f6963b5c15bdf0d4cb8053abce218034eb455704bcbe190b0a08c7ff68aa8。哈希标识本次私有候选，不代表仓库分发镜像。

## RIL已经定位，但没有混入本轮修复

radio日志与实际ARM64厂商库反汇编相互对应：ql_find_libpath遍历APEX后选中com.android.vndk.v31/lib64/libnetutils.so；vendor linker namespace只允许对应VNDK33，dlopen拒绝访问。ql_ndk_init失败返回前未初始化property_get，随后RIL_Init读取ro.build.version.release时调用空指针，造成SIGSEGV循环。

VNDK33的对应库实际存在。没有连接modem节点不解释这次空指针，不把蜂窝硬件缺席写成崩溃根因。修复应正确选择厂商VNDK版本并处理初始化失败；没有放宽全局linker namespace、移除所有旧VNDK APEX或停掉服务来掩盖错误。本轮该项仍未修复。

## 整镜像验证

新候选已经安装但尚未启动，DSU暂时disabled，板子保持原版Android13正常运行。蓝牙开机权限、默认刷新率和GPU服务跨启动稳定性不计为通过。boot分区哈希与安装前相同。

安装前导出8GiB userdata backing file及旧lp_metadata。安装后的inode/时间戳检查发现原厂gsi_tool重建了userdata；help中的旧--wipe说明不能用来推断省略该参数会保留数据。匹配AOSP的PartitionInstaller会删除已有backing image，重新分配并初始化数据卷。这次在重启前识别，没有让新数据卷完成Android启动。

还发现metadata加密影响备份层级：libfiemap的DSU块映射绕过宿主/data的dm-default-key；直接cat backing file取得的字节与块映射视图不同。只把文件层备份复制到新分配的extent，或只验证文件SHA256相等，都不足以证明旧DSU数据可挂载。当前文件层副本和旧extent元数据作为私有取证材料保留，未称为已成功恢复。文件层直接恢复已停止，等待确认旧测试数据是否必须恢复；数据恢复需要按原映射处理宿主加密。原版13的数据未作清理。

后续更新应使用经实测验证的仅system分区更新流程，或在非运行中的映射块设备层正确备份userdata与必要密钥/metadata；不得把本轮失败的文件层复制方法作为可复现恢复指南。新候选仍保持single-boot恢复路径。

机器可读结果见 [improvements-results.json](improvements-results.json)。这轮不是CTS/VTS、长时老化、真实蓝牙音频或蜂窝网络认证。
