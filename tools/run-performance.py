#!/usr/bin/env python3
"""Run matched K11C performance probes; keep raw captures private.

Requires a userdebug device with su 0, USB ADB and the diagnostics APK built
from this checkout. Run once per system; this tool never switches OS images.
"""
import argparse, hashlib, json, pathlib, re, shlex, signal, subprocess, threading, time
p = argparse.ArgumentParser()
p.add_argument('--serial', required=True)
p.add_argument('--sdk', required=True, type=int)
p.add_argument('--apk', required=True)
p.add_argument('--out', required=True)
p.add_argument('--sudo-adb', action='store_true', help='Use the root-owned ADB server on a Linux host')
a = p.parse_args()
out = pathlib.Path(a.out)
out.mkdir(parents=True, exist_ok=False)
adb = (['sudo', '-n'] if a.sudo_adb else []) + ['adb', '-s', a.serial]
pkg = 'org.kickpi.diagnostics'
stresses = []
stop = threading.Event()
samples = []
phase = 'prepare'
safety = []

def terminate(signum, frame):
    raise SystemExit('Interrupted by signal ' + str(signum))

signal.signal(signal.SIGTERM, terminate)

def command(args, timeout=60):
    r = subprocess.run(adb + args, capture_output=True, text=True, timeout=timeout)
    if r.returncode:
        raise RuntimeError(str(args) + ': ' + r.stderr[-2000:] + r.stdout[-2000:])
    return r.stdout.strip()

def shell(script, root=False, timeout=60):
    return command(['shell', '-T', shlex.join(['su', '0', 'sh', '-c', script]) if root else script], timeout)

def save(name, value):
    (out / (name + '.json')).write_text(json.dumps(value, indent=2) + '\n')

def log(value):
    print(time.strftime('%H:%M:%S'), value, flush=True)
    (out / 'progress.txt').open('a').write(time.strftime('%H:%M:%S') + ' ' + value + '\n')

def sample():
    raw = shell('head -1 /proc/stat; echo MEM; cat /proc/meminfo; echo TEMP; for z in /sys/class/thermal/thermal_zone*; do cat $z/type $z/temp; done; echo FREQ; cat /sys/devices/system/cpu/cpufreq/policy0/scaling_cur_freq; echo PSI; cat /proc/pressure/memory /proc/pressure/cpu /proc/pressure/io', True)
    cpu, raw = raw.split('\nMEM\n')
    mem, raw = raw.split('\nTEMP\n')
    temps, raw = raw.split('\nFREQ\n')
    freq, psi = raw.split('\nPSI\n')
    lines = temps.splitlines()
    return {'t': time.monotonic(), 'phase': phase, 'cpu': [int(x) for x in cpu.split()[1:]], 'mem_kib': {k: int(v) for k, v in re.findall('^(\\w+):\\s+(\\d+) kB', mem, re.M)}, 'temperature_c': {lines[i]: int(lines[i + 1]) / 1000 for i in range(0, len(lines), 2)}, 'cpu_frequency_khz': int(freq), 'psi': psi}

def kill_stress():
    for pid in stresses[:]:
        subprocess.run(adb + ['shell', 'kill', pid], capture_output=True, timeout=10)
    stresses.clear()

def monitor():
    while not stop.is_set():
        try:
            item = sample()
            samples.append(item)
            if max(item['temperature_c'].values()) >= 85:
                safety.append({'temperature_c': item['temperature_c'], 'phase': phase})
                kill_stress()
        except Exception as e:
            log('monitor error: ' + str(e))
        stop.wait(3)

def begin(value):
    global phase
    phase = value
    log(value)

def probe(feature, label=None):
    name = label or feature
    begin(name)
    raw = shell('am instrument -w -e test ' + feature + ' -e duration_ms 30000 ' + pkg + '/.Probe', timeout=70)
    (out / (name + '.txt')).write_text(raw + '\n')
    reports = []
    for line in raw.splitlines():
        try:
            obj = json.loads(line)
        except ValueError:
            continue
        if obj.get('test') == feature:
            reports.append(obj)
    shell('am force-stop ' + pkg)
    if len(reports) != 1 or reports[0].get('status') != 'PASS':
        raise RuntimeError(name + ' probe failed: ' + raw[-2000:])
    result = reports[0]
    save(name, result)
    log(name + ' ' + json.dumps(result))
    return result

def cool():
    begin('cooldown')
    shell('input keyevent KEYCODE_HOME')
    deadline = time.monotonic() + 240
    while time.monotonic() < deadline:
        item = sample()
        if item['temperature_c']['soc-thermal'] <= 56.5:
            return item
        time.sleep(5)
    return sample()

def scrolling(label):
    begin(label)
    shell('am force-stop com.android.settings')
    shell('am start -W -a android.settings.SETTINGS')
    time.sleep(2)
    shell('dumpsys gfxinfo com.android.settings reset')
    before = sample()
    started = time.monotonic()
    for i in range(24):
        shell('input swipe 650 ' + ('500 650 150' if i % 2 == 0 else '150 650 500') + ' 250')
    raw = shell('dumpsys gfxinfo com.android.settings framestats')
    (out / (label + '.txt')).write_text(raw)
    after = sample()
    result = {'wall_seconds': time.monotonic() - started}
    for key, pattern in {'frames': 'Total frames rendered: (\\d+)', 'janky': 'Janky frames: (\\d+)', 'p50_ms': '50th percentile: (\\d+)ms', 'p90_ms': '90th percentile: (\\d+)ms', 'p95_ms': '95th percentile: (\\d+)ms', 'p99_ms': '99th percentile: (\\d+)ms', 'gpu_p95_ms': '95th gpu percentile: (\\d+)ms'}.items():
        hit = re.search(pattern, raw)
        if hit:
            result[key] = int(hit.group(1))
    result['cpu_busy_percent'] = busy(before, after)
    result['temperature_before_c'] = before['temperature_c']
    result['temperature_after_c'] = after['temperature_c']
    if result.get('frames', 0) < 100:
        raise RuntimeError('too few scroll frames ' + str(result))
    save(label, result)
    return result

def busy(x, y):
    d = [b - a for a, b in zip(x['cpu'], y['cpu'])]
    return 100 * (sum(d[:8]) - d[3] - d[4]) / sum(d[:8])
result = {}
original = {}
installed = False
thread = None
try:
    assert shell('getprop ro.build.version.sdk') == str(a.sdk)
    assert shell('getprop sys.boot_completed') == '1'
    assert shell('getenforce') == 'Enforcing'
    assert 'package:' + pkg not in shell('pm list packages ' + pkg).splitlines(), 'diagnostics already installed'
    result['metadata'] = {'sdk': a.sdk, 'fingerprint': shell('getprop ro.build.fingerprint'), 'kernel': shell('uname -r'), 'wm': shell('wm size; wm density'), 'navigation_mode': shell('settings get secure navigation_mode'), 'apk_sha256': hashlib.sha256(pathlib.Path(a.apk).read_bytes()).hexdigest(), 'dsu_slot': shell('getprop ro.gsid.dsu_slot', True), 'cpu_policy': shell('cat /sys/devices/system/cpu/cpufreq/policy0/scaling_governor /sys/devices/system/cpu/cpufreq/policy0/scaling_available_frequencies', True)}
    for table, keys in {'system': ['min_refresh_rate', 'peak_refresh_rate', 'screen_brightness', 'screen_brightness_mode', 'screen_off_timeout'], 'global': ['window_animation_scale', 'transition_animation_scale', 'animator_duration_scale']}.items():
        for key in keys:
            original[table + ':' + key] = shell('settings get ' + table + ' ' + key)
    result['original_settings'] = original
    save('original-settings', original)
    result['pids_before'] = shell('pidof system_server surfaceflinger zygote64')
    (out / 'crash-before.txt').write_text(shell('logcat -b crash -d', True))
    (out / 'display-before.txt').write_text(shell('dumpsys display'))
    (out / 'background-before.txt').write_text(shell('ps -A; dumpsys thermalservice; dumpsys meminfo; df -k /data', True))
    for key, value in [('screen_brightness_mode', '0'), ('screen_brightness', '102'), ('screen_off_timeout', '2147483647')]:
        shell('settings put system ' + key + ' ' + value)
    for key in ['window_animation_scale', 'transition_animation_scale', 'animator_duration_scale']:
        shell('settings put global ' + key + ' 1.0')
    shell('input keyevent KEYCODE_WAKEUP')
    shell('input swipe 500 550 500 120 300')
    shell('wm dismiss-keyguard')
    shell('input keyevent KEYCODE_HOME')
    time.sleep(2)
    command(['install', a.apk])
    installed = True
    shell('pm grant ' + pkg + ' android.permission.RECORD_AUDIO')
    for i in range(3):
        probe('gpu', 'warmup-gpu-' + str(i))
        shell('am start -W -a android.settings.SETTINGS')
        shell('input keyevent KEYCODE_HOME')
    cool()
    begin('idle-60s')
    idle_start = sample()
    thread = threading.Thread(target=monitor, daemon=True)
    thread.start()
    time.sleep(60)
    idle_end = sample()
    result['idle'] = {'seconds': idle_end['t'] - idle_start['t'], 'cpu_busy_percent': busy(idle_start, idle_end), 'mem_kib': idle_end['mem_kib'], 'temperature_c': idle_end['temperature_c'], 'psi': idle_end['psi']}
    for key in ['min_refresh_rate', 'peak_refresh_rate']:
        shell('settings delete system ' + key)
    result['animation_default'] = [probe('animation', 'animation-default-' + str(i)) for i in range(3)]
    for key in ['min_refresh_rate', 'peak_refresh_rate']:
        shell('settings put system ' + key + ' 62.0')
    result['animation_fixed62'] = [probe('animation', 'animation-fixed62-' + str(i)) for i in range(3)]
    result['scroll_fixed62'] = [scrolling('scroll-fixed62-' + str(i)) for i in range(3)]
    begin('settings-launch')
    launches = []
    for i in range(10):
        row = {}
        for mode in ['cold', 'warm']:
            if mode == 'cold':
                shell('am force-stop com.android.settings')
            shell('input keyevent KEYCODE_HOME')
            time.sleep(0.4)
            raw = shell('am start -W -a android.settings.SETTINGS')
            (out / ('launch-' + str(i) + '-' + mode + '.txt')).write_text(raw)
            row[mode] = {k: int(v) for k, v in re.findall('^(TotalTime|WaitTime|ThisTime): (\\d+)', raw, re.M)}
            row[mode]['launch_state'] = next((s.split(': ', 1)[1] for s in raw.splitlines() if s.startswith('LaunchState:')), 'unknown')
            time.sleep(0.7)
        launches.append(row)
    result['settings_launch'] = launches
    result['storage'] = [probe('storage', 'storage-' + str(i)) for i in range(3)]
    result['gpu'] = [probe('gpu', 'gpu-' + str(i)) for i in range(3)]
    result['compute'] = [probe('compute', 'compute-' + str(i)) for i in range(3)]
    result['media'] = {feature: [probe(feature, feature + '-' + str(i)) for i in range(3)] for feature in ['video-hardware-1080p60-surface', 'video-hardware-1080p60-bounded', 'video-software', 'audio-decode']}
    cool()
    begin('load-start')
    result['load_start'] = sample()
    for i in range(4):
        pid = shell('nohup sha256sum /dev/zero >/dev/null 2>&1 </dev/null & echo $!')
        assert pid.isdigit(), pid
        stresses.append(pid)
    time.sleep(10)
    result['animation_loaded'] = [probe('animation', 'animation-loaded-' + str(i)) for i in range(3)]
    result['scroll_loaded'] = [scrolling('scroll-loaded-' + str(i)) for i in range(3)]
    result['load_end'] = sample()
    kill_stress()
    result['pids_after'] = shell('pidof system_server surfaceflinger zygote64')
    result['core_pids_stable'] = result['pids_before'] == result['pids_after']
    (out / 'crash-after.txt').write_text(shell('logcat -b crash -d', True))
    (out / 'background-after.txt').write_text(shell('ps -A; dumpsys thermalservice; dumpsys meminfo; df -k /data', True))
    result['safety_events'] = safety
    result['completed'] = True
except BaseException as error:
    result['error'] = repr(error)
    log('ERROR ' + repr(error))
    raise
finally:
    kill_stress()
    stop.set()
    if thread:
        thread.join(timeout=15)
    save('samples', samples)
    if installed:
        subprocess.run(adb + ['uninstall', pkg], capture_output=True, timeout=30)
    for table_key, value in original.items():
        table, key = table_key.split(':')
        try:
            shell('settings ' + ('delete ' + table + ' ' + key if value == 'null' else 'put ' + table + ' ' + key + ' ' + shlex.quote(value)))
        except Exception as e:
            log('restore error ' + str(e))
            result.setdefault('restore_errors', []).append(str(e))
    try:
        shell('input keyevent KEYCODE_HOME')
        result['restored_settings'] = {tk: shell('settings get ' + tk.replace(':', ' ')) for tk in original}
        result['settings_restored'] = original == result['restored_settings']
    except Exception as e:
        result['restore_error'] = str(e)
    save('results', result)
    log('FINISHED completed=' + str(result.get('completed', False)))
