#!/usr/bin/env bash
# Double-click launcher for macOS. See README.md "Quick Start" -- the first
# time you double-click this, macOS Gatekeeper may refuse to open it because
# it's an unsigned script from the internet. That's expected, not an error:
# right-click (or Control-click) this file, choose "Open", then confirm in
# the dialog that appears. After that first time, double-clicking works
# normally.
cd "$(dirname "$0")"
exec ./run.sh
