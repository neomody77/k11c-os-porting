// SPDX-License-Identifier: Apache-2.0
#include <android-base/file.h>
#include <android-base/logging.h>
#include <android-base/properties.h>
#include <android-base/unique_fd.h>
#include <openssl/sha.h>

#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>

#include <array>
#include <cerrno>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <sstream>
#include <string>
#include <vector>

namespace {
constexpr char kSource[] = "/vendor/lib64/librk-ril.so";
constexpr char kInput[] = "/dev/k11c-ril/original.so";
constexpr char kDir[] = "/dev/k11c-ril";
constexpr char kCopy[] = "/system_ext/lib64/k11c/librk-ril.so";
constexpr char kBefore[] = "242fe86dfbdb5796674077ac55ffa4f6facc067c4b3e1bf519f0da5d2925ab5b";
constexpr char kAfter[] = "f61f59dba68563eb9a037b6ac1c42bd3788724fdf9b94a52badc737624aeda8d";
constexpr size_t kSize = 769528;

std::string Digest(const std::string& bytes) {
    std::array<unsigned char, SHA256_DIGEST_LENGTH> digest{};
    SHA256(reinterpret_cast<const unsigned char*>(bytes.data()), bytes.size(), digest.data());
    constexpr char hex[] = "0123456789abcdef";
    std::string result;
    for (unsigned char value : digest) {
        result += hex[value >> 4];
        result += hex[value & 15];
    }
    return result;
}

bool Replace(std::string* bytes, size_t offset, const std::string& before,
             const std::string& after) {
    if (before.size() != after.size() || offset + before.size() > bytes->size() ||
        bytes->compare(offset, before.size(), before) != 0) return false;
    bytes->replace(offset, before.size(), after);
    return true;
}

std::string Words(std::initializer_list<uint32_t> words) {
    std::string bytes;
    for (uint32_t word : words) {
        for (int shift = 0; shift < 32; shift += 8) bytes += static_cast<char>(word >> shift);
    }
    return bytes;
}

bool Prepare(std::string* bytes) {
    if (bytes->size() != kSize || Digest(*bytes) != kBefore) return false;
    const std::string netBefore("/system/lib64/libnetutils.so\0", 29);
    const std::string utilsBefore("/system/lib64/libcutils.so\0", 27);
    std::string netAfter("libnetutils.so\0", 15);
    std::string utilsAfter("libcutils.so\0", 13);
    netAfter.resize(netBefore.size(), '\0');
    utilsAfter.resize(utilsBefore.size(), '\0');
    // The final digest also checks every unchanged byte against the known candidate.
    return Replace(bytes, 662470, netBefore, netAfter) &&
           Replace(bytes, 662878, utilsBefore, utilsAfter) &&
           Replace(bytes, 422672, Words({0xa9bd57f6, 0xa9014ff4}),
                   Words({0x52800000, 0xd65f03c0})) &&
           Replace(bytes, 177504, Words({0xf0000342, 0x90000363, 0x913aa442, 0x9133e463, 0x52800020}),
                   Words({0x7102809f, 0x540000c1, 0x52800185, 0xb9000325, 0x17fffecf})) &&
           Digest(*bytes) == kAfter;
}

bool SupportedBoot() {
    using android::base::GetProperty;
    return GetProperty("ro.gsid.image_running", "") == "1" &&
           GetProperty("ro.build.version.sdk", "") == "36" &&
           GetProperty("ro.build.version.release", "") == "16" &&
           GetProperty("ro.vendor.api_level", "") == "33" &&
           GetProperty("ro.product.board", "") == "rk30sdk" &&
           GetProperty("ro.debuggable", "") == "1";
}

int Fail(const char* reason) {
    LOG(ERROR) << "K11C RIL compatibility: " << reason;
    return 1;
}
bool ReadOnlyBind(const std::string& root, const std::string& target, const std::string& filesystem = "tmpfs") {
    std::string mounts;
    if (!android::base::ReadFileToString("/proc/self/mountinfo", &mounts)) return false;
    size_t matches = 0;
    std::istringstream lines(mounts);
    std::string line;
    while (std::getline(lines, line)) {
        std::istringstream fields(line);
        std::string id, parent, device, sourceRoot, point, options, token, fs;
        if (!(fields >> id >> parent >> device >> sourceRoot >> point >> options)) continue;
        if (sourceRoot != root || point != target ||
            (options != "ro" && options.compare(0, 3, "ro,") != 0)) continue;
        while (fields >> token && token != "-") {}
        if (token == "-" && fields >> fs && fs == filesystem) ++matches;
    }
    return matches == 1;
}

bool WriteStaged(const std::string& path, const std::string& bytes) {
    std::string name = path + ".XXXXXX";
    std::vector<char> temporary(name.begin(), name.end());
    temporary.push_back('\0');
    android::base::unique_fd output(mkstemp(temporary.data()));
    if (output.get() < 0) return false;
    if (!android::base::WriteStringToFd(bytes, output.get()) ||
        fchmod(output.get(), 0444) || fsync(output.get()) || rename(temporary.data(), path.c_str())) {
        unlink(temporary.data());
        return false;
    }
    return true;
}

int Bluetooth(bool mounted) {
    constexpr char source[] = "/vendor/etc/bluetooth/skwbt.conf";
    constexpr char stage[] = "/dev/k11c-bluetooth";
    const std::string config = std::string(stage) + "/skwbt.conf";
    if (mounted) {
        if (android::base::GetProperty("sys.k11c.bluetooth_prepared", "") != "1" ||
            !ReadOnlyBind("/k11c-bluetooth/skwbt.conf", source))
            return Fail("Bluetooth init configuration bind not verified");
        return android::base::SetProperty("sys.k11c.bluetooth_compat", "active") ? 0 : 1;
    }
    struct stat directory{};
    if (lstat(stage, &directory) || !S_ISDIR(directory.st_mode) || directory.st_uid != 0 ||
        (directory.st_mode & 0077)) return Fail("unsafe Bluetooth stage directory");
    std::string bytes;
    if (!android::base::ReadFileToString(std::string(stage) + "/original.conf", &bytes) ||
        Digest(bytes) != "1f4ddff789ec0246d90d642ddb7272448e027c2cb19ebe6bfa34c3b656085241")
        return Fail("unsupported Seekwave configuration; original retained");
    const std::string before = "BtSnoopFileName=/data/misc/bluedroid/btsnoop_hci.cfa";
    const auto offset = bytes.find(before);
    if (offset == std::string::npos || bytes.find(before, offset + before.size()) != std::string::npos)
        return Fail("unexpected Seekwave data path");
    bytes.replace(offset, before.size(), "BtSnoopFileName=/data/vendor/k11c-bluetooth/btsnoop_hci.cfa");
    if (Digest(bytes) != "b6814e5dc945d84873154aaba219b5d7946db4ef3a639201257ad026c130dca0" ||
        !android::base::SetProperty("sys.k11c.bluetooth_prepared", "0") ||
        !WriteStaged(config, bytes) ||
        !android::base::SetProperty("sys.k11c.bluetooth_prepared", "1"))
        return Fail("prepare vendor-only Bluetooth data path");
    return 0;
}

int Sensors(bool mounted) {
    constexpr char source[] = "/vendor/lib64/hw/sensors.rk30board.so";
    constexpr char features[] = "/vendor/etc/permissions/tablet_core_hardware.xml";
    constexpr char stage[] = "/dev/k11c-sensors";
    const std::string xml = std::string(stage) + "/features.xml";
    if (mounted) {
        if (android::base::GetProperty("sys.k11c.sensors_prepared", "") != "1" ||
            !ReadOnlyBind("/system/system_ext/lib64/sensors.k11c-empty.so", source, "ext4") ||
            !ReadOnlyBind("/k11c-sensors/features.xml", features))
            return Fail("no-device sensors init binds not verified");
        if (!android::base::SetProperty("sys.k11c.sensors_compat", "no-configured-device"))
            return Fail("publish sensor declaration status");
        LOG(INFO) << "K11C sensors: no configured device; empty list and absent feature active";
        return 0;
    }
    struct stat node{}, directory{};
    if (lstat("/dev/mma8452_daemon", &node) == 0 || errno != ENOENT)
        return Fail("sensor node present or not safely inspectable; original retained");
    if (lstat(stage, &directory) || !S_ISDIR(directory.st_mode) || directory.st_uid != 0 ||
        (directory.st_mode & 0077)) return Fail("unsafe sensor stage directory");
    std::string original, permissions, empty;
    if (!android::base::ReadFileToString(std::string(stage) + "/original.so", &original) ||
        Digest(original) != "952e59fd625c0825fe6fd24f4020f27b68229d6e98bef89bea3476b4a4c7731f" ||
        !android::base::ReadFileToString(std::string(stage) + "/original.xml", &permissions) ||
        Digest(permissions) != "9ac57b570e4880907985e2d2cb4ce2d47d7f08985eaed2318dd61919c838b4cf")
        return Fail("unsupported sensor HAL or feature XML; original retained");
    const std::string declared = "<feature name=\"android.hardware.sensor.accelerometer\" />";
    const auto offset = permissions.find(declared);
    if (offset == std::string::npos || permissions.find(declared, offset + declared.size()) != std::string::npos)
        return Fail("unexpected accelerometer feature declaration");
    permissions.replace(offset, declared.size(),
                        "<unavailable-feature name=\"android.hardware.sensor.accelerometer\" />");
    if (!android::base::ReadFileToString("/system_ext/lib64/sensors.k11c-empty.so", &empty) ||
        empty.size() < 64 || empty.compare(0, 4, "\177ELF") != 0 ||
        !android::base::SetProperty("sys.k11c.sensors_prepared", "0"))
        return Fail("read compiled empty sensors module");
    if (!WriteStaged(xml, permissions) ||
        !android::base::SetProperty("sys.k11c.sensors_source", "/system_ext/lib64/sensors.k11c-empty.so") ||
        !android::base::SetProperty("sys.k11c.sensors_prepared", "1")) {
        unlink(xml.c_str());
        return Fail("prepare no-device sensor module and declarations");
    }
    LOG(INFO) << "K11C sensors: exact absent-device firmware prepared; no samples synthesized";
    return 0;
}
}  // namespace

int main(int argc, char** argv) {
    android::base::InitLogging(argv, android::base::LogdLogger());
    const bool verifyOnly = argc == 2 && std::strcmp(argv[1], "--verify-only") == 0;
    const bool mounted = argc == 2 && std::strcmp(argv[1], "--check-mounted") == 0;
    const bool sensorsPrepare = argc == 2 && std::strcmp(argv[1], "--sensors-prepare") == 0;
    const bool sensorsCheck = argc == 2 && std::strcmp(argv[1], "--sensors-check") == 0;
    const bool bluetoothPrepare = argc == 2 && std::strcmp(argv[1], "--bluetooth-prepare") == 0;
    const bool bluetoothCheck = argc == 2 && std::strcmp(argv[1], "--bluetooth-check") == 0;
    if (argc != 1 && !bluetoothPrepare && !bluetoothCheck && !verifyOnly && !mounted && !sensorsPrepare && !sensorsCheck) return 2;
    if (!SupportedBoot()) {
        LOG(INFO) << "K11C RIL compatibility: unsupported boot; skipped";
        return 0;
    }
    if (bluetoothPrepare || bluetoothCheck) return Bluetooth(bluetoothCheck);
    if (sensorsPrepare || sensorsCheck) return Sensors(sensorsCheck);
    if (mounted) {
        if (android::base::GetProperty("sys.k11c.ril_prepared", "") != "1" ||
            !ReadOnlyBind("/system/system_ext/lib64/k11c/librk-ril.so", kSource, "ext4"))
            return Fail("init read-only bind not verified");
        if (!android::base::SetProperty("sys.k11c.ril_compat", "active"))
            return Fail("publish activation status");
        LOG(INFO) << "K11C RIL compatibility: init read-only bind verified in enforcing domain";
        return 0;
    }
    // Init copies the immutable vendor input into private tmpfs. This domain
    // never opens vendor libraries, relabels files, or mounts filesystems.
    android::base::unique_fd input(open(kInput, O_RDONLY | O_CLOEXEC | O_NOFOLLOW));
    struct stat sourceStat{};
    std::string bytes;
    if (input.get() < 0 || fstat(input.get(), &sourceStat) ||
        !S_ISREG(sourceStat.st_mode) || sourceStat.st_uid != 0 ||
        sourceStat.st_size != static_cast<off_t>(kSize) ||
        !android::base::ReadFdToString(input.get(), &bytes)) return Fail("read init-staged original");
    if (!Prepare(&bytes)) return Fail("unsupported vendor library or transformation mismatch");
    if (verifyOnly) {
        LOG(INFO) << "K11C RIL compatibility: exact candidate verified; no output written";
        return 0;
    }
    if (!android::base::SetProperty("sys.k11c.ril_prepared", "0"))
        return Fail("reset preparation status");
    struct stat dirStat{};
    if (lstat(kDir, &dirStat) || !S_ISDIR(dirStat.st_mode) || dirStat.st_uid != 0 ||
        (dirStat.st_mode & 0077)) return Fail("unsafe init tmpfs directory");
    // Runtime-generated executable files cannot be relabeled as immutable vendor
    // code under AOSP neverallow rules. Verify the privately prepared image copy.
    std::string immutable;
    if (!android::base::ReadFileToString(kCopy, &immutable) || immutable != bytes)
        return Fail("immutable image payload differs from exact candidate");
    if (!android::base::SetProperty("sys.k11c.ril_source", kCopy) ||
        !android::base::SetProperty("sys.k11c.ril_prepared", "1"))
        return Fail("publish verified image payload");
    LOG(INFO) << "K11C RIL compatibility: exact candidate prepared for init";
    return 0;
}
