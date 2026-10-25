# 三键导航：自然横屏布局修复

2026-10-24 在原生 Android16 / SDK36 上复现。设备为 1024×600、密度 200，Launcher 将其分类为 phone，物理屏幕的自然方向却是横屏，当前显示旋转为 0。

原系统使用手势导航，切换到三键导航后，Launcher 按横屏手机把按钮排为竖列，又在窗口缩放时只保留 60 像素宽；导航窗口实际落在底部，仅 60×60。因而缺失的是被裁剪的屏幕导航按钮，与触摸面板驱动无关。相同逻辑也存在于 Android17。

补丁 `0011-navbar-natural-landscape-rotation.patch` 在 Launcher3 三处统一使用实际显示旋转判断导航方向：

1. `DimensionUtils.kt`：导航容器尺寸。
2. `NavButtonLayoutFactory.kt`：按钮横排、竖排布局。
3. `TaskbarActivityContext.java`：更新窗口宽度或高度的条件。

旋转 0/180 与已有导航窗口逻辑一致使用底部横条，90/270 使用侧边竖条；手势与大屏 Taskbar 分支保持原逻辑。实机本次验证的是自然方向、旋转 0，不宣称其余三个旋转的实机测试已完成。

在固定 `android-16.0.0_r4` checkout 编译同版本 `Launcher3QuickStep`，以保留数据的系统应用更新方式安装；没有刷写 boot、super、vbmeta，也没有格式化 userdata。原始系统 APK 和原桌面数据保留。修复 APK SHA-256 为 `7db8cef4dddc4bed2b10f76c68cb891c7b248d4624668b63476921c7d51bf94b`。

安装后导航窗口恢复为 1024×60，三个按键实际显示在屏幕底部。根据 Taskbar 的真实触摸区域，分别点击返回、主页、最近任务：返回和主页能离开独立启动的设置界面，最近任务显示设置任务卡片；截图已在私有工作区核验。测试保持密度 200、三键模式、全局 SELinux Enforcing。

源码修复与结果仅维护在 `android-16` 工作树；Android17 的对应补丁在其独立分支。镜像内原始 Launcher 仍是旧版，本机效果来自 userdata 中的系统应用更新；未来重建 Android16 镜像时需通过更新后的补丁入口集成。完整固件重刷、所有旋转、CTS/VTS 不在本次验收范围。
