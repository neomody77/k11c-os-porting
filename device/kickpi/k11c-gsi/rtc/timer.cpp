// SPDX-License-Identifier: Apache-2.0
// Native equivalent of the vendor scheduled-power timer, with no permissive domain.
#include <android-base/file.h>
#include <android-base/logging.h>
#include <android-base/properties.h>
#include <android-base/unique_fd.h>
#include <cerrno>
#include <climits>
#include <cstdlib>
#include <cstring>
#include <ctime>
#include <fcntl.h>
#include <string>
#include <unistd.h>

bool ValidTime(const std::string& value, unsigned long long* number) {
    size_t first = !value.empty() && value.front() == '+' ? 1 : 0;
    if (value.size() <= first || value.size() - first > 19) return false;
    for (size_t i = first; i < value.size(); ++i)
        if (value[i] < '0' || value[i] > '9') return false;
    errno = 0;
    char* end = nullptr;
    *number = std::strtoull(value.c_str() + first, &end, 10);
    return !errno && end && !*end && *number && *number <= LLONG_MAX;
}

int main(int argc, char** argv) {
    android::base::InitLogging(argv, android::base::LogdLogger());
    if (argc == 3 && std::strcmp(argv[1], "--validate-time") == 0) {
        unsigned long long number;
        return ValidTime(argv[2], &number) ? 0 : 2;
    }
    if (argc != 1) return 2;
    if (android::base::GetProperty("sys.k11c.ril_compat", "") != "active") return 0;
    if (!android::base::SetProperty("sys.k11c.rtc_timer", "active")) return 1;
    std::string rejected;
    for (;;) {
        const auto value = android::base::GetProperty("sys.power.scheduled.time", "");
        if (!value.empty()) {
            unsigned long long number;
            if (!ValidTime(value, &number) ||
                (value.front() != '+' && number <= static_cast<unsigned long long>(time(nullptr)))) {
                if (rejected != value) LOG(ERROR) << "RTC schedule is invalid or in the past; no shutdown";
                rejected = value;
            } else {
                android::base::unique_fd alarm(open("/sys/class/rtc/rtc0/wakealarm", O_WRONLY | O_CLOEXEC));
                if (alarm.get() >= 0 && android::base::WriteStringToFd(value, alarm.get())) {
                    if (android::base::SetProperty("sys.k11c.scheduled_shutdown", "1")) {
                        LOG(INFO) << "RTC alarm programmed; shutdown requested through init";
                        return 0;
                    }
                }
                LOG(ERROR) << "RTC alarm or init shutdown request failed; no shutdown";
            }
        }
        sleep(1);
    }
}
