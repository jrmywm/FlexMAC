#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
sta_ref=$(python -c 'import json; print(json.load(open("eda/toolchain.json"))["opensta_commit"])')
cudd_ref=$(python -c 'import json; print(json.load(open("eda/toolchain.json"))["cudd_commit"])')
task_root=$PWD
mkdir -p .tools
git init .tools/cudd
git -C .tools/cudd remote add origin https://github.com/cuddorg/cudd.git
git -C .tools/cudd fetch --depth 1 origin "$cudd_ref"
git -C .tools/cudd checkout --detach FETCH_HEAD
(
    cd .tools/cudd
    autoreconf -fi
    ./configure --prefix="$task_root/.tools/cudd-install" --enable-static --disable-shared
    make -j2
    make install
)
git init .tools/OpenSTA
git -C .tools/OpenSTA remote add origin https://github.com/parallaxsw/OpenSTA.git
git -C .tools/OpenSTA fetch --depth 1 origin "$sta_ref"
git -C .tools/OpenSTA checkout --detach FETCH_HEAD
cmake -S .tools/OpenSTA -B .tools/OpenSTA/build -DCMAKE_BUILD_TYPE=Release \
    -DCUDD_DIR="$task_root/.tools/cudd-install" \
    -DCMAKE_INTERPROCEDURAL_OPTIMIZATION=OFF -DCMAKE_INTERPROCEDURAL_OPTIMIZATION_RELEASE=OFF
cmake --build .tools/OpenSTA/build -j2
