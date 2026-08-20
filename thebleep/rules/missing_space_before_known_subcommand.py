# -*- encoding: utf-8 -*-

"""`ls-la` -> `ls -la`, and `gitstatus` -> `git status`. Not a guess.

The same slip as `missing_space_before_subcommand`, and the half of it that is
not a guess -- which is why it is a rule of its own, and why it answers *ahead*
of the ordinary spelling correction.

    $ ls-la
    ls-la: command not found
    $ bleep
    lsblk                    <- two edits, and it was the first suggestion

    $ gitstatus
    $ bleep
    aa-status                <- three edits

`ls -la` and `git status` were both in that list, one row down, behind an answer
nobody would ever want. `no_command` sits at priority 3000 and this used to sit
at 4000, so a three-edit neighbour beat a certainty.

What makes it a certainty rather than a guess is the remainder:

- **a flag.** `ls-la`, `du-h`, `grep-r`. Nobody has ever meant a program with a
  `-la` on the end of its name, and no spelling correction competes.
- **a subcommand the program itself admits to.** `gitstatus` is `git status`
  because git listed `status`, which is the same evidence that makes `git satus`
  a typo. `git` and `cargo` are the two programs this tool can ask; see
  `replay.DISPATCHERS`.

Everything else -- `npminstall`, `watchls` -- is a guess, stays a guess, and
stays behind `no_command` where it was. `whoiam` is why: it is two edits from
`whoami` and one insertion from `who iam`, and `whoami` is obviously what was
meant. Distance cannot tell those apart; what the remainder *is* can.

"""

from thebleep.rules.missing_space_before_subcommand import certain, split_at


def match(command):
    return bool(command.script_parts) and certain(command)


def get_new_command(command):
    return split_at(command)


# Ahead of `no_command`, which is at 3000.
priority = 2900


# The command itself is the whole question.
requires_output = False
