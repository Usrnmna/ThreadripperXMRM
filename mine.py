#!/usr/bin/env python3
"""Topology-aware foreground launcher for the upstream XMRig engine."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent
SYS_CPU = Path('/sys/devices/system/cpu')


def cpu_list(value):
    result = set()
    for part in value.strip().split(','):
        bounds = part.split('-')
        if len(bounds) == 1:
            result.add(int(bounds[0]))
        elif len(bounds) == 2 and int(bounds[0]) <= int(bounds[1]):
            result.update(range(int(bounds[0]), int(bounds[1]) + 1))
        else:
            raise ValueError('Invalid Linux CPU list')
    return result


def select_cpus(allowed, mode, sys_cpu=SYS_CPU):
    """Use actual sibling sets, not an assumption that CPUs 0..63 are cores."""
    allowed = sorted(allowed)
    if not allowed:
        raise ValueError('No CPUs are available to this process')
    if mode == 'all':
        return allowed
    selected, seen = [], set()
    for cpu in allowed:
        siblings = frozenset(cpu_list(
            (sys_cpu / f'cpu{cpu}/topology/thread_siblings_list').read_text()))
        if siblings not in seen:
            selected.append(cpu)
            seen.add(siblings)
    return selected


def pool_address(value):
    # Require an explicit port. TLS is selected separately, including for IPv6.
    if not re.fullmatch(r'(?:\[[0-9a-fA-F:]+\]|[A-Za-z0-9_.-]+):[0-9]+', value):
        raise argparse.ArgumentTypeError('Use pool-host:port or [IPv6]:port, without a URL scheme')
    if not 1 <= int(value.rsplit(':', 1)[1]) <= 65535:
        raise argparse.ArgumentTypeError('Pool port must be between 1 and 65535')
    return value


def wallet_address(value):
    if len(value) not in (95, 106) or not re.fullmatch(r'[1-9A-HJ-NP-Za-km-z]+', value):
        raise argparse.ArgumentTypeError('Expected a 95- or 106-character Monero public address')
    return value


def configuration(cpus, args):
    pools = []
    if args.command == 'mine':
        pools.append({'coin': 'monero', 'algo': None, 'url': args.pool,
                      'user': args.wallet, 'pass': args.password,
                      'rig-id': args.rig_id, 'tls': not args.no_tls,
                      'keepalive': True, 'enabled': True})
    return {
        'autosave': False, 'background': False, 'watch': False,
        'donate-level': 1, 'print-time': 30, 'health-print-time': 60,
        'http': {'enabled': False},
        'randomx': {'init': -1, 'mode': 'fast', 'numa': True,
                    '1gb-pages': False, 'rdmsr': False, 'wrmsr': False},
        'cpu': {'enabled': True, 'huge-pages': True, 'memory-pool': True,
                'yield': True, 'asm': True, 'rx': cpus},
        'opencl': {'enabled': False}, 'cuda': {'enabled': False},
        'pools': pools,
    }


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    commands = result.add_subparsers(dest='command', required=True)
    for name in ('mine', 'benchmark', 'inspect'):
        p = commands.add_parser(name)
        p.add_argument('--workers', choices=('all', 'cores'), default='all',
                       help='all: every allowed hardware thread; cores: one worker per physical core')
        p.add_argument('--dry-run', action='store_true', help='print config without starting XMRig')
        p.add_argument('--xmrig', type=Path, default=ROOT / 'bin/xmrig')
        if name == 'mine':
            p.add_argument('pool', type=pool_address, help='host:port')
            p.add_argument('wallet', type=wallet_address, help='public payout address, never seed/private key')
            p.add_argument('--password', default='x', help='pool-specific password, usually x')
            p.add_argument('--rig-id', default='threadripper')
            p.add_argument('--no-tls', action='store_true', help='for pools without TLS or local P2Pool')
        if name == 'benchmark':
            p.add_argument('--size', choices=('1M', '10M'), default='1M')
            p.add_argument('--algo', choices=('rx/0', 'rx/2'), default='rx/0')
    return result


def main():
    p = parser()
    args = p.parse_args()
    if not sys.platform.startswith('linux') or not hasattr(os, 'sched_getaffinity'):
        p.error('Run this launcher on Linux; mining is not started on this host')
    try:
        allowed = os.sched_getaffinity(0)
        cpus = select_cpus(allowed, args.workers)
        cores = select_cpus(allowed, 'cores')
        config = configuration(cpus, args)
        print(f'Available: {len(cores)} physical cores / {len(allowed)} hardware threads. '
              f'Selected: {len(cpus)} workers.', flush=True)
        print('CPU affinity: ' + ','.join(map(str, cpus)), flush=True)
        if len(allowed) != 64 or len(cores) != 32:
            print('Expected 32 cores / 64 threads for your stated CPU with SMT enabled. '
                  'Check firmware SMT, offline CPUs, and process/container CPU restrictions.', flush=True)
        if args.command == 'inspect' or args.dry_run:
            print(json.dumps(config, indent=2))
            return 0
        executable = args.xmrig.expanduser().resolve()
        if not executable.is_file() or not os.access(executable, os.X_OK):
            p.error(f'XMRig executable missing or not executable: {executable}. Run bash install.sh')
        # The file is private and removed on normal exit; the wallet is public.
        with tempfile.TemporaryDirectory(prefix='monero-threadripper-') as temporary:
            config_path = Path(temporary) / 'config.json'
            config_path.write_text(json.dumps(config, indent=2), encoding='utf-8')
            os.chmod(config_path, 0o600)
            command = [str(executable), '--config', str(config_path)]
            if args.command == 'benchmark':
                command.extend(['--bench', args.size, '--algo', args.algo])
            child = subprocess.Popen(command)
            try:
                return child.wait()
            except KeyboardInterrupt:
                # The foreground process group also delivers Ctrl+C to XMRig.
                try:
                    return child.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    child.terminate()
                    try:
                        child.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        child.kill()
                        child.wait()
                return 130
    except (OSError, ValueError) as error:
        p.error(str(error))


if __name__ == '__main__':
    sys.exit(main())
