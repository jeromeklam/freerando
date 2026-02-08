import psutil
import time

_prev_net_io = None
_prev_net_time = None


def collect():
    global _prev_net_io, _prev_net_time

    # CPU Temperature
    cpu_temp = None
    temps = psutil.sensors_temperatures()
    if "cpu_thermal" in temps and temps["cpu_thermal"]:
        cpu_temp = temps["cpu_thermal"][0].current

    # CPU Usage
    cpu_percent = psutil.cpu_percent(interval=0.1)
    cpu_per_core = psutil.cpu_percent(interval=0.1, percpu=True)

    # CPU Frequency
    freq = psutil.cpu_freq()

    # RAM
    mem = psutil.virtual_memory()

    # Disks - filter out squashfs/loop/tmpfs
    disks = []
    for part in psutil.disk_partitions(all=False):
        if part.fstype in ("squashfs",) or "loop" in part.device:
            continue
        try:
            usage = psutil.disk_usage(part.mountpoint)
            disks.append({
                "device": part.device,
                "mountpoint": part.mountpoint,
                "fstype": part.fstype,
                "total": usage.total,
                "used": usage.used,
                "free": usage.free,
                "percent": usage.percent,
            })
        except PermissionError:
            pass

    # Network speed (delta-based)
    current_net = psutil.net_io_counters()
    current_time = time.time()
    upload_speed = 0
    download_speed = 0
    if _prev_net_io is not None:
        dt = current_time - _prev_net_time
        if dt > 0:
            upload_speed = round((current_net.bytes_sent - _prev_net_io.bytes_sent) / dt)
            download_speed = round((current_net.bytes_recv - _prev_net_io.bytes_recv) / dt)
    _prev_net_io = current_net
    _prev_net_time = current_time

    # IPs
    ips = {}
    for nic, addrs in psutil.net_if_addrs().items():
        if nic == "lo":
            continue
        for a in addrs:
            if a.family.name == "AF_INET":
                ips[nic] = a.address

    # Uptime
    boot = psutil.boot_time()
    uptime_seconds = int(time.time() - boot)

    return {
        "cpu_temp": cpu_temp,
        "cpu_percent": cpu_percent,
        "cpu_per_core": cpu_per_core,
        "cpu_freq": {
            "current": freq.current if freq else None,
            "min": freq.min if freq else None,
            "max": freq.max if freq else None,
        },
        "ram": {
            "total": mem.total,
            "used": mem.total - mem.available,
            "available": mem.available,
            "percent": mem.percent,
        },
        "disks": disks,
        "network": {
            "ips": ips,
            "upload_speed": upload_speed,
            "download_speed": download_speed,
        },
        "uptime_seconds": uptime_seconds,
        "timestamp": time.time(),
    }
