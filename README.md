# Monero mining for a 32-core Threadripper

Ubuntu 26.04 LTS x86-64 launcher and source installer for XMRig. Python configures
and starts the miner; XMRig's native code performs RandomX hashing and pool work.
The package requires internet access to install and a pool plus your public payout
address to mine. No wallet is needed for the offline benchmark.

## Hardware and worker count

This setup targets your **32-core Threadripper**, identified by you as 3990WX.
It reads the actual Linux topology instead of requiring a particular model name.
With SMT enabled, the default is **64 workers**, explicitly pinned to all allowed
Linux CPU IDs. At 2 MiB per worker, 64 workers require a 128 MiB L3 cache
budget, distributed appropriately among the CPU's cache groups. The exact
model and cache capacity have not been verified; the worker count follows
your stated 32-core/64-thread specification. Memory bandwidth, temperatures,
and clock speeds determine whether it beats 32 workers on your machine.

The launcher detects Linux CPU affinity and SMT sibling groups. A constrained
container or disabled SMT produces fewer workers and a notice. `--workers cores`
uses one available hardware thread per physical core. It does not assume that
the first 32 Linux CPU IDs correspond to 32 different cores.

64 GB RAM is sufficient for typical NUMA configurations. RandomX uses a dataset
per NUMA node; it does not need or benefit from allocating all 64 GB. NUMA support
remains enabled. Populate memory channels according to your motherboard manual.

## Install on Ubuntu

Copy this entire folder to your Ubuntu computer, open a terminal in it, and run:

```bash
bash install.sh
python3 mine.py inspect
```

The installer builds upstream XMRig **v6.26.0** with hardware topology and TLS
support, installing the executable under `bin/`. This is a pinned version,
not a claim that it is the latest release. The source commit is recorded in
`bin/xmrig-source-commit.txt`. Dependencies are installed using Ubuntu's package
manager. Source code stays in `vendor/` with its upstream license.
Compilation uses up to 16 jobs; mining uses all 64 available threads.

## Enable 2 MiB huge pages

Preview and then apply the per-node reservation:

```bash
python3 hugepages.py
sudo python3 hugepages.py --apply
```

This helper reserves a dataset/cache allowance, one page per online hardware
thread, and some headroom on each CPU-bearing NUMA node. On a single-node,
64-thread system, the target is 1,264 pages (2,528 MiB). It preserves larger
existing reservations and refuses a plan exceeding half of any node's RAM.
The reservation and `vm.hugetlb_shm_group` setting last until reboot; the group
setting permits your user's primary group to allocate huge pages. On a shared
machine, this replaces the existing huge-page group setting for this boot.
No boot files or permanent system configuration are changed. Reboot to undo.

Partial reservation exits with an error. Apply early after reboot if RAM is
fragmented. In XMRig output, check that both dataset and workers show
`huge pages 100%`; reserved pages alone do not establish successful use.
Run the miner as your normal user. MSR tuning and 1 GiB pages are disabled in
this package; additional tuning could improve performance but is not required
to use every hardware thread.

## Saved configuration file

`config.json` contains the 32-core / 64-thread preset. Before live mining, edit
`pools[0].url` to your pool's host and port and `pools[0].user` to your public
Monero payout address. These two fields currently contain placeholders; the
file cannot mine successfully until they are replaced. Set `pools[0].tls` to
match that endpoint (currently `true`). The pool password defaults to `x`.

After installing XMRig and configuring huge pages as described above, run from
this package folder on Ubuntu:

```bash
./bin/xmrig --config ./config.json
```

This saved configuration explicitly pins 64 RandomX workers to Linux CPU IDs
0 through 63. It assumes all those CPUs are online and available to your process.
Check `python3 mine.py inspect` on the target machine first. If the available
CPU IDs differ, use the topology-aware `mine.py mine` command below instead.
The Python launcher generates its own configuration and does not load this file.

The preset enables NUMA and 2 MiB huge-page support, disables GPU mining and
remote HTTP control, and retains the upstream 1% donation. No MSR changes or
1 GiB page allocation are requested. It runs in the foreground; Ctrl+C stops it.
Configuration JSON and worker selection were checked locally. Native XMRig
startup, pool login, and accepted shares still require validation on Ubuntu
with your pool and wallet filled in.

Settings reference: [XMRig CPU configuration](https://xmrig.com/docs/miner/config/cpu)
and [pool configuration](https://xmrig.com/docs/miner/config/pool).

## Mine

Replace the example host and address with your pool's **TLS endpoint** and your
public Monero payout address:

```bash
python3 mine.py mine POOL_HOST:TLS_PORT YOUR_MONERO_ADDRESS
```

For a pool endpoint without TLS, or an already configured local P2Pool server:

```bash
python3 mine.py mine 127.0.0.1:3333 YOUR_MONERO_ADDRESS --no-tls
```

The local command assumes P2Pool is already running; this package does not
install a Monero node or P2Pool. Use `--password` or `--rig-id` when your pool
requires them. Pool support for worker identifiers varies. Address validation
checks length and Base58 characters only; confirm network and checksum in your
wallet. Never enter a seed phrase or private key.

XMRig runs visibly in the foreground. Press **Ctrl+C** to stop. Look for accepted
shares to establish that the pool connection and work submission are working.
The pool controls payout thresholds and fees. Upstream XMRig's **1% developer
donation** remains enabled. No background service or automatic startup is installed.

To review the exact generated configuration without starting mining:

```bash
python3 mine.py mine POOL_HOST:TLS_PORT YOUR_MONERO_ADDRESS --dry-run
```

## Compare 64 versus 32 workers

Run these sequentially under similar temperature and background-load conditions:

```bash
python3 mine.py benchmark --size 1M
python3 mine.py benchmark --size 1M --workers cores
```

These are offline RandomX `rx/0` benchmarks and do not publish results. Use `10M`
for a longer comparison. Check XMRig's checksum, reported hash rate, worker count,
and huge-page utilization. `--algo rx/2` is available for an explicit RandomX v2
benchmark; mining uses `coin: monero` and leaves algorithm selection to XMRig
and the pool's jobs. For 32-worker mining, add `--workers cores` to the mine command.
Watch CPU temperature and sustained clocks during your first long run.

## Validation boundary

The included unit tests exercise 64-thread selection, 32-core SMT selection,
sparse CPU affinity, config serialization, TLS selection, and input validation:

```bash
python3 -m unittest -v
```

This package was authored on Windows. Ubuntu dependency installation, native
compilation, huge-page allocation, real hashing, pool connections, and payouts
have **not** been verified on the target hardware. No hash-rate claim is made.

## References

- [XMRig Ubuntu build](https://xmrig.com/docs/miner/build/ubuntu)
- [RandomX tuning](https://xmrig.com/docs/miner/randomx-optimization-guide)
- [CPU configuration](https://xmrig.com/docs/miner/config/cpu)
- [Huge pages](https://xmrig.com/docs/miner/hugepages)
- [Benchmarks](https://xmrig.com/docs/miner/benchmark)
