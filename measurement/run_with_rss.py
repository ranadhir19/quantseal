#!/usr/bin/env python3
"""Run one command and record its peak child RSS.

    python3 measurement/run_with_rss.py <rss_out_file> <command> [args...]

The command's stdout/stderr pass through unchanged. After it exits, the
peak resident set size of the child (ru_maxrss, KiB on Linux) is written
to <rss_out_file>. The exit code is the command's exit code.
"""

import resource
import subprocess
import sys


def main() -> int:
    if len(sys.argv) < 3:
        print("usage: run_with_rss.py <rss_out_file> <command> [args...]",
              file=sys.stderr)
        return 2
    rss_out, cmd = sys.argv[1], sys.argv[2:]
    proc = subprocess.run(cmd)
    peak_kib = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    with open(rss_out, "w", encoding="utf-8") as fh:
        fh.write("%d\n" % peak_kib)
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
