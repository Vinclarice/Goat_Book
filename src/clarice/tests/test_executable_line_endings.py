"""Scripts a shell has to parse, checked for CRLF in the working copy.

`.gitattributes` sets `eol=lf` and explains why: *"a CRLF line ending there
breaks the shebang entirely"*. That governs what git **writes on checkout**. It
does not govern what anything else writes afterwards, and the blob stays LF
either way -- so a corrupted working copy shows nothing in `git status`, passes
review, and fails only when somebody runs the file.

**This is not hypothetical.** `infra/check-restore-integrity.sh` was written,
run successfully against a live database, then edited by a tool whose default
newline handling on Windows rewrites `\\n` as `\\r\\n`. The commit was clean
because git normalised the blob. The next person to run it from WSL got

    syntax error near unexpected token `$'{\\r''

on the first function definition -- and the documented restore workflow runs
exactly there, from WSL against the Windows checkout.

**CI cannot catch this.** A fresh Linux checkout always has LF, so this test is
green on the runner by construction. It exists to fail *locally*, on the machine
where the corruption happens and where the drill is run from.
"""
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


REPO = settings.BASE_DIR.parent


def shell_parsed_files():
    """Files a shell reads: every `infra` script, plus the two the repository
    invokes through a shebang.

    Named rather than discovered by walking, because a walk wide enough to find
    them all also reaches `node_modules`, `.venv` and Gradle's build output --
    thousands of vendored files whose line endings are not this project's
    business.
    """
    found = sorted(REPO.glob("infra/**/*.sh"))
    for named in (REPO / "src" / "manage.py", REPO / "android" / "gradlew"):
        if named.exists():
            found.append(named)
    return found


class NoCarriageReturnsTest(SimpleTestCase):
    def test_no_shell_parsed_file_has_crlf_in_the_working_copy(self):
        offenders = {}
        for path in shell_parsed_files():
            raw = path.read_bytes()
            count = raw.count(b"\r\n")
            if count:
                offenders[path.relative_to(REPO).as_posix()] = count

        self.assertEqual(
            offenders,
            {},
            "CRLF in a file a shell has to parse. The blob is fine and git "
            "shows no diff, which is why this needs its own check: re-checkout "
            "with `rm <file> && git checkout -- <file>`, and write it with "
            "newline='\\n' next time.",
        )

    def test_the_sweep_actually_finds_the_scripts(self):
        """A positive control. A glob that matched nothing would make the
        assertion above pass forever and read as coverage -- which is how
        `test_export.py`'s guard reported a complete export while a model was
        missing."""
        names = {path.name for path in shell_parsed_files()}

        self.assertIn("check-restore-integrity.sh", names)
        self.assertIn("check-backup-freshness.sh", names)
        self.assertIn("manage.py", names)
        self.assertGreaterEqual(len(shell_parsed_files()), 4)

    def test_every_file_it_checks_is_actually_readable(self):
        """The other way the sweep could pass vacuously: a path that exists but
        cannot be read would raise, not pass -- this makes that explicit rather
        than incidental."""
        for path in shell_parsed_files():
            with self.subTest(path=path.name):
                self.assertGreater(len(path.read_bytes()), 0)
