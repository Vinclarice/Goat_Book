"""The Dockerfile's build-time environment has to be able to import settings.

`collectstatic` runs inside the image build with `DJANGO_ENVIRONMENT=production`
and a handful of placeholder credentials, which means **settings.py's production
branch executes at build time** with an environment nobody has ever tested.

It broke on the deploy of 2026-08-18. Selecting the Resend backend by default
when `DEBUG` is off, and requiring its key to be non-empty at boot, were both
deliberate — and together they meant the build step demanded a variable the
Dockerfile does not set:

    django.core.exceptions.ImproperlyConfigured:
        DJANGO_RESEND_API_KEY is required when DJANGO_EMAIL_BACKEND is 'resend'

Every suite was green. `test_mail.py` proved the settings branch resolves
correctly *given* an environment; nothing proved the environment the image
actually builds with is one of the ones that works. This is that.

**It reads the Dockerfile rather than restating it**, so the two cannot drift:
adding a required setting without adding it to the build env fails here, at the
cost of a subprocess, instead of failing a deploy after a thirteen-second image
build.
"""
import os
import pathlib
import re
import subprocess
import sys

from django.conf import settings
from django.test import SimpleTestCase


DOCKERFILE = settings.BASE_DIR.parent / "Dockerfile"


def build_time_environment():
    """The `KEY=value` assignments the image's `collectstatic` step runs with.

    Read from the `RUN` that invokes it rather than from a copy kept here.
    Raises rather than returning `{}` if the step cannot be found: a sweep that
    quietly matches nothing would make every assertion below pass while
    checking an empty environment.
    """
    text = DOCKERFILE.read_text(encoding="utf-8")
    # Join the line continuations first, so one RUN is one line to match.
    joined = re.sub(r"\\\s*\n\s*", " ", text)
    step = next(
        (line for line in joined.splitlines() if "collectstatic" in line and line.startswith("RUN")),
        None,
    )
    if step is None:
        raise AssertionError(
            "no RUN step invoking collectstatic found in the Dockerfile; "
            "this test's parser has gone stale."
        )

    pairs = re.findall(r"\b(DJANGO_[A-Z_]+|ALLOW_[A-Z_]+)=(\S+)", step)
    if not pairs:
        raise AssertionError(f"no environment assignments found in: {step!r}")
    return dict(pairs)


class TheImageCanImportSettingsTest(SimpleTestCase):
    def test_django_boots_with_exactly_the_build_environment(self):
        """The assertion the deploy needed and did not have.

        A subprocess with `env=` and nothing inherited, because inheriting this
        shell's variables is how a test like this passes on the one machine
        that happens to have the missing one set.
        """
        environment = {
            # Enough for the interpreter to start, and nothing that settings
            # reads. PATH because Windows needs it to spawn python at all.
            "PATH": os.environ.get("PATH", ""),
            "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),
            "DJANGO_SETTINGS_MODULE": "clarice.settings",
            "PYTHONPATH": str(settings.BASE_DIR),
            **build_time_environment(),
        }

        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "import django; django.setup(); "
                "from django.conf import settings; print(settings.EMAIL_BACKEND)",
            ],
            capture_output=True,
            text=True,
            env=environment,
        )

        self.assertEqual(
            result.returncode,
            0,
            "settings.py cannot be imported with the Dockerfile's build "
            f"environment, so `docker build` will fail:\n{result.stderr}",
        )

    def test_the_build_runs_as_production(self):
        """The reason this test has to exist at all. If the build ever stopped
        claiming production, settings' production branch would no longer run at
        build time and this whole class would be checking the development
        path."""
        self.assertEqual(
            build_time_environment().get("DJANGO_ENVIRONMENT"), "production"
        )

    def test_the_build_sends_no_mail(self):
        """`collectstatic` has no reason to reach a relay, and a build that
        selects a real transport needs a real credential to boot -- which is
        exactly how the 2026-08-18 deploy failed."""
        self.assertEqual(
            build_time_environment().get("DJANGO_EMAIL_BACKEND"), "console"
        )

    def test_the_parser_actually_found_the_step(self):
        """Positive control. Every assertion above reads the same dict, and a
        parser that returned an empty one would make two of them fail loudly
        but this is the one that says why."""
        found = build_time_environment()

        self.assertIn("DJANGO_SECRET_KEY", found)
        self.assertIn("DJANGO_DATABASE_URL", found)
        self.assertGreaterEqual(len(found), 4)

    def test_no_real_credential_is_baked_into_the_build(self):
        """These are placeholders and must stay placeholders. A build argument
        that became a real key would be readable in the image's history by
        anyone who pulls it."""
        for key, value in build_time_environment().items():
            if "KEY" in key or "PASSWORD" in key or "SECRET" in key:
                with self.subTest(variable=key):
                    self.assertIn("build-only", value)


class TailwindSourcesReachTheImageTest(SimpleTestCase):
    """Every `@source` Tailwind scans has to exist in the stage that builds it.

    The frontend stage copied `frontend/` and nothing else, so the globs in
    tailwind.css reaching `../../../src/...` matched an empty directory. A
    utility used *only* in a Django template therefore generated no rule --
    silently, because matching nothing is not an error to Tailwind -- and the
    class fell back to inherited colour in production while every local build,
    which has the whole tree, was correct.

    It shipped on 2026-08-18: `text-kept` and `text-released` on the landing
    page's marks rendered as body text, and the deployed tokens.css was 4kB
    smaller than the one built here. It had been true of every Django-only
    utility since the Tailwind migration; those marks were simply the first
    that nothing else in the tree also used.

    Reads both files rather than restating either, in the same spirit as the
    environment sweep above: adding an `@source` outside what the stage copies
    fails here rather than in production, where the failure mode is a page that
    renders and is wrong.
    """

    TAILWIND = settings.BASE_DIR.parent / "frontend" / "src" / "app" / "tailwind.css"

    def frontend_stage(self):
        text = DOCKERFILE.read_text(encoding="utf-8")
        start = text.index("FROM node")
        end = text.index("FROM ", start + 1)
        return text[start:end]

    def copied_roots(self):
        """The repo-relative paths the frontend stage copies in."""
        return {
            source.split("/")[0]
            for line in self.frontend_stage().splitlines()
            if line.startswith("COPY ")
            for source in line.split()[1:-1]
        }

    def external_sources(self):
        """`@source` targets that reach outside frontend/, repo-relative."""
        css = self.TAILWIND.read_text(encoding="utf-8")
        found = set()
        for raw in re.findall(r'@source\s+"([^"]+)"', css):
            if not raw.startswith(".."):
                continue
            # Relative to frontend/src/app/, which is where tailwind.css sits.
            resolved = pathlib.PurePosixPath("frontend/src/app") / raw
            parts = []
            for part in resolved.parts:
                if part == "..":
                    parts.pop()
                else:
                    parts.append(part)
            found.add(parts[0])
        return found

    def test_the_sweep_actually_finds_both_halves(self):
        # Positive controls. Either side matching nothing would make the
        # assertion below pass while comparing two empty sets.
        self.assertIn("frontend", self.copied_roots())
        self.assertTrue(self.external_sources())

    def test_every_scanned_directory_is_present_when_the_bundle_is_built(self):
        missing = self.external_sources() - self.copied_roots()

        self.assertEqual(
            missing,
            set(),
            f"tailwind.css scans {sorted(missing)}, which the Dockerfile's "
            "frontend stage does not COPY -- those utilities will be missing "
            "from the built CSS, without any error.",
        )
