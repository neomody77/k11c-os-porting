# 上游跟踪

截至2026-10-02的查重快照，AOSP已有同类AVC溢出修复：

- Gerrit：[VideoCapabilities: Fix mul-overflow on bitrate calculation，change 4043384](https://android-review.googlesource.com/c/platform/frameworks/av/+/4043384)。查询时状态ABANDONED，维护者备注为内部合入 ag/39570476。
- 关联issue：[505063251](https://issuetracker.google.com/issues/505063251)。未确认对所有用户公开可读。
- 本项目新增四项边界回归测试，单独纯测试补丁可从完整补丁中提取。公开/Android16目标分支是否已有对应fix，需要在贡献前重新检查。

因此优先在既有review补充独立复现与回归证据、询问公开分支/backport状态，避免向AOSP GitHub镜像提交重复PR。尚未向上游发送本项目反馈；本仓库的存在不代表上游已接受这些改动。

只提供源码相对位置、算术复现和脱敏测试摘要，不上传完整logcat、vendor固件、分区dump或网络/设备标识。
