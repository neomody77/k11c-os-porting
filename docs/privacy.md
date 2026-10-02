# 公开仓库的数据边界

允许提交源码补丁、板型/SoC/通用软件版本、相对源码路径、操作方法、聚合性能指标、脱敏失败原因和公开上游链接。

不提交ADB配对码或serial、SSID/BSSID/MAC、真实网络地址、个人邮箱、主机用户名/SSH别名/主目录、认证信息、个人APK/照片、原始日志/抓取、截图、分区镜像、签名私钥。Android的通用/dev、/proc、/sys路径不是个人主目录；示例路径使用/path/to占位。

原始诊断输出只进入本地被忽略的artifacts/等目录，人工查看后从中提取公开字段。公开JSON不保留UID、network ID、DNS地址或完整MediaFormat对象。提交使用GitHub noreply邮箱，避免个人邮箱进入Git作者历史。

tools/check-publication.py检查所有拟发布文件和Git提交身份，拦截主目录、邮箱、MAC、实际IP、认证字符串以及不应公开的二进制/捕获类型。规则是防线而非隐私保证，发布前还要审查新增内容的语义；不要把敏感值本身写到仓库的“禁止列表”中。

CI只运行静态检查，不连接设备、不刷机、不上传诊断captures。新增结果用test-results的显式字段结构，避免把完整logcat自动脱敏后整份上传。
