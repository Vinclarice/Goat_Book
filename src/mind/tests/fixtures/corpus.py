"""Synthetic note corpus for evaluating the dormant-thread detector.

All entries are fictional, written for an invented person. Nothing here refers to
a real individual. The corpus is deliberately mostly mundane: errands, logistics
and unremarkable observations, with a small number of genuine dormant threads
buried in it and a set of near-miss traps.

Import-safe: no I/O, no framework imports, stdlib ``dataclasses`` only.

Conventions
-----------
* ``CORPUS`` is in chronological order.
* ``TRUE_PAIRS`` / ``FALSE_PAIRS`` are ``(new_note_key, other_key, why)`` with the
  *newer* note first, mirroring how the detector is called (a note is captured,
  the detector looks backwards).
* Every entry's ``note`` field says why the entry exists in the fixture.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Entry:
    key: str          # short stable slug, e.g. "mondly-evening-2019"
    date: str         # ISO date "YYYY-MM-DD"
    body: str         # the note text
    note: str = ""    # why this entry exists in the fixture (for the test reader)


CORPUS: list[Entry] = [
    # ---------------------------------------------------------------- 2018
    Entry(
        key="scanner-jam-2018",
        date="2018-04-03",
        body=(
            "third time this month the scanner utility has died halfway through a batch. "
            "lost the whole run of grandad's letters out of the shoebox, 40-odd pages, and "
            "it doesn't even keep the ones it already did. spent the evening re-feeding "
            "them one at a time. there has to be a way of doing this that doesn't involve "
            "that software at all. a stand and the phone camera maybe"
        ),
        note="true pair with receipts-again-2025 (same tool frustration, 7 years apart)",
    ),
    Entry(
        key="dentist-logistics-2018",
        date="2018-04-05",
        body="Dentist Tue 17th, 8:40am. The practice on Wren St, not the old one. Bring the referral letter.",
        note="pure logistics filler",
    ),
    Entry(
        key="shed-key-2018",
        date="2018-04-19",
        body="shed key lives in the blue tin on the shelf by the boiler",
        note="one-line filler",
    ),
    Entry(
        key="manager-advice-2018",
        date="2018-06-21",
        body=(
            "R.'s last day. She was my manager for a bit over two years and at lunch she "
            "said the thing she regretted most in twenty years was taking the job that "
            "moved her out of the room where the actual work got done. Said you don't "
            "notice the trade for about a year, because at first it just feels like being "
            "trusted, and then one day you realise you can't speak about the work in any "
            "detail any more and there is no route back that doesn't look like a demotion. "
            "She wasn't being bitter about it, she said it more like a weather report. "
            "Writing it down because I know I'll remember the gist wrong and I think she "
            "meant it as a favour."
        ),
        note="true pair with team-lead-offer-2023 (advice that becomes relevant 5 years later)",
    ),
    Entry(
        key="train-delay-thought-2018",
        date="2018-09-02",
        body=(
            "Forty minutes on a stopped train outside Didcot and it was the calmest I've "
            "been all week. Nothing expected of me and nothing I could do. Suspicious that "
            "the only rest I get is rest that's imposed on me."
        ),
        note="filler reflective note",
    ),
    Entry(
        key="hardware-store-book-2018",
        date="2018-11-27",
        body=(
            "Twenty minutes waiting for a key to be cut and I ended up going through the "
            "drawers of fasteners at the back, the ones with the labels written by hand and "
            "corrected twice. Here is an idea and I think it's a real one rather than the "
            "usual kind. You could describe a whole town through what its ironmonger keeps "
            "in stock, and better than that, through what it has stopped keeping. Chimney "
            "brushes gone. Whole wall of pond liner that wasn't there five years ago. Half "
            "an aisle of the little brackets that only fit one make of window nobody "
            "installs any more, still there because a dozen houses on the same street have "
            "them. That's a portrait of a place without a single interview in it. Objects "
            "as census. I don't know what shape it takes, probably chapters by aisle, and I "
            "don't know if it's mine to write, but I keep thinking about it in the car."
        ),
        note="true pair with shop-closing-2022 (project idea returned to)",
    ),
    Entry(
        key="christmas-list-2018",
        date="2018-12-15",
        body=(
            "sprouts, chestnuts, the good butter, two bottles of the red H. likes, batteries "
            "(AA and the little round ones for the scales), wrapping paper, tape — we always "
            "forget tape"
        ),
        note="pure logistics filler (shopping list)",
    ),

    # ---------------------------------------------------------------- 2019
    Entry(
        key="mondly-evening-2019",
        date="2019-03-14",
        body=(
            "Paid for the whole year on the app, so that's committed. Plan: fifteen minutes "
            "after dinner before the telly goes on. The actual reason, which I don't say out "
            "loud, is that I've now sat through four Christmases at H.'s parents' being "
            "smiled at by people who are being kind to me in words I can't hold up my end "
            "of, and it has started to feel rude rather than shy."
        ),
        note="true pair with silent-dinner-2024 (recurring deferred intention)",
    ),
    Entry(
        key="spring-closet-2019",
        date="2019-03-30",
        body=(
            "cleared the hall cupboard. four bags for the charity shop, one bag of things I "
            "put back for no reason i could defend"
        ),
        note="filler",
    ),
    Entry(
        key="cello-neighbor-2019",
        date="2019-05-09",
        body=(
            "The woman in 4B knocked round to say our radiator is knocking through her "
            "floor at night. Very decent about it. She's the one who practises the same "
            "eight bars every Sunday morning — turns out she did that for a living, most of "
            "her working life in an orchestra in France, and teaches a bit now. Said the "
            "knocking doesn't bother her especially, she just wanted us to know before it "
            "got worse."
        ),
        note="true pair with recital-2025 (same person, described differently, no shared name)",
    ),
    Entry(
        key="half-marathon-2019",
        date="2019-06-08",
        body=(
            "Six weeks out. 16k on the canal path at a slower pace than I wanted and the "
            "right knee grumbled for the last three. The plan says keep the long run easy "
            "and I keep turning it into a test of something. Slow down. Finish. That's the "
            "whole job."
        ),
        note="vocabulary trap for running-the-standup-2024 ('running' as exercise)",
    ),
    Entry(
        key="left-hand-tingle-2019",
        date="2019-08-05",
        body=(
            "woke up twice with the left hand completely dead — had to hang it off the side "
            "of the bed and shake it out. gone in a minute or two. almost certainly just the "
            "way i sleep with the arm folded under the pillow"
        ),
        note="true pair with grip-jar-2023 (same symptom noted twice, ~4 years apart)",
    ),
    Entry(
        key="phone-callback-2019",
        date="2019-08-22",
        body="call the garage back — 0117 496 2288, ask for Dean. quote is front pads only, not discs.",
        note="pure logistics filler (phone number to call back)",
    ),
    Entry(
        key="long-reflection-work-2019",
        date="2019-10-13",
        body=(
            "Seven years in this city and I still catch myself talking about it as somewhere "
            "I'm currently living. Everything here is provisional in a way I've stopped "
            "noticing. The flat is furnished with things that were meant to do for a year. "
            "I know two people well and about forty people enough to nod at. When my cousin "
            "asked at the weekend whether we'd stay I heard myself say probably not, in a "
            "tone that surprised me, because nothing about the last three years suggests "
            "we're going anywhere. I think I keep the provisional feeling on purpose. If "
            "it's temporary then none of the choices are real choices and nothing has been "
            "decided by default. Which is obviously nonsense, because seven years is seven "
            "years whatever I call it, and the things I've deferred have been deferred in "
            "real time. The one-year sofa is now a five-year sofa and it is not going to "
            "improve. Either I should treat this as the place I live or actually make a plan "
            "with a date on it, and I notice I would rather write about the choice than make "
            "it, which is probably the most honest sentence in this entry."
        ),
        note="long reflective filler; deliberately near several themes without matching one",
    ),
    Entry(
        key="flu-shot-2019",
        date="2019-11-02",
        body="Flu jab: pharmacy on Colston, walk-in Sat before 12. Take the card.",
        note="pure logistics filler",
    ),

    # ---------------------------------------------------------------- 2020
    Entry(
        key="sourdough-2020",
        date="2020-05-17",
        body=(
            "starter is finally lively. second loaf was edible, third one went flat in the "
            "oven. too wet i think, or i knocked all the air out getting it off the peel"
        ),
        note="filler",
    ),
    Entry(
        key="desk-chair-2020",
        date="2020-06-02",
        body="the kitchen chair is not a desk chair. lower back by 3pm every day.",
        note="one-line filler",
    ),
    Entry(
        key="long-reflection-solitude-2020",
        date="2020-08-09",
        body=(
            "Five months of mostly our own company and the strange discovery is that I "
            "haven't minded it nearly as much as I expected to, and that this is slightly "
            "embarrassing to admit to people who have found it hard. What I've missed is not "
            "company exactly but incidental company. The queue. Overhearing. Being one of "
            "forty people in a room paying attention to the same thing. I've had plenty of "
            "conversation and almost no ambient life, and it turns out the ambient part was "
            "doing something I never gave it credit for — it made the day feel populated "
            "without asking anything of me. The friendships I actually maintain have come "
            "down to about four people and I don't think that's a pandemic number, I think "
            "that's the real number and the pandemic just took away the scenery that made it "
            "look bigger. Not sure what to do with that. Probably nothing, probably it's fine, "
            "but I'd like to have noticed it on purpose rather than by having it pointed out "
            "to me by circumstance."
        ),
        note="long reflective filler",
    ),
    Entry(
        key="bike-tuneup-2020",
        date="2020-10-11",
        body=(
            "new chain, new bar tape, back brake bled. rides like a different bike. the man "
            "in the shop says the bottom bracket has a season left in it at most"
        ),
        note="filler; mild vocabulary overlap with grip-jar-2023 (bars, riding)",
    ),
    Entry(
        key="plumber-quote-2020",
        date="2020-11-30",
        body="Plumber coming Thu 10th between 8 and 12. £180 quoted for the valve and the airing cupboard.",
        note="pure logistics filler",
    ),

    # ---------------------------------------------------------------- 2021
    Entry(
        key="espresso-pressure-2021",
        date="2021-02-14",
        body=(
            "machine is pulling shots in about twelve seconds, so there's no pressure "
            "building at all. ground finer, tamped harder, still runs straight through. "
            "either the basket is shot or water is getting past somewhere it shouldn't. "
            "descale is overdue anyway. nine bar is apparently the number you want"
        ),
        note="vocabulary trap for boiler-pressure-2023 (pressure/water/bar, unrelated topic)",
    ),
    Entry(
        key="app-restart-2021",
        date="2021-04-06",
        body=(
            "reinstalled it, day 6. mostly food and animals so far. fifteen minutes at lunch "
            "seems to stick better than after dinner did"
        ),
        note="false pair for silent-dinner-2024: already-obvious mid-chain link, not a dormant recovery",
    ),
    Entry(
        key="evening-routine-2021",
        date="2021-05-23",
        body=(
            "new rule: no screens for the last fifteen minutes before bed, book instead. "
            "three nights in and it's the fifteen minutes of the day I look forward to. the "
            "hour after dinner is still a write-off"
        ),
        note="vocabulary trap for mondly-evening-2019 (fifteen minutes/after dinner/before bed)",
    ),
    Entry(
        key="kesslers-errand-2021",
        date="2021-07-02",
        body="kessler's: return the unused drill bits, 2 keys cut, picture hooks (small brass ones)",
        note="errand trap for shop-closing-2022 (shares the shop name, no substance)",
    ),
    Entry(
        key="wedding-logistics-2021",
        date="2021-09-11",
        body=(
            "Train 9:42 from Temple Meads, changes at Newport. Hotel booked under H.'s name, "
            "check-in after 3. Suit needs the trousers taken up before then."
        ),
        note="pure logistics filler",
    ),
    Entry(
        key="long-reflection-attention-2021",
        date="2021-10-30",
        body=(
            "Counted it honestly this week: eleven books started this year, two finished, and "
            "both of those on holiday. It isn't that I've stopped enjoying reading, it's that "
            "I've stopped being able to stay in one place for the length of a chapter without "
            "the feeling that something is being neglected elsewhere. The phone is the obvious "
            "culprit and I don't think it's the whole story. I read all day, just in fragments "
            "and always in a slightly defensive posture, skimming for whether this is the thing "
            "I need. A book asks you to accept that you don't know yet why you're being told "
            "this, which is exactly the tolerance I seem to have spent. What worked on holiday "
            "was boredom plus no signal, which is not a plan, it's a location."
        ),
        note="long reflective filler",
    ),

    # ---------------------------------------------------------------- 2022
    Entry(
        key="sleep-schedule-2022",
        date="2022-01-09",
        body=(
            "Third week of waking at half four and lying there until six doing arithmetic "
            "about how much sleep I'm still going to get. Going to try a fixed wake time, "
            "6:15 every day including Sunday, and get up rather than negotiate."
        ),
        note="false pair with coffee-cutoff-2022: genuinely related but only 18 days apart",
    ),
    Entry(
        key="coffee-cutoff-2022",
        date="2022-01-27",
        body=(
            "no coffee after eleven for nine days now. going off easier, still surfacing "
            "around five but getting back down most nights. the 6:15 thing is holding, "
            "barely, and only because getting up is less awful than the arithmetic"
        ),
        note="false pair with sleep-schedule-2022: correct connection, wrong detector (not dormant)",
    ),
    Entry(
        key="shop-closing-2022",
        date="2022-07-30",
        body=(
            "Kessler's is going at the end of August. Fifty-one years, and the sign in the "
            "window is A4 and printed off a computer. Went in and there was already tape "
            "across half the shelves. I took photographs of the drawer labels, the "
            "hand-lettered ones, and of the wall of brackets nobody has asked for since about "
            "1998, and the lad clearing up looked at me like I was a bit odd, which fair "
            "enough. Everything's going to a clearance firm in Swindon. I have been circling "
            "the same thing for years without doing anything about it and this feels like the "
            "last time I'll be able to look at it properly."
        ),
        note="true pair with hardware-store-book-2018; also false pair with kesslers-errand-2021",
    ),
    Entry(
        key="new-glasses-2022",
        date="2022-08-14",
        body="new prescription, ready Fri after 2. Kept the old pair for the shed.",
        note="pure logistics filler",
    ),
    Entry(
        key="dry-cleaning-2022",
        date="2022-09-06",
        body="pick up the dry cleaning. stamps.",
        note="one-line errand filler",
    ),
    Entry(
        key="rent-increase-2022",
        date="2022-11-19",
        body=(
            "Letter says £95 more from January. Not outrageous for the area and still "
            "annoying, mostly because it arrives as information rather than a conversation. "
            "Worth pricing up what else is going in the two streets either side before we "
            "just sign it."
        ),
        note="filler",
    ),

    # ---------------------------------------------------------------- 2023
    Entry(
        key="grip-jar-2023",
        date="2023-06-11",
        body=(
            "Dropped a jar of olives on the kitchen floor — just didn't have hold of it, no "
            "warning. Been noticing the pad of the left palm under the thumb goes sort of "
            "muffled, worst on long rides where I'm leaning on the bars, and for an hour "
            "after. Fine by the afternoon. Might mention it at the check-up in September if "
            "I remember, which historically I don't."
        ),
        note="true pair with left-hand-tingle-2019 (same symptom, different words)",
    ),
    Entry(
        key="library-card-2023",
        date="2023-06-28",
        body="renew the library card. the book on hold expires thursday.",
        note="errand trap for hardware-store-book-2018 (shares 'book', no substance)",
    ),
    Entry(
        key="team-lead-offer-2023",
        date="2023-09-18",
        body=(
            "K. has offered me the lead role for the platform group and I said I'd think "
            "about it, which everyone read as yes. Two weeks of shadowing so far. The "
            "calendar is now about four hours a day of other people's decisions, and I "
            "haven't had an editor open since Tuesday, and nobody has noticed or minded, "
            "which is the part I keep turning over. It's more money, it's obviously the next "
            "step, three people congratulated me before I'd answered. And I can't work out "
            "whether the hesitation is cowardice or information. Need to give K. an answer "
            "by the 6th."
        ),
        note="true pair with manager-advice-2018 (old advice becoming applicable)",
    ),
    Entry(
        key="boiler-pressure-2023",
        date="2023-10-08",
        body=(
            "Boiler pressure down to 0.6 again, topped it back up to 1.5 on the filling "
            "loop. Third time since spring, so water is leaving the system somewhere and I "
            "can't see where. Bled the upstairs radiators, one was all air. If it drops "
            "again before Christmas I'm calling someone instead of doing this."
        ),
        note="vocabulary trap with espresso-pressure-2021 (pressure/water/bar, unrelated)",
    ),
    Entry(
        key="long-reflection-friendship-2023",
        date="2023-12-03",
        body=(
            "Ran into D. outside the chemist and we did the whole thing — great to see you, "
            "we should do something proper, I'll message you — and both of us knew neither of "
            "us would. Fifteen years ago he was in this kitchen twice a week. Nothing "
            "happened. There was no falling out to point at, which somehow makes it worse "
            "than if there had been, because it means the whole thing was held up by "
            "proximity and shared timetables and when those went the rest went with them. "
            "The uncomfortable bit is that I've been treating friendship as something that "
            "either survives on its own or doesn't, as if maintenance were a bit needy, when "
            "in fact everyone I'm still close to is someone who was willing to be the one "
            "who texts first. I'm not that person and I've been calling it not wanting to "
            "impose. I did message him, in the end, three days later, and he replied within "
            "the hour, which rather settles the question of whether the reluctance was ever "
            "mutual."
        ),
        note="long reflective filler",
    ),

    # ---------------------------------------------------------------- 2024
    Entry(
        key="running-the-standup-2024",
        date="2024-03-07",
        body=(
            "I am running the Thursday standup badly. Twenty-two minutes for six people and "
            "over half of that was me talking. Next week: hard stop at fifteen, one question "
            "each, take the long conversations off the call. Set the pace and then get out "
            "of the way."
        ),
        note="homonym trap for half-marathon-2019 ('running' a meeting, shared pace/long/minutes)",
    ),
    Entry(
        key="tomato-seedlings-2024",
        date="2024-04-21",
        body=(
            "seedlings on the bathroom windowsill, leggy already. potted on the eight best "
            "ones, gave four to the neighbours. sungold and the beefsteak ones from last year's "
            "seed"
        ),
        note="filler",
    ),
    Entry(
        key="silent-dinner-2024",
        date="2024-11-02",
        body=(
            "Lunch at H.'s parents' and I understood maybe one word in nine, and only the "
            "food ones. Sat there for three hours doing the face — attentive, agreeable, "
            "completely absent. H.'s mother did the thing where she translates the punchline "
            "for me afterwards, which is the kindest possible version of being handed a "
            "summary of a room you were sitting in. Nobody minds. That's what's actually "
            "wrong with it: nobody has ever minded, so there has never been a deadline, and "
            "I have now been meaning to fix this for the entire time I've known them. Three "
            "different things paid for over the years and none of them used past February. "
            "The person I want to talk to is her grandmother, who is ninety-one, and that is "
            "the part of this that has a clock on it. She keeps offering me the small plums "
            "from the garden and saying something I can tell is a joke about them, and every "
            "time I laugh at a shape I can't hear the inside of."
        ),
        note="true pair with mondly-evening-2019; false pair with app-restart-2021",
    ),
    Entry(
        key="car-service-2024",
        date="2024-12-04",
        body="Service + MOT booked 19th, drop off 8am. They'll ring about the rear tyres.",
        note="pure logistics filler",
    ),

    # ---------------------------------------------------------------- 2025
    Entry(
        key="recital-2025",
        date="2025-01-19",
        body=(
            "Marguerite from upstairs is playing at St Aldhelm's on the 8th and pressed two "
            "tickets on us in the stairwell, wouldn't hear about paying. She's the one with "
            "the tabby that sleeps on the third landing. Said she was in Lyon for "
            "twenty-two years before she came back to look after her mother. I had genuinely "
            "no idea she'd done it professionally."
        ),
        note="true pair with cello-neighbor-2019 (same neighbour, different description)",
    ),
    Entry(
        key="receipts-again-2025",
        date="2025-03-22",
        body=(
            "Lost most of Saturday to the flatbed. Sixty-odd receipts for the accountant, it "
            "gave up somewhere around thirty-five and kept none of them. I have now had this "
            "exact afternoon four or five times, and every time I decide never again and then "
            "do it again eighteen months later because the machine is sitting right there. "
            "Ordered a copy stand and a phone bracket, £22. Even if the pictures are worse it "
            "will be finished."
        ),
        note="true pair with scanner-jam-2018 (same tool frustration, 7 years apart)",
    ),
    Entry(
        key="shoulder-ache-2025",
        date="2025-05-30",
        body=(
            "right shoulder aching since painting the hall ceiling saturday. worse reaching "
            "behind me for the seatbelt. ibuprofen and it's already better than it was tuesday"
        ),
        note="near-miss health trap for grip-jar-2023 (different limb, obvious cause, resolving)",
    ),
    Entry(
        key="long-reflection-notes-2025",
        date="2025-09-12",
        body=(
            "Went looking for one thing in the old notes and lost an hour. What struck me "
            "wasn't the forgotten stuff, it was how many of the same intentions turn up in "
            "different handwriting years apart, each one written as though it were the first "
            "time I'd thought of it. The same three or four things, phrased slightly better "
            "each time, never done. I don't think writing them down has helped at all in the "
            "way I assumed it would; it mostly gave me somewhere to put the intention so I "
            "could stop carrying it. The useful version of this system would not be a better "
            "search box, it would be something that walked up and said: you have said this "
            "before, in 2019, and here is what you said then."
        ),
        note="long reflective filler; meta but must not be paired with any specific thread",
    ),

    # ---------------------------------------------------------------- 2026
    Entry(
        key="spare-keys-2026",
        date="2026-02-03",
        body="get two spare keys cut for H.'s brother before the 14th",
        note="one-line errand filler",
    ),
]


# (new_note_key, should_surface_key, why) — the detector SHOULD connect these
TRUE_PAIRS: list[tuple[str, str, str]] = [
    (
        "silent-dinner-2024",
        "mondly-evening-2019",
        "Same deferred intention to learn the family's language, 5y7m apart; the old note "
        "names the app and the schedule, the new one never does — the shared thing is the "
        "embarrassment at family meals.",
    ),
    (
        "team-lead-offer-2023",
        "manager-advice-2018",
        "Advice recorded five years earlier about the promotion that removes you from the "
        "work; the new note describes exactly that situation without quoting or referencing "
        "the advice.",
    ),
    (
        "grip-jar-2023",
        "left-hand-tingle-2019",
        "Same left-hand numbness noted twice, ~3y10m apart, described in different words "
        "(hand 'dead' overnight vs palm 'muffled' under load) and dismissed both times.",
    ),
    (
        "shop-closing-2022",
        "hardware-store-book-2018",
        "The ironmonger-as-portrait-of-a-town idea, 3y8m later; the new note says 'circling "
        "the same thing for years' without saying what the thing is or using the word book.",
    ),
    (
        "recital-2025",
        "cello-neighbor-2019",
        "Same neighbour under two different descriptions (the woman in 4B who practises "
        "Sundays and played in a French orchestra / Marguerite from upstairs with the tabby "
        "who was in Lyon), 5y8m apart, no shared name.",
    ),
    (
        "receipts-again-2025",
        "scanner-jam-2018",
        "Same recurring frustration with the same scanner, 7 years apart, ending in the same "
        "abandoned resolution (phone camera on a stand).",
    ),
]

# (new_note_key, must_not_surface_key, why) — plausible-looking but wrong
FALSE_PAIRS: list[tuple[str, str, str]] = [
    (
        "boiler-pressure-2023",
        "espresso-pressure-2021",
        "Heavy shared vocabulary (pressure, water, bar, topping up, something leaking where "
        "it shouldn't) across two completely unrelated domestic problems.",
    ),
    (
        "running-the-standup-2024",
        "half-marathon-2019",
        "Word-sense trap: 'running' a meeting vs running as exercise, plus shared pace / long "
        "/ slow down / minutes vocabulary.",
    ),
    (
        "library-card-2023",
        "hardware-store-book-2018",
        "A one-line errand sharing only the word 'book' with a substantial project note; "
        "surfacing errands against reflections is the failure mode that makes the detector "
        "useless.",
    ),
    (
        "shop-closing-2022",
        "kesslers-errand-2021",
        "Strongest literal overlap in the corpus (the shop name) but the older note is a "
        "13-month-old errand with no content — neither dormant nor meaningful.",
    ),
    (
        "coffee-cutoff-2022",
        "sleep-schedule-2022",
        "Genuinely the same thread and correctly connected in general, but only 18 days "
        "apart — recent continuation, not a dormant thread, so out of scope for this detector.",
    ),
    (
        "silent-dinner-2024",
        "app-restart-2021",
        "Relates to a thread that is already obviously linked: the 2021 restart is a visible "
        "mid-chain repetition and surfacing it adds nothing over the 2019 origin note.",
    ),
    (
        "evening-routine-2021",
        "mondly-evening-2019",
        "Vocabulary trap: fifteen minutes, after dinner, before bed, screens/book — the two "
        "notes share the shape of a small evening habit and nothing else.",
    ),
    (
        "shoulder-ache-2025",
        "grip-jar-2023",
        "Near-miss health match: both are minor upper-limb complaints, but different side, "
        "obvious mechanical cause and already resolving — not a recurrence of the hand "
        "symptom.",
    ),
]


# Fixture counts: 46 entries, 6 true pairs, 8 false pairs.
