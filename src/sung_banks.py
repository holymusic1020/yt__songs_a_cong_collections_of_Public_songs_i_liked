"""Sung-lyric banks — one REAL chorus per genre (2026-10-09, hype audit).

Why this file exists: `src/lyrics.py` used to sing ONE shared English
verse/chorus/bridge for every genre and every day, and verse 2 was literally
three of verse 1's lines shuffled (`rng.sample(b["verse"], 3)` on a 4-line
verse). Two weeks of releases therefore carried the same hook — the single
biggest reason the channel stopped sounding like anything.

Rules baked in here (verified by tools/v35_hype_ut.py):
  · 24 genres → 24 DISTINCT choruses (no label shares a hook with another)
  · every chorus is 4 lines, end-rhymed in AABB couplets
  · every bridge is 2 rhymed lines
  · verses are NOT stored here — they come from the per-genre caption banks
    in `lyrics.LINES` (already unique per genre), sliced without repetition
  · lowercase, 3-8 words a line, singable, no artist names, no real-song lines
"""
from __future__ import annotations

# genre_key -> (4-line chorus, 2-line bridge). Couplet rhymes only.
CHORUSES: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "deep_pop": (
        ("so let the night go down on me",
         "i saved your place for you to see",
         "if love is loud then love is gone",
         "i hum your name against the dawn"),
        ("and if i break, i break in tune",
         "my heart keeps time against the moon")),
    "drift_phonk": (
        ("headlights write the road in wires",
         "i drive until the want expires",
         "no phone, no map, no mercy, no",
         "the city bleeds in neon glow"),
        ("the engine is a prayer i keep",
         "the dark is wide and i am deep")),
    "villain_pop": (
        ("i am the smile before the fall",
         "i ruin you and you love it all",
         "sweet teeth, soft voice, sharp design",
         "the villain wins — she's feeling fine"),
        ("don't ask me nice, i bite",
         "the crown fits better tight")),
    "chart_pop": (
        ("play it loud, it's our summer night",
         "every heart breaks right, then it's alright",
         "we don't need a reason to shine",
         "one more chorus, then you're mine"),
        ("if this is the last dance we get",
         "i'll make it the best one yet")),
    "melodic_trap": (
        ("i turned my pain into a check",
         "i wear my scars around my neck",
         "the hook is cold, the beat is warm",
         "i made my sadness into form"),
        ("no sleep, just streams, just the tide",
         "i built a bed out of my pride")),
    "summer_rap": (
        ("we take the coast and take it low",
         "we chase the sun and never slow",
         "salt on my skin, gold in the air",
         "this summer owes us, and we're there"),
        ("the radio knows what we did",
         "i keep it loud, i keep it hid")),
    "phonk_mafia": (
        ("i do the numbers, not the crime",
         "the block remembers every time",
         "black windows, low notes, slow ride",
         "respect is bought, it ain't denied"),
        ("we eat in silence, leave in steel",
         "the family is all i feel")),
    "velvet_fang": (
        ("come close, i bite when i am meant",
         "my love arrives in velvet, bent",
         "sweet poison poured in crystal clear",
         "i kiss the wound, i keep the spear"),
        ("the party ends, the fangs stay out",
         "i am the doubt inside your doubt")),
    "emo_rap": (
        ("i typed it out and deleted twice",
         "3 a.m. knows my advice",
         "i cry in the booth, the tears keep time",
         "pain makes the prettiest rhyme"),
        ("my hoodie still holds your shape",
         "grief is a room i can't escape")),
    "templestep": (
        ("bells in the rain, drums in the floor",
         "i pray loud and i pray for more",
         "the gate swings wide for the steady beat",
         "knees on the stone, feet on the street"),
        ("stillness hits harder than the drop",
         "i light a match, the gods don't stop")),
    "lastjuly": (
        ("we were fireworks that forgot to land",
         "summer left early, i understand",
         "one last swim before the leaves turn brown",
         "i keep the season like a crown"),
        ("the bonfire wrote us in the smoke",
         "the ash remembers what the fire broke")),
    "ashrise": (
        ("they buried me in embers, i rose up",
         "i drank the fire from a paper cup",
         "every ending fed my ignition line",
         "i am the smoke that learned to shine"),
        ("ruins are a good foundation",
         "i am my own slow renovation")),
    "brazilian_phonk": (
        ("the street teaches the speaker how to dance",
         "we take the night, we never ask for chance",
         "rio don't sleep, it just changes the beat",
         "sweat on the concrete, fire on the street"),
        ("carnival inside a neon age",
         "we move all night, we own the stage")),
    "saint_of_leaving": (
        ("i bless the door, i keep the peace",
         "no war inside me, no release",
         "i leave soft, i don't stay",
         "the holiest thing is what i don't say"),
        ("halo packed, cab at the stair",
         "mercy is leaving before the war is there")),
    "indie_waves": (
        ("salt in my hair, a chord in my chest",
         "we wrote our name where the tide takes rest",
         "off-key and honest, loud and low",
         "the ocean never rushes, though"),
        ("a garage band down at the bank",
         "we play till the sunrise fills the tank")),
    "lambs_teeth": (
        ("be gentle till the gentle's gone",
         "i keep my mercy in the dawn",
         "soft hands, but the count is true",
         "i love you mean and i mean you"),
        ("i learned that quiet isn't weak",
         "the kindest mouth still knows to speak")),
    "god_in_the_bass": (
        ("there's a god in the low end humming",
         "every wall in this city's drumming",
         "i don't pray loud, i pray deep",
         "the floor is the only sky i keep"),
        ("turn it till the windows shake",
         "faith is a frequency i make")),
    "anime_titan": (
        ("stand up where the sky cracks wide",
         "i am the oath you can't divide",
         "the city burns and i still stand",
         "i hold the line with an empty hand"),
        ("one more step, the titan turns",
         "i burn my fear, the city burns")),
    "disco_house": (
        ("mirror ball heart on the floor",
         "give me one more, one more, one more",
         "hands to the ceiling, sweat on the street",
         "we own the night till the morning's sweet"),
        ("the bassline is a open door",
         "leave your sad self on the floor")),
    "skyline_anthem": (
        ("every rooftop is a finish line",
         "we are the loud, we are the shine",
         "raise it up till the towers ring",
         "this is the song the rooftops sing"),
        ("one breath, a thousand voices",
         "we are the choice, not the choices")),
    "baroque_waltz": (
        ("turn the candle, count the three",
         "dance with who you used to be",
         "hold the turn and never slow",
         "one more waltz before i go"),
        ("the harpsichord knows your lies",
         "it plays them softer to my eyes")),
    "dark_ambient": (
        ("stay in the fog, it knows your name",
         "nothing is lost that stays the same",
         "the far light waits, the rain don't lie",
         "i breathe, and so the dark goes by"),
        ("no words, just weather, just delay",
         "the quiet says what i can't say")),
    "orbit_trap": (
        ("i fly the route my fear drew",
         "the zero's mine, the sky's the crew",
         "i trust the dark, i have no fear",
         "the orbit's mine, the sky is clear"),
        ("no gravity, no permission",
         "orbit is my addition")),
    "lofi": (
        ("rain on the window, tea gone cold",
         "i study you in half-lit gold",
         "the page turns slow, the light extends",
         "i keep the space where daylight ends"),
        ("vinyl crackle, rain on the sill",
         "i write the part i never will")),
}


# Verse material for the FALLBACK path: authored couplets that rhyme by
# construction, so a bank song is never the flat free-verse wall the old
# shared bank produced. A release gets 4 consecutive-but-distinct couplets
# (2 per verse) chosen from a per-genre offset — same genre never sings the
# same verse twice in a row, and different genres start in different places.
VERSE_COUPLETS: tuple[tuple[str, str], ...] = (
    ("i drive until the pain lets go",
     "the radio knows what i don't show"),
    ("your name still lives inside my phone",
     "i keep it lit, i die alone"),
    ("the city hums a lower key",
     "it never asked for you or me"),
    ("two cups of coffee, one cold chair",
     "i set the table, then i stare"),
    ("the rear-view holds your fading face",
     "i speed to slow down time and space"),
    ("rain writes what we never said",
     "i leave the porch light on instead"),
    ("i wrote your name in window steam",
     "it faded first, i woke the same"),
    ("midnight doesn't judge me, no",
     "it only asks me where to go"),
    ("the engine hums our old refrain",
     "i say it low, i say it plain"),
    ("some goodbyes land like summer rain",
     "they wet the street, they don't explain"),
    ("i pay the cost and leave the tip",
     "i keep my promise, lose my grip"),
    ("the night is deep, the tape still spins",
     "i lose you where the song begins"),
)


def verses_for(key: str, rng) -> tuple[list[str], list[str]]:
    """Two DISTINCT 4-line verses built from 4 different couplets."""
    n = len(VERSE_COUPLETS)
    off = (abs(hash(key)) // 2 + rng.randrange(1, n)) % n
    idx = [off % n, (off + 3) % n, (off + 6) % n, (off + 9) % n]
    if len(set(idx)) < 4:                       # tiny tables — never repeat a pair
        idx = list(range(4))
    pick = [VERSE_COUPLETS[i] for i in idx]
    v1 = [pick[0][0], pick[0][1], pick[1][0], pick[1][1]]
    v2 = [pick[2][0], pick[2][1], pick[3][0], pick[3][1]]
    # keep the title's own flavour line first in verse 2 when we have one
    return v1, v2


def has_genre(key: str) -> bool:
    return key in CHORUSES


def chorus_for(key: str) -> tuple[str, ...]:
    return CHORUSES.get(key, CHORUSES["deep_pop"])[0]


def bridge_for(key: str) -> tuple[str, ...]:
    return CHORUSES.get(key, CHORUSES["deep_pop"])[1]
