# Runner command inventory

`command_inventory.py` records the first executable for every command on
`PATH`, then captures version/help output for a deliberately small safe
allowlist. The OS command vocabulary is different on a GitHub-hosted macOS or
Windows runner, and the hosted images change over time, so the result is
published as an artifact by the scheduled **OS command inventory** workflow.

The inventory is discovery data. It must not be copied into the hermetic
correction corpus without checking the program and wording in a real
environment first. A runner image update is evidence to inspect, not a test
failure by itself.

The scheduled run also validates a small set of output-dependent rules against
the probes while their temporary files still exist. This is a compatibility
smoke test, not a claim that every failure deserves a correction: if a selected
rule stops matching current output, the OS job fails and the captured artifact
shows the wording that changed. Ambiguous output, such as BusyBox `mv`'s
source/destination error, is intentionally left out and must continue to
abstain.

macOS provides the Darwin/BSD-derived userland here. Linux containers cover
the additional GNU, BusyBox and slim-userland variations; Docker cannot run a
FreeBSD kernel/userland faithfully on a Linux GitHub runner.
