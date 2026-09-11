#!/bin/sh
set -eu
cd /work
mkdir -p logs build prefix dist
exec > logs/build.log 2>&1
apk add --no-cache build-base cmake ninja git python3 libffi-dev zlib-dev zstd-dev libxml2-dev binutils patch bash coreutils diffutils
apk info -v > logs/apk-packages.txt
git config --global --add safe.directory '*'
cp -a /src source
for patchfile in /src/ci/musl/patches/*.patch; do patch -d source -p1 < "$patchfile"; done
cmake -S source/llvm -B build -G Ninja -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_INSTALL_PREFIX=/work/prefix -DCMAKE_INSTALL_LIBDIR=lib \
  -DCMAKE_INSTALL_RPATH='$ORIGIN/../lib' -DLLVM_BUILD_LLVM_DYLIB=ON \
  -DLLVM_LINK_LLVM_DYLIB=ON -DLLVM_TARGETS_TO_BUILD=all \
  -DLLVM_ENABLE_RTTI=ON -DLLVM_ENABLE_EH=ON -DLLVM_ENABLE_ASSERTIONS=OFF \
  -DLLVM_ENABLE_FFI=ON -DLLVM_ENABLE_ZLIB=ON -DLLVM_ENABLE_ZSTD=ON \
  -DLLVM_ENABLE_LIBXML2=ON -DLLVM_ENABLE_CURL=OFF -DLLVM_ENABLE_LIBEDIT=OFF \
  -DLLVM_ENABLE_TERMINFO=OFF -DLLVM_BUILD_TESTS=ON -DLLVM_INCLUDE_BENCHMARKS=OFF \
  -DLLVM_INCLUDE_EXAMPLES=OFF -DLLVM_APPEND_VC_REV=OFF \
  > logs/configure.log 2>&1
cmake --build build --parallel 2 --target LLVM llvm-config llc opt llvm-as llvm-dis SupportTests ADTTests > logs/compile.log 2>&1
build/unittests/ADT/ADTTests > logs/tests.log 2>&1
build/unittests/Support/SupportTests >> logs/tests.log 2>&1
cmake --build build --target install-LLVM install-llvm-config install-llc install-opt install-llvm-as install-llvm-dis install-llvm-headers install-cmake-exports > logs/install.log 2>&1
python /src/ci/musl/package.py
