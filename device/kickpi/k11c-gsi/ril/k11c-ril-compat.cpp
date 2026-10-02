// SPDX-License-Identifier: Apache-2.0
#include <android-base/file.h>
#include <android-base/logging.h>
#include <android-base/properties.h>
#include <android-base/unique_fd.h>
#include <openssl/sha.h>
#include <selinux/selinux.h>

#include <sys/mount.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>

#include <array>
#include <cerrno>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>

namespace {
constexpr char kSource[] = "/vendor/lib64/librk-ril.so";
constexpr char kDir[] = "/dev/k11c-ril";
constexpr char kCopy[] = "/dev/k11c-ril/librk-ril.so";
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
}  // namespace

int main(int argc, char** argv) {
    android::base::InitLogging(argv, android::base::LogdLogger());
    const bool verifyOnly = argc == 2 && std::strcmp(argv[1], "--verify-only") == 0;
    if (argc != 1 && !verifyOnly) return 2;
    if (!SupportedBoot()) {
        LOG(INFO) << "K11C RIL compatibility: unsupported boot; skipped";
        return 0;
    }
    android::base::unique_fd input(open(kSource, O_RDONLY | O_CLOEXEC | O_NOFOLLOW));
    struct stat sourceStat{};
    std::string bytes;
    if (input.get() < 0 || fstat(input.get(), &sourceStat) ||
        !S_ISREG(sourceStat.st_mode) || sourceStat.st_size != static_cast<off_t>(kSize) ||
        !android::base::ReadFdToString(input.get(), &bytes)) return Fail("read original library");
    if (Digest(bytes) == kAfter) {
        LOG(INFO) << "K11C RIL compatibility: candidate already active";
        if (!verifyOnly) android::base::SetProperty("sys.k11c.ril_compat", "active");
        return 0;
    }
    if (!Prepare(&bytes)) return Fail("unsupported vendor library or transformation mismatch");
    if (verifyOnly) {
        LOG(INFO) << "K11C RIL compatibility: exact candidate verified; no mount performed";
        return 0;
    }
    const std::string state = android::base::GetProperty("init.svc.vendor.ril-daemon", "");
    if (!state.empty() && state != "stopped") return Fail("RIL must be stopped before mounting");
    char* rawContext = nullptr;
    if (fgetfilecon(input.get(), &rawContext) < 0) return Fail("read vendor SELinux context");
    const std::string context(rawContext);
    freecon(rawContext);
    if (context != "u:object_r:vendor_file:s0") return Fail("unexpected vendor SELinux context");
    if (mkdir(kDir, 0700) && errno != EEXIST) return Fail("create tmpfs directory");
    struct stat dirStat{};
    if (lstat(kDir, &dirStat) || !S_ISDIR(dirStat.st_mode) || dirStat.st_uid != 0 ||
        (dirStat.st_mode & 0022)) return Fail("unsafe tmpfs directory");
    char temporary[] = "/dev/k11c-ril/.ril-XXXXXX";
    android::base::unique_fd output(mkstemp(temporary));
    if (output.get() < 0) return Fail("create candidate file");
    if (!android::base::WriteStringToFd(bytes, output.get()) ||
        fchown(output.get(), sourceStat.st_uid, sourceStat.st_gid) ||
        fchmod(output.get(), 0444) || fsetfilecon(output.get(), context.c_str()) ||
        fsync(output.get()) || rename(temporary, kCopy)) {
        unlink(temporary);
        return Fail("write or label candidate file");
    }
    if (mount(kCopy, kSource, nullptr, MS_BIND, nullptr)) {
        unlink(kCopy);
        return Fail("bind candidate library");
    }
    if (mount(nullptr, kSource, nullptr, MS_BIND | MS_REMOUNT | MS_RDONLY, nullptr)) {
        umount(kSource);
        unlink(kCopy);
        return Fail("make bind read-only");
    }
    if (!android::base::SetProperty("sys.k11c.ril_compat", "active")) {
        umount(kSource);
        unlink(kCopy);
        return Fail("publish activation status");
    }
    LOG(INFO) << "K11C RIL compatibility: verified read-only tmpfs bind active";
    return 0;
}
