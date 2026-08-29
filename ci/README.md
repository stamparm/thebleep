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

macOS provides the Darwin/BSD-derived userland here. Linux containers cover
the additional GNU, BusyBox and slim-userland variations; Docker cannot run a
FreeBSD kernel/userland faithfully on a Linux GitHub runner.
