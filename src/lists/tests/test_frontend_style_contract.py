import re

from django.conf import settings
from django.test import SimpleTestCase

FRONTEND_SRC = settings.BASE_DIR.parent / "frontend" / "src"
TAILWIND_CSS = FRONTEND_SRC / "app" / "tailwind.css"


def _components():
    return list(FRONTEND_SRC.rglob("*.tsx"))


def _css_modules():
    return list(FRONTEND_SRC.rglob("*.module.css"))


class RetiredStyleClassTest(SimpleTestCase):
    """`visually-hidden` came from Bootstrap and left with it.

    Retiring `site.css` took `bootstrap-utilities.css` with it, and that
    file was the only place `.visually-hidden` was ever defined. The class
    name kept working in the sense that it kept compiling -- an undefined
    class is not an error, it is simply no styling -- so thirteen labels
    that exist only for screen readers began rendering as visible page
    text on the Agenda, Area and Archive screens, and every test stayed
    green because assertions look for the copy they expect rather than the
    copy that should not be showing.

    Tailwind's `sr-only` is the replacement, and the newer routes already
    use it. A static sweep rather than a rendered check because jsdom
    applies no stylesheet, so a component test cannot tell the two apart --
    the only other place this is observable is a real browser.
    """

    def test_no_component_uses_the_retired_visually_hidden_class(self):
        offenders = []
        for path in _components():
            for number, line in enumerate(
                path.read_text(encoding="utf-8").splitlines(), start=1
            ):
                if "visually-hidden" in line:
                    offenders.append(f"{path.name}:{number}")

        self.assertEqual(
            offenders,
            [],
            "visually-hidden is undefined since Bootstrap was retired, so "
            "these render as visible text -- use Tailwind's sr-only.",
        )

    def test_the_sweep_actually_reaches_the_components(self):
        # A positive control: an empty file list would make the check above
        # pass forever, and silently, if the layout ever moves.
        self.assertGreater(len(_components()), 20)


class CssModuleTokenTest(SimpleTestCase):
    """A CSS module may only name custom properties that `@theme` defines.

    Nothing type-checks CSS, and an unresolvable `var()` does not fall back
    to anything -- it invalidates the whole declaration. So when the theme
    moved to Tailwind v4 and its tokens gained their `--color-` prefix,
    `sidenav.module.css` kept asking for `--border`, `--text`, `--accent`
    and `--muted-foreground`, and silently lost its right border, its hover
    feedback and its active-page highlight. The nav was distinguishing the
    current page by font weight alone.

    This sweep is what makes the next rename fail loudly. It is deliberately
    strict about fallbacks: `var(--warn, #f4c98a)` did keep rendering, but
    it rendered a colour no stylesheet had chosen since `site.css` -- which
    used `#f08a8a` for the same overdue count -- so a working fallback is
    not evidence that the token reference is right.
    """

    def _defined_tokens(self):
        css = TAILWIND_CSS.read_text(encoding="utf-8")
        theme = re.search(r"@theme\s*\{(.*?)\n\}", css, re.DOTALL)
        self.assertIsNotNone(theme, f"No @theme block found in {TAILWIND_CSS}")
        return set(re.findall(r"(--[\w-]+)\s*:", theme.group(1)))

    def test_css_modules_only_reference_tokens_the_theme_defines(self):
        defined = self._defined_tokens()

        offenders = []
        for path in _css_modules():
            for number, line in enumerate(
                path.read_text(encoding="utf-8").splitlines(), start=1
            ):
                for name in re.findall(r"var\(\s*(--[\w-]+)", line):
                    if name not in defined:
                        offenders.append(f"{path.name}:{number} {name}")

        self.assertEqual(
            offenders,
            [],
            "An unresolvable var() drops the whole declaration silently. "
            "Use the --color-* names declared in app/tailwind.css.",
        )

    def test_the_layouts_two_breakpoints_still_describe_the_same_width(self):
        """The rail's collapse is declared twice, in two languages.

        `sidenav.module.css` collapses the rail and reveals the disclosure's
        <summary> below a width; `AppLayout.tsx` forces the disclosure open
        above one. They are the same edge seen from either side, and a
        disagreement is not cosmetic -- it leaves a band of widths where the
        summary is hidden *and* the disclosure is shut, which is B0 exactly:
        a navigation sealed inside a control with no handle.

        The comment that used to guard this said "if one moves, the other has
        to". That is a hope. This is the check.
        """
        css = (FRONTEND_SRC / "app" / "sidenav.module.css").read_text(
            encoding="utf-8"
        )
        layout = (FRONTEND_SRC / "app" / "AppLayout.tsx").read_text(encoding="utf-8")

        collapse = re.search(r"@media \(max-width:\s*([\d.]+)px\)", css)
        wide = re.search(r"\(min-width:\s*([\d.]+)px\)", layout)
        self.assertIsNotNone(collapse, "No max-width breakpoint in sidenav.module.css")
        self.assertIsNotNone(wide, "No min-width breakpoint in AppLayout.tsx")

        # Adjacent, not equal: the CSS stops one hair below where the JS
        # starts, so no width falls through both.
        self.assertLess(
            float(collapse.group(1)),
            float(wide.group(1)),
            "The CSS collapse must end below where the layout calls it wide.",
        )
        self.assertLess(
            float(wide.group(1)) - float(collapse.group(1)),
            1.0,
            "A gap wider than a pixel leaves widths where the rail is "
            "collapsed and the disclosure cannot be opened.",
        )

    def test_the_theme_block_actually_parses(self):
        # Two positive controls. An unparseable @theme would yield an empty
        # set and fail every module instead of passing them, but an empty
        # module list would pass forever -- and one known-good token proves
        # the regex is reading declarations rather than matching nothing.
        self.assertGreater(len(_css_modules()), 0)
        self.assertIn("--color-border", self._defined_tokens())
