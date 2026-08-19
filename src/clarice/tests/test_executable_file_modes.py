"""Files invoked through a shebang, checked for the execute bit git recorded.

The sibling of `test_executable_line_endings.py`, for the other attribute this
checkout cannot carry. `core.fileMode` is `false` here, so git has no mode to
observe and records `100644` for anything new; Git Bash prints the file with a
`*` regardless, guessing from the extension; and `git status` has nothing to say
either way. The blob is wrong and every local signal agrees it is fine.

**This is not hypothetical.** All four `infra/*.sh` were recorded `100644` from
the day each was written. The backup-freshness workflow died on it -- exit 126,
`Permission denied` -- the first night its API token let it reach the script at
all, and `MIGRATION.md`'s restore drill would have failed identically at step 5,
mid-drill, with a billed scratch cluster running.

**Why nobody noticed for weeks, and the reason this test reads git rather than
the filesystem.** The production image is built by the deploy playbook from WSL
over `/mnt/c`, and that mount carries `aname=drvfs` with no `metadata` option --
so every file there reports `-rwxrwxrwx` whatever git recorded. Windows answers
much the same. `os.access(path, os.X_OK)` and `stat().st_mode` therefore report
success on the two platforms this repository is worked on, and the truth lives
only in the index. A filesystem check here would be green forever and mean
nothing.

**Unlike its sibling, this one works on CI**, because `git ls-files -s` reports
the recorded mode identically on every platform. The sibling exists to fail
locally and is green on the runner by construction; this one is the reverse of
that only in where the corruption happens, not in where it can be caught.

**What it protects that is not yet visible.** `src/manage.py` carries
`#!/usr/bin/env python` and the playbook runs it as `./manage.py migrate` in the
migration container and in three cron jobs. That works today solely because of
the drvfs behaviour above. `architecture-trajectory.md` §6 plans CI-built
immutable images; on the day one is built from a real Linux checkout, a
`100644` here stops the first thing a deploy does.
"""
import subprocess

from django.conf import settings
from django.test import SimpleTestCase

from clarice.tests.test_executable_line_endings import shell_parsed_files


REPO = settings.BASE_DIR.parent

# git's mode for a file it considers executable. The only other value it stores
# for an ordinary file is 100644, so this is a two-value question.
EXECUTABLE = "100755"


def recorded_modes():
    """What git has stored for each shebang-invoked file, as {path: mode}.

    Shelling out rather than reading `.git/index`: the index is a binary format
    with its own versions, and `ls-files -s` is the documented way to ask this
    question. Paths come back repository-relative with forward slashes on every
    platform, which is what the assertion messages want anyway.
    """
    paths = [p.relative_to(REPO).as_posix() for p in shell_parsed_files()]
    result = subprocess.run(
        ["git", "ls-files", "-s", "--", *paths],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=True,
    )
    modes = {}
    for line in result.stdout.splitlines():
        meta, path = line.split("\t", 1)
        modes[path] = meta.split()[0]
    return modes


class ShebangFilesAreExecutableTest(SimpleTestCase):
    def test_every_shebang_invoked_file_is_executable_in_git(self):
        offenders = {
            path: mode
            for path, mode in recorded_modes().items()
            if mode != EXECUTABLE
        }

        self.assertEqual(
            offenders,
            {},
            "A file the repository invokes directly is not executable in git. "
            "Nothing local will show this -- chmod does nothing while "
            "core.fileMode is false, and both Windows and WSL report the file "
            "as executable anyway. Fix it in the index: "
            "`git update-index --chmod=+x <path>`.",
        )

    def test_the_sweep_actually_finds_the_scripts(self):
        """A positive control, for the same reason the sibling carries one: a
        path list that silently matched nothing would make the assertion above
        pass forever while reading as coverage."""
        modes = recorded_modes()

        self.assertIn("src/manage.py", modes)
        self.assertIn("infra/check-restore-integrity.sh", modes)
        self.assertIn("infra/check-backup-freshness.sh", modes)
        self.assertGreaterEqual(len(modes), 4)

    def test_git_reports_a_mode_for_every_file_checked(self):
        """The other way this could pass vacuously. `ls-files` prints nothing
        for a path it does not track, so an untracked script would vanish from
        the comparison rather than fail it -- and a script nobody committed is
        exactly the one whose mode nobody set."""
        expected = {p.relative_to(REPO).as_posix() for p in shell_parsed_files()}

        self.assertEqual(set(recorded_modes()), expected)
