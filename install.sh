#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
if [[ "$(uname -s)" != Linux || "$(uname -m)" != x86_64 ]]; then
    echo 'This installer requires x86-64 Linux.' >&2
    exit 1
fi
if (( EUID == 0 )); then
    echo 'Run bash install.sh as your normal user; sudo is used only for packages.' >&2
    exit 1
fi
source /etc/os-release
if [[ "${ID:-}" != ubuntu || "${VERSION_ID:-}" != 26.04 ]]; then
    echo 'Designed for Ubuntu 26.04 LTS; this host is a different release.' >&2
fi
version=v6.26.0
sudo apt-get update
sudo apt-get install -y git build-essential cmake libuv1-dev libssl-dev libhwloc-dev python3
mkdir -p vendor bin
source_dir="vendor/xmrig-${version}"
if [[ ! -e "$source_dir" ]]; then
    git clone --depth 1 --branch "$version" https://github.com/xmrig/xmrig.git "$source_dir"
fi
[[ "$(git -C "$source_dir" describe --tags --exact-match HEAD)" == "$version" ]]
if [[ -n "$(git -C "$source_dir" status --porcelain --untracked-files=no)" ]]; then
    echo 'XMRig tracked source files were modified; refusing to build.' >&2
    exit 1
fi
cmake -S "$source_dir" -B "$source_dir/build" -DCMAKE_BUILD_TYPE=Release \
    -DWITH_HWLOC=ON -DWITH_TLS=ON -DWITH_OPENCL=OFF -DWITH_CUDA=OFF
# Keep compilation memory use modest; this does not limit mining workers.
jobs="$(nproc)"
if (( jobs > 16 )); then jobs=16; fi
cmake --build "$source_dir/build" --parallel "$jobs"
install -m 755 "$source_dir/build/xmrig" bin/xmrig
git -C "$source_dir" rev-parse HEAD > bin/xmrig-source-commit.txt
bin/xmrig --version
echo 'Installed. See README.md for huge pages, benchmarks, and mining commands.'
