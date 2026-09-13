# llvm-project: reproducible platform builds

This guide describes the InsightOS fork/import and the scripts in this checkout.
The validated distribution from this repository is **Linux x86_64 musl**. glibc
and macOS source recipes below are native development builds, not a claim that
this fork publishes or has requalified those binaries. The complete installer
selects different binary formats and dependency locks for each platform.

## Source and tools

Validated musl tag: [`musl-v21.1.2-1`](https://github.com/insightos-community/llvm-project/releases/tag/musl-v21.1.2-1);
source commit: `bf34d4037a24448468ce46ee56c8a0c0bee802e3`. Use a normal clone so container packaging can read `.git`.

```bash
git clone https://github.com/insightos-community/llvm-project.git llvm-project-repro
cd llvm-project-repro
git checkout --detach musl-v21.1.2-1
test "$(git rev-parse HEAD)" = bf34d4037a24448468ce46ee56c8a0c0bee802e3
```

Native build prerequisites: C++ compiler, CMake, Ninja and Python. Provision at least the musl CI budget (12 GiB RAM, two compile jobs) and substantial free disk space. The native recipe uses `LLVM_BUILD_LLVM_DYLIB=ON` with `BUILD_SHARED_LIBS=OFF`: LLVM rejects `LLVM_LINK_LLVM_DYLIB=ON` together with shared component libraries. The native development recipe limits targets to X86/AArch64; the musl release script builds all targets and selects specific LLVM tools/tests.

## Linux glibc

Run on a native Linux x86_64 glibc build host (Ubuntu 24.04 is the project CI
baseline). Install the prerequisites above. This native recipe uses the host
compiler and libraries; it does not apply the musl-only patches or emit a
portable/manylinux wheel.

```bash
cmake -S llvm -B build-glibc -G Ninja \
  -DCMAKE_BUILD_TYPE=Release -DCMAKE_POLICY_VERSION_MINIMUM=3.5 \
  -DCMAKE_INSTALL_PREFIX="$PWD/prefix-glibc" -DCMAKE_INSTALL_LIBDIR=lib \
  -DBUILD_SHARED_LIBS=OFF \
  -DLLVM_BUILD_LLVM_DYLIB=ON -DLLVM_LINK_LLVM_DYLIB=ON -DLLVM_TARGETS_TO_BUILD="X86;AArch64" -DLLVM_ENABLE_RTTI=ON -DLLVM_ENABLE_EH=ON -DLLVM_BUILD_TESTS=ON -DLLVM_INCLUDE_BENCHMARKS=OFF
cmake --build build-glibc --parallel 2
cmake --build build-glibc --target ADTTests SupportTests --parallel 2
./build-glibc/unittests/ADT/ADTTests
./build-glibc/unittests/Support/SupportTests
cmake --install build-glibc
```

## Linux musl: reproduce the Release

The authoritative pipeline is [musl-release.yml](.github/workflows/musl-release.yml),
with [build.sh](ci/musl/build.sh) as its local entry point. Run from the checked-out
repository root on a Linux x86_64 Docker host. Building requires network access
for pinned sources and package downloads; the output directory must be fresh.

```bash
REPRO_IMAGE='python:3.13-alpine3.23@sha256:75f27d686432419c9d42420b2b9ef605868c7a0682a6be10a6601fad46c2df01'
REPRO_WORK="$(mktemp -d "${TMPDIR:-/tmp}/llvm-project-musl.XXXXXXXX")"
docker run --rm --platform linux/amd64 --cpus=2 --memory=12g --memory-swap=12g --pids-limit=1024 \
  --mount "type=bind,src=$PWD,dst=/src,readonly" \
  --mount "type=bind,src=$REPRO_WORK,dst=/work" \
  "$REPRO_IMAGE" sh /src/ci/musl/build.sh
```

Repeat the published relocation/install probe in a clean container without network:

```bash
docker run --rm --platform linux/amd64 --network none \
  --mount "type=bind,src=$PWD,dst=/src,readonly" \
  --mount "type=bind,src=$REPRO_WORK,dst=/work" \
  "$REPRO_IMAGE" sh /src/ci/musl/clean.sh
```

Outputs are in `$REPRO_WORK/dist/`; build/test logs and package inventories are
in `$REPRO_WORK/logs/`. Retain `build-manifest.json` and `SHA256SUMS` alongside:

- `llvm-21.1.2-musl-x86_64-prefix.tar.gz`

```bash
(cd "$REPRO_WORK/dist" && sha256sum -c SHA256SUMS)
```

Repository-local input/metadata manifests: [`project.json`](ci/musl/project.json).

The pinned Python/Alpine image does not freeze every subsequently installed APK
or pip package. Preserve the emitted package inventory; the result is a musl
build, not a completely static application or a bit-for-bit reproducibility claim.

## macOS / macosx

Use a fresh checkout on Apple Silicon, Xcode Command Line Tools and native arm64
versions of the prerequisites. Do not reuse Linux build directories or `$ORIGIN`
RPATHs. The following is a source-development recipe; it is not the macOS installer
release recipe or a universal/x86_64 qualification.

```bash
cmake -S llvm -B build-macos -G Ninja \
  -DCMAKE_BUILD_TYPE=Release -DCMAKE_POLICY_VERSION_MINIMUM=3.5 \
  -DCMAKE_INSTALL_PREFIX="$PWD/prefix-macos" -DCMAKE_INSTALL_LIBDIR=lib \
  -DBUILD_SHARED_LIBS=OFF -DCMAKE_OSX_ARCHITECTURES=arm64 \
  -DLLVM_BUILD_LLVM_DYLIB=ON -DLLVM_LINK_LLVM_DYLIB=ON -DLLVM_TARGETS_TO_BUILD="X86;AArch64" -DLLVM_ENABLE_RTTI=ON -DLLVM_ENABLE_EH=ON -DLLVM_BUILD_TESTS=ON -DLLVM_INCLUDE_BENCHMARKS=OFF
cmake --build build-macos --parallel 2
cmake --build build-macos --target ADTTests SupportTests --parallel 2
./build-macos/unittests/ADT/ADTTests
./build-macos/unittests/Support/SupportTests
cmake --install build-macos
```

This fork’s musl Release is not used as a macOS binary dependency. Native builds here are optional development tools/libraries; the installer uses its locked macOS wheel or bundled/system library set.

## Run the same build on GitHub

A manual dispatch builds/tests artifacts without publishing. Select the immutable
release tag to reproduce its scripts (GitHub CLI and workflow permission required):

```bash
gh workflow run musl-release.yml --repo insightos-community/llvm-project --ref musl-v21.1.2-1
gh run list --repo insightos-community/llvm-project --workflow musl-release.yml --limit 5
# Set REPRO_RUN_ID to the run ID printed above.
gh run watch "$REPRO_RUN_ID" --repo insightos-community/llvm-project --exit-status
gh run download "$REPRO_RUN_ID" --repo insightos-community/llvm-project --name musl-dist --dir downloaded-dist
```

## Reproduction evidence

Build in a fresh checkout and a separate output directory for each ABI. Preserve
source commits, compiler/tool versions, dependency locks, package inventories and
test logs. Fixed source revisions and a container digest reproduce the recipe;
unlocked OS packages, runner images, timestamps and build tools can still change
archive bytes. Compare a downloaded release against its published `SHA256SUMS`;
do not expect a local rebuild to have the same digest.

See the [complete installer and repository index](https://github.com/insightos-community/quick-start/blob/main/README.build.md) for assembly order,
platform locks and end-to-end validation. Local build commands do not publish a
Release. Publishing requires repository write access and a new version tag;
existing release tags/assets should not be replaced.
