#!/usr/bin/env python3
"""Reserve temporary 2 MiB huge pages per CPU-bearing NUMA node."""
import argparse
import os
from pathlib import Path
import subprocess
import sys

from mine import cpu_list


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--apply', action='store_true', help='apply the printed plan; requires sudo')
    args = p.parse_args()
    try:
        if not sys.platform.startswith('linux'):
            p.error('This helper requires Linux')
        nodes = Path('/sys/devices/system/node')
        online = cpu_list(Path('/sys/devices/system/cpu/online').read_text())
        plan = []
        for node in sorted(nodes.glob('node[0-9]*')):
            cpus = cpu_list((node / 'cpulist').read_text()) if (node / 'cpulist').read_text().strip() else set()
            count = len(cpus & online)
            if not count:
                continue
            path = node / 'hugepages/hugepages-2048kB/nr_hugepages'
            current = int(path.read_text())
            # 2080 MiB dataset + 256 MiB cache, 2 MiB per worker, and headroom.
            target = max(current, 1168 + count + 32)
            total_kib = next(int(line.split()[-2]) for line in
                             (node / 'meminfo').read_text().splitlines() if 'MemTotal:' in line)
            if target * 2048 > total_kib // 2:
                p.error(f'{node.name}: reservation would exceed half the node RAM; review NUMA layout')
            plan.append((path, target))
            print(f'{node.name}: {count} online threads; {current} -> {target} huge pages '
                  f'({target * 2} MiB reserved)')
        if not plan:
            p.error('No CPU-bearing NUMA nodes with 2 MiB huge-page support found')
        if not args.apply:
            print('Preview only. Apply with: sudo python3 hugepages.py --apply')
            return 0
        if os.geteuid() != 0 or not os.environ.get('SUDO_GID'):
            p.error('Run from your mining user account with sudo python3 hugepages.py --apply')
        gid = int(os.environ['SUDO_GID'])
        subprocess.run(['sysctl', '-w', f'vm.hugetlb_shm_group={gid}'], check=True)
        failed = False
        for path, target in plan:
            path.write_text(str(target))
            actual = int(path.read_text())
            print(f'{path.parents[2].name}: allocated {actual}/{target} pages')
            failed |= actual < target
        print('Settings are temporary and reset at reboot. Run mining as your normal user.')
        if failed:
            print('Partial allocation: stop memory-heavy applications or reboot and apply early.', file=sys.stderr)
            return 1
        return 0
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f'Cannot configure huge pages: {error}. Earlier changes may have applied; reboot resets them.',
              file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
