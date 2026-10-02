// SPDX-License-Identifier: Apache-2.0
// A legacy HAL for a board with no configured sensor device. Never emits samples.
#include <hardware/sensors.h>
#include <errno.h>
#include <pthread.h>
#include <stdbool.h>
#include <stdlib.h>
#include <string.h>

struct empty_device {
    sensors_poll_device_1_t api;
    pthread_mutex_t lock;
    pthread_cond_t changed;
    bool closed;
    unsigned pollers;
};

static int get_list(struct sensors_module_t* module, const struct sensor_t** list) {
    (void)module;
    if (!list) return -EINVAL;
    *list = NULL;
    return 0;
}

static int activate(struct sensors_poll_device_t* dev, int handle, int enabled) {
    (void)dev; (void)handle; (void)enabled;
    return -EINVAL;
}

static int delay(struct sensors_poll_device_t* dev, int handle, int64_t ns) {
    (void)dev; (void)handle; (void)ns;
    return -EINVAL;
}

static int batch(struct sensors_poll_device_1* dev, int handle, int flags,
                 int64_t period, int64_t timeout) {
    (void)dev; (void)handle; (void)flags; (void)period; (void)timeout;
    return -EINVAL;
}

static int flush(struct sensors_poll_device_1* dev, int handle) {
    (void)dev; (void)handle;
    return -EINVAL;
}

static int poll_empty(struct sensors_poll_device_t* api, sensors_event_t* data, int count) {
    if (!data || count <= 0) return -EINVAL;
    struct empty_device* dev = (struct empty_device*)api;
    pthread_mutex_lock(&dev->lock);
    ++dev->pollers;
    while (!dev->closed) pthread_cond_wait(&dev->changed, &dev->lock);
    --dev->pollers;
    pthread_cond_broadcast(&dev->changed);
    pthread_mutex_unlock(&dev->lock);
    return -ENODEV;
}

static int close_empty(struct hw_device_t* api) {
    struct empty_device* dev = (struct empty_device*)api;
    pthread_mutex_lock(&dev->lock);
    dev->closed = true;
    pthread_cond_broadcast(&dev->changed);
    while (dev->pollers) pthread_cond_wait(&dev->changed, &dev->lock);
    pthread_mutex_unlock(&dev->lock);
    pthread_cond_destroy(&dev->changed);
    pthread_mutex_destroy(&dev->lock);
    free(dev);
    return 0;
}

static int open_empty(const struct hw_module_t* module, const char* id,
                      struct hw_device_t** out) {
    if (!out || !id || strcmp(id, SENSORS_HARDWARE_POLL)) return -EINVAL;
    struct empty_device* dev = calloc(1, sizeof(*dev));
    if (!dev) return -ENOMEM;
    int result = pthread_mutex_init(&dev->lock, NULL);
    if (result) { free(dev); return -result; }
    result = pthread_cond_init(&dev->changed, NULL);
    if (result) { pthread_mutex_destroy(&dev->lock); free(dev); return -result; }
    dev->api.common.tag = HARDWARE_DEVICE_TAG;
    dev->api.common.version = SENSORS_DEVICE_API_VERSION_1_3;
    dev->api.common.module = (struct hw_module_t*)module;
    dev->api.common.close = close_empty;
    dev->api.activate = activate;
    dev->api.setDelay = delay;
    dev->api.poll = poll_empty;
    dev->api.batch = batch;
    dev->api.flush = flush;
    *out = &dev->api.common;
    return 0;
}

static struct hw_module_methods_t methods = { .open = open_empty };
struct sensors_module_t HAL_MODULE_INFO_SYM = {
    .common = {
        .tag = HARDWARE_MODULE_TAG,
        .module_api_version = SENSORS_MODULE_API_VERSION_0_1,
        .hal_api_version = HARDWARE_HAL_API_VERSION,
        .id = SENSORS_HARDWARE_MODULE_ID,
        .name = "K11C no configured sensor device",
        .author = "K11C community port",
        .methods = &methods,
    },
    .get_sensors_list = get_list,
};
