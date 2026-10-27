#!/usr/bin/env bash
set -euo pipefail
if [[ "${GITHUB_ACTIONS:-}" != true ]]; then
    echo 'This installer is for the disposable Ubuntu CI runner only.' >&2
    exit 2
fi
# The Azure mirror was transferring packages very slowly in the first runs.
# Keep Ubuntu's signed packages, using its main archive instead.
for task_source in /etc/apt/sources.list /etc/apt/sources.list.d/ubuntu.sources; do
    if [[ -f "$task_source" ]]; then
        sudo sed -i 's|http://azure.archive.ubuntu.com/ubuntu|https://archive.ubuntu.com/ubuntu|g' "$task_source"
    fi
done
packages=(yosys iverilog)
if [[ "${1:-}" == timing ]]; then
    packages+=(cmake g++ make autoconf automake libtool flex libfl-dev bison swig
        tcl-dev zlib1g-dev libeigen3-dev libfmt-dev)
fi
if [[ "${1:-}" == replay ]]; then packages+=(verilator g++ make); fi
sudo apt-get -o Acquire::Retries=1 -o Acquire::http::Timeout=30 -o Acquire::https::Timeout=30 update
sudo apt-get -o Acquire::Retries=1 -o Acquire::http::Timeout=30 -o Acquire::https::Timeout=30 \
    install --no-install-recommends -y "${packages[@]}"
