#!/bin/sh
set -eu
exec > /work/logs/clean-install.log 2>&1
mkdir -p /opt/check /opt/runtime
tar -xzf /work/dist/*-musl-x86_64-prefix.tar.gz -C /opt/check
cp /work/runtime/* /opt/runtime/ 2>/dev/null || test -z "$(ls -A /work/runtime)"
export LD_LIBRARY_PATH=/opt/check/prefix/lib:/opt/runtime
python /src/ci/musl/smoke.py /opt/check/prefix
