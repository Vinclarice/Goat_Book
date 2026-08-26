"""The write endpoint a machine calls has a ceiling — `/api/v1/capture`.

The sibling `test_unauthenticated_endpoints_are_throttled.py` names in its title,
and the premise does not stretch: capture is authenticated by token or session,
so no stranger reaches it and that file's rule has nothing to say about it.

**The argument is different, and so is the attacker.**
`security-and-resilience-plan.md` 2.3: the bearer lives ninety days in an
Android Keystore and the offline queue on the other end is *designed* to retry,
so *"a retry loop or a leaked token writes unbounded `Node` rows against a
droplet with one core and 458MB."* `architecture-trajectory.md` §6 defers broad
API rate limiting until `/api/v1/` serves somebody untrusted, and says an
individual route can meet the trigger alone. This one has, by a different route
than that section anticipated.

**The rate is chosen against what the phone actually does**, which the plan asks
for by name rather than accepting a round number. `QueueDrainer.drain()` walks
`queue.waiting()` **serially with no delay between items**, so a backlog of N
captures is N requests as fast as the round-trips allow — which means `burst` is
the number that has to cover a real backlog, and the sustained rate only ever
bites a runaway.

- **`burst=60 nodelay`** — a whole backlog delivered without one 429. The corpus
  is 47 nodes in total, so sixty queued captures is generous by a wide margin.
- **`rate=30r/m`** — half a write a second sustained. Legitimate use is bursty
  and then idle; only a loop or an abused token stays at the ceiling.

**A 429 cannot lose a capture, which is what makes this safe to add at all.**
`CaptureContract.dispositionFor` maps every unrecognised status — 429 among them
— to `RETRY_LATER`, and its comment says why: *"treating an unknown response as
rejection would discard a thought the person typed, and that is the one failure
this app exists to prevent."* The item stays in the queue with its text and its
idempotency key.

**And it cannot strand one either**, which was the thing worth checking rather
than assuming. `RETRY_LATER` charges an attempt, `CaptureQueue.DEFAULT_CEILING`
is five, and an item reaching it goes `STALLED`. But `CaptureWorker` backs off
exponentially from thirty seconds, and thirty seconds at `30r/m` replenishes
fifteen tokens — so the retry after a 429 arrives at a bucket that has refilled.
Reaching five would take five separate wake-ups all landing against a full
bucket, which is a sustained flood, which is the case this limit is for.

**Idempotency does most of the work anyway.** `/api/v1/capture` collides on
`public_id`, so the *retry* half of the plan's worry creates no rows at all. The
sustained cap is for distinct keys — abuse, or a client bug minting new ones.

**Proved by running nginx, not by reading the template** — which is what the
plan asks for and what `9eb9eea` did for the login throttle. This file can only
assert on text; the run is the evidence behind the numbers it asserts.

August 26, 2026, `nginx:alpine`, the template rendered through Jinja with both
values of `include_www_alias` and both loading clean under `nginx -t`. Then the
zone and the `limit_req` lines were lifted *out of the rendered file* rather
than retyped, and 100 rapid requests fired at them: **61 passed and 39 came
back 429.** Sixty-one is `burst` plus the one the rate itself allows, which is
nginx's documented behaviour and means a sixty-item backlog drains without a
single refusal.

**The first version of that proof was wrong in the direction that flatters.**
The stub answered with `return 200`, and every one of 200 rapid requests came
back 200 — because `return` is a *rewrite*-phase directive and short-circuits
before `limit_req` runs at preaccess. A limiter can be reported as working, and
as generous, by a harness that never reaches it. The stub serves a file now, and
the passing requests answer 405 because a POST to a static file is method-not-
allowed: an unlovely status that is itself the proof, since only a request that
got past the limiter can be refused by the content handler.
"""

import re
from pathlib import Path

from django.test import SimpleTestCase


NGINX_TEMPLATE = (
    Path(__file__).resolve().parents[3] / "infra" / "templates" / "nginx-clarice.conf.j2"
)

#: `location = /path {` — nginx's exact match, which beats every prefix and
#: regex block whatever the order. Shared in spirit with the sibling file rather
#: than imported from it: the two ask different questions of the same file, and
#: a helper that moved would silently change what both of them prove.
EXACT_LOCATION = re.compile(
    r"location\s*=\s*(?P<path>\S+)\s*\{(?P<body>[^}]*)\}", re.MULTILINE
)

CAPTURE = "/api/v1/capture"


def block_for(path):
    config = NGINX_TEMPLATE.read_text(encoding="utf-8")
    for match in EXACT_LOCATION.finditer(config):
        if match.group("path") == path:
            return match.group("body")
    return ""


class TheCaptureEndpointHasACeilingTest(SimpleTestCase):
    def test_capture_has_an_exact_match_block(self):
        """Exact, so a later prefix rule cannot shadow it. The endpoint matched
        nothing but `location /` until now."""
        self.assertNotEqual(block_for(CAPTURE), "")

    def test_that_block_actually_spends_a_rate_limit(self):
        """A `location` that exists and limits nothing is the shape this whole
        plan item is about."""
        self.assertIn("limit_req", block_for(CAPTURE))

    def test_it_answers_429_rather_than_503(self):
        """nginx's default for a refused request is 503, which
        `dispositionFor` also treats as `RETRY_LATER` — so this is about
        honesty rather than behaviour. A queue told *service unavailable* when
        the service is available and declining is a queue whose logs mislead
        whoever reads them."""
        self.assertIn("limit_req_status 429", block_for(CAPTURE))

    def test_the_burst_covers_a_real_backlog(self):
        """`QueueDrainer` is serial with no gap between items, so the burst is
        what a returning-from-offline drain spends. Below a realistic backlog
        this would 429 the phone for doing exactly what it was built to do."""
        burst = re.search(r"burst=(\d+)", block_for(CAPTURE))

        self.assertIsNotNone(burst)
        self.assertGreaterEqual(int(burst.group(1)), 60)

    def test_the_burst_is_not_delayed(self):
        """Without `nodelay` nginx *queues* the burst rather than passing it,
        spacing the phone's backlog out at the sustained rate — which turns a
        two-second drain into two minutes of held connections on a one-core
        droplet."""
        self.assertIn("nodelay", block_for(CAPTURE))

    def test_the_sustained_rate_leaves_room_for_the_retry_after_a_refusal(self):
        """The stranding check, kept as an assertion because it is the one that
        would be silently wrong. `CaptureWorker` backs off exponentially from
        thirty seconds and `CaptureQueue.DEFAULT_CEILING` is five, so the rate
        must refill at least one token inside thirty seconds -- otherwise a
        refused item meets a refusal again on every wake-up and stalls after
        five of them, which is a capture that stops retrying."""
        config = NGINX_TEMPLATE.read_text(encoding="utf-8")
        zone = re.search(
            r"limit_req_zone[^;]*zone=clarice_capture:[^;]*rate=(\d+)r/m", config
        )

        self.assertIsNotNone(zone)
        tokens_per_thirty_seconds = int(zone.group(1)) / 2
        self.assertGreaterEqual(tokens_per_thirty_seconds, 1)
