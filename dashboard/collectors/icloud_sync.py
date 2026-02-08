import os
import time
import config

_cache = None
_cache_time = 0


def collect():
    global _cache, _cache_time

    now = time.time()
    if _cache is not None and (now - _cache_time) < config.PHOTOS_CACHE_TTL:
        return _cache

    root = config.PHOTOS_ROOT
    total_count = 0
    total_size = 0
    by_year = {}
    by_extension = {}
    recent_files = []

    if not os.path.isdir(root):
        _cache = {
            "total_count": 0,
            "total_size_bytes": 0,
            "total_size_human": "0 B",
            "by_year": [],
            "by_extension": {},
            "recent_files": [],
            "photos_root": root,
            "error": f"Directory not found: {root}",
        }
        _cache_time = now
        return _cache

    for dirpath, _dirnames, filenames in os.walk(root):
        for fname in filenames:
            filepath = os.path.join(dirpath, fname)
            try:
                stat = os.stat(filepath)
                fsize = stat.st_size
                mtime = stat.st_mtime
            except OSError:
                continue

            total_count += 1
            total_size += fsize

            # Extract year from path: .../YYYY/MM/DD/file
            rel = os.path.relpath(filepath, root)
            parts = rel.split(os.sep)
            if len(parts) >= 1 and parts[0].isdigit():
                year = parts[0]
                by_year[year] = by_year.get(year, 0) + 1

            # Extension
            ext = os.path.splitext(fname)[1].upper()
            if ext:
                by_extension[ext] = by_extension.get(ext, 0) + 1

            # Track recent files (keep top 10 by mtime)
            recent_files.append((mtime, fname, fsize))
            if len(recent_files) > 50:
                recent_files.sort(key=lambda x: x[0], reverse=True)
                recent_files = recent_files[:10]

    recent_files.sort(key=lambda x: x[0], reverse=True)
    recent_files = recent_files[:10]

    _cache = {
        "total_count": total_count,
        "total_size_bytes": total_size,
        "total_size_human": _human_size(total_size),
        "by_year": sorted(
            [{"year": y, "count": c} for y, c in by_year.items()],
            key=lambda x: x["year"],
        ),
        "by_extension": by_extension,
        "recent_files": [
            {
                "filename": f[1],
                "modified": time.strftime("%Y-%m-%d %H:%M", time.localtime(f[0])),
                "size_human": _human_size(f[2]),
            }
            for f in recent_files
        ],
        "photos_root": root,
        "error": None,
    }
    _cache_time = now
    return _cache


def _human_size(nbytes):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if nbytes < 1024:
            return f"{nbytes:.1f} {unit}"
        nbytes /= 1024
    return f"{nbytes:.1f} PB"
