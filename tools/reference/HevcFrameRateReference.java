// SPDX-License-Identifier: Apache-2.0
import android.media.MediaCodecInfo;
import android.media.MediaFormat;
import android.util.Range;
import java.lang.reflect.Constructor;
import java.lang.reflect.Method;

/** Run via app_process on the pinned userdebug Android17 build, not as an APK. */
public final class HevcFrameRateReference {
    public static void main(String[] args) throws Exception {
        Class<?> legacy = Class.forName(
                "android.media.MediaCodecInfo$CodecCapabilities$CodecCapsLegacyImpl");
        Constructor<?> constructor = legacy.getDeclaredConstructor(
                MediaCodecInfo.CodecProfileLevel[].class, int[].class, boolean.class,
                MediaFormat.class, MediaFormat.class);
        constructor.setAccessible(true);

        MediaFormat defaults = new MediaFormat();
        defaults.setString(MediaFormat.KEY_MIME, MediaFormat.MIMETYPE_VIDEO_HEVC);
        MediaFormat details = new MediaFormat();
        String[][] strings = {
            {"alignment", "2x2"}, {"bitrate-range", "1-120000000"},
            {"block-count-range", "1-32640"}, {"block-size", "16x16"},
            {"blocks-per-second-range", "1-3916800"}, {"max-concurrent-instances", "16"},
            {"measured-frame-rate-1280x720-range", "547-553"},
            {"measured-frame-rate-1920x1080-range", "569-572"},
            {"measured-frame-rate-352x288-range", "1150-1250"},
            {"measured-frame-rate-3840x2160-range", "159-159"},
            {"measured-frame-rate-640x360-range", "528-529"},
            {"measured-frame-rate-720x480-range", "546-548"},
            {"performance-point-1280x720-range", "240"},
            {"performance-point-3840x2160-range", "120"},
            {"size-range", "64x64-3840x2176"},
        };
        for (String[] entry : strings) details.setString(entry[0], entry[1]);
        details.setInteger("feature-adaptive-playback", 0);
        details.setInteger("feature-can-swap-width-height", 1);
        int[] profileIds = {1, 2, 4096, 8192};
        MediaCodecInfo.CodecProfileLevel[] profiles =
                new MediaCodecInfo.CodecProfileLevel[profileIds.length];
        for (int i = 0; i < profiles.length; i++) {
            profiles[i] = new MediaCodecInfo.CodecProfileLevel();
            profiles[i].profile = profileIds[i];
            profiles[i].level = 8388608;
        }
        Object caps = constructor.newInstance(profiles, new int[0], false, defaults, details);
        Method video = legacy.getDeclaredMethod("getVideoCapabilities");
        video.setAccessible(true);
        MediaCodecInfo.VideoCapabilities vc =
                (MediaCodecInfo.VideoCapabilities) video.invoke(caps);
        Range<Integer> rates = vc.getSupportedFrameRates();
        System.out.println("JAVA_LEGACY_FIXTURE_HEVC_FRAME_RATE_RANGE=" + rates);
        System.out.println("JAVA_LEGACY_FIXTURE_0FPS=" + vc.areSizeAndRateSupported(1280, 720, 0.0));
        System.out.println("JAVA_LEGACY_FIXTURE_1FPS=" + vc.areSizeAndRateSupported(1280, 720, 1.0));
        if (rates.getLower() != 1 || rates.getUpper() != 960
                || vc.areSizeAndRateSupported(1280, 720, 0.0)
                || !vc.areSizeAndRateSupported(1280, 720, 1.0)) {
            throw new AssertionError("Java reference differs from the pinned native HEVC fixture");
        }
    }
}
