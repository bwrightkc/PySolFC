#!/usr/bin/env python
# -*- mode: python; coding: utf-8; -*-
#
# Generates confirmed-solvable Klondike seeds for
# pysollib/games/solvable_seeds/klondike_solvable_seeds.py.
#
# Deals each seed exactly as PySolFC would (via pysol_cards, the same
# MTRandom shuffle pysollib itself uses for seeds >= 32000 -- see
# construct_random() in pysolrandom.py) and hands the board to
# bwrightkc/klondike-solver-test's `klondike-solver` binary (a fork of
# sigoden/klondike, migrated from ShootMe's MinimalKlondike) over stdin.
#
# Build the solver first:
#   git clone https://github.com/bwrightkc/klondike-solver-test
#   cd klondike-solver-test && cargo build --release -p klondike-cli
#
# Usage:
#   scripts/generate_klondike_solvable_seeds.py --solver PATH/klondike-solver \
#       --start-seed 211080 --count 5000

import argparse
import re
import subprocess
import time
from pathlib import Path

from pysol_cards.deal_game import Game
from pysol_cards.random_base import RandomBase

SEEDS_FILE = (
    Path(__file__).resolve().parent.parent
    / "pysollib" / "games" / "solvable_seeds" / "klondike_solvable_seeds.py"
)
DIFFICULTY_FILE = (
    Path(__file__).resolve().parent.parent
    / "pysollib" / "games" / "solvable_seeds" / "klondike_seed_difficulty.py"
)


def load_existing_seeds():
    # exec'd directly (not imported) so this script doesn't have to pull in
    # the rest of the pysollib.games package, which needs a GUI toolkit.
    ns = {}
    exec(SEEDS_FILE.read_text(encoding="utf-8"), ns)
    return ns["SOLVABLE_SEEDS"]


def load_attempted_ranges():
    # The header's "covering ..." line is the only record of which spans
    # were actually run through the solver (individual unsolvable seeds
    # are just missing from the tuple, not distinguishable from
    # never-attempted ones). Parse it so a fresh run doesn't claim
    # coverage over a gap -- e.g. the untouched 110023-199999 stretch --
    # that was never attempted.
    m = re.search(r"covering (.+)\.", SEEDS_FILE.read_text(encoding="utf-8"))
    ranges = []
    for part in m.group(1).split(", "):
        if "-" in part:
            a, b = part.split("-")
            ranges.append((int(a), int(b)))
        else:
            ranges.append((int(part), int(part)))
    return ranges


def load_existing_difficulty():
    if not DIFFICULTY_FILE.exists():
        return {}
    ns = {}
    exec(DIFFICULTY_FILE.read_text(encoding="utf-8"), ns)
    return dict(ns["SEED_STATES"])


def merge_ranges(ranges):
    ranges = sorted(ranges)
    merged = [ranges[0]]
    for a, b in ranges[1:]:
        last_a, last_b = merged[-1]
        if a <= last_b + 1:
            merged[-1] = (last_a, max(last_b, b))
        else:
            merged.append((a, b))
    return merged

RANKS = "A23456789TJQK"
# klondike-solver's Board format wants suit symbols, not letters. Order
# matches pysollib's util.SUITS (Club Spade Heart Diamond).
SUITS = "♣♠♥♦"


def board_text(seed):
    deal = Game("klondike", seed, RandomBase.DEALS_PYSOLFC)
    deal.deal()
    deal.klondike()
    board = deal.board

    lines = []
    for i, col in enumerate(board.columns.cols, start=1):
        cards = "".join(f"{RANKS[c.rank - 1]}{SUITS[c.suit]}" for c in col)
        face_up = f"{RANKS[col[-1].rank - 1]}{SUITS[col[-1].suit]}"
        face_down = cards[:-2]
        lines.append(f"Tableau{i}: {face_down}|{face_up}")

    # board.talon[0] is the next card to draw (top of stock); the solver's
    # Stock: line is drawn from the right end, so the top card goes last.
    stock = "".join(
        f"{RANKS[c.rank - 1]}{SUITS[c.suit]}" for c in reversed(board.talon)
    )
    lines.append(f"Stock: {stock}")
    lines.append("DrawCount: 1")
    return "\n".join(lines)


STATES_RE = re.compile(r"States:\s*(\d+)")


def solve_seed(solver_path, seed, max_states):
    # Returns the solver's states-explored count if solvable, else None.
    # States-explored is a reasonable, free difficulty proxy: harder boards
    # force the search to branch/backtrack more before it finds a solution.
    text = board_text(seed)
    try:
        proc = subprocess.run(
            [solver_path, "--fast", "--max-states", str(max_states)],
            input=text,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=60,
        )
    except subprocess.TimeoutExpired:
        return None
    if "Solved" not in proc.stdout:
        return None
    m = STATES_RE.search(proc.stdout)
    return int(m.group(1)) if m else None


def format_seeds_file(seeds, attempted_ranges):
    seeds = sorted(seeds)
    coverage = ", ".join(
        f"{a}-{b}" if a != b else str(a) for a, b in attempted_ranges
    )

    lines = [
        "#!/usr/bin/env python",
        "# -*- mode: python; coding: utf-8; -*-",
        "#",
        "# Klondike seeds confirmed solvable, used by KlondikeAlwaysSolvable",
        "# in klondike.py. Made with the seed generator script -- run it",
        "# again with a fresh --start-seed to add more.",
        "#",
        "# Must all be >= 32000, or they'd deal a different game than what",
        "# was actually solved (see construct_random() in pysolrandom.py).",
        "#",
        f"# {len(seeds)} seeds, covering {coverage}.",
        "",
        "SOLVABLE_SEEDS = (",
    ]
    for i in range(0, len(seeds), 8):
        chunk = seeds[i:i + 8]
        lines.append("    " + ", ".join(str(s) for s in chunk) + ",")
    lines.append(")")
    lines.append("")
    return "\n".join(lines)


def tier_seeds(difficulty):
    # Split into rough thirds by states-explored. Needs at least a handful
    # of data points per tier to mean anything.
    if len(difficulty) < 3:
        return {}, {}, {}
    ordered = sorted(difficulty.items(), key=lambda kv: kv[1])
    n = len(ordered)
    easy_cut = n // 3
    hard_cut = 2 * n // 3
    easy = dict(ordered[:easy_cut])
    medium = dict(ordered[easy_cut:hard_cut])
    hard = dict(ordered[hard_cut:])
    return easy, medium, hard


def format_difficulty_file(difficulty):
    states = sorted(difficulty.items())
    easy, medium, hard = tier_seeds(difficulty)

    lines = [
        "#!/usr/bin/env python",
        "# -*- mode: python; coding: utf-8; -*-",
        "#",
        "# Difficulty data for the KlondikeAlwaysSolvable seed pool in",
        "# klondike_solvable_seeds.py, made by the same seed generator",
        "# script. SEED_STATES maps seed -> states the solver explored to",
        "# find a solution (--fast mode) -- a free difficulty proxy: harder",
        "# boards force the search to branch/backtrack more.",
        "#",
        "# Only covers seeds actually run through klondike-solver-test;",
        "# seeds from the original ShootMe-generated pool have no stats and",
        "# are absent here, even though they're still in SOLVABLE_SEEDS.",
        "#",
        f"# {len(states)} seeds with known difficulty, split into rough",
        "# thirds by states-explored -- EASY/MEDIUM/HARD_SEEDS below.",
        "",
        "SEED_STATES = {",
    ]
    for seed, n in states:
        lines.append(f"    {seed}: {n},")
    lines.append("}")
    lines.append("")
    for name, bucket in (("EASY", easy), ("MEDIUM", medium), ("HARD", hard)):
        seeds = sorted(bucket)
        lines.append(f"{name}_SEEDS = (")
        for i in range(0, len(seeds), 8):
            chunk = seeds[i:i + 8]
            lines.append("    " + ", ".join(str(s) for s in chunk) + ",")
        lines.append(")")
        lines.append("")
    return "\n".join(lines)


# A long run (e.g. a 90k-seed gap) can take days -- checkpoint often
# enough that a sleep/reboot/Ctrl+C doesn't lose it all.
CHECKPOINT_SECONDS = 300


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--solver", required=True,
                        help="path to the built klondike-solver binary")
    parser.add_argument("--start-seed", type=int, default=32000)
    parser.add_argument("--count", type=int, default=1000,
                        help="number of new seeds to try")
    parser.add_argument("--max-states", type=int, default=20_000_000)
    args = parser.parse_args()

    existing = set(load_existing_seeds())
    found = set(existing)
    attempted_ranges = load_attempted_ranges()
    difficulty = load_existing_difficulty()

    attempt_start = max(args.start_seed, 32000)
    seed = attempt_start
    tried = 0
    new_solvable = 0
    backfilled = 0
    last_checkpoint = time.monotonic()

    def checkpoint(up_to_seed):
        ranges = attempted_ranges
        if tried:
            ranges = merge_ranges(ranges + [(attempt_start, up_to_seed)])
        SEEDS_FILE.write_text(
            format_seeds_file(found, ranges), encoding="utf-8")
        DIFFICULTY_FILE.write_text(
            format_difficulty_file(difficulty), encoding="utf-8")
        print(f"--- checkpoint: {len(found)} seeds total "
              f"({new_solvable} new, {backfilled} backfilled), "
              f"{len(difficulty)} with difficulty data, "
              f"attempted through {up_to_seed} ---")

    try:
        while tried < args.count:
            # Seeds already in the pool but from the old ShootMe-era
            # generator have no difficulty data (no states-explored
            # number) -- re-solve those too, just to backfill it.
            already_solvable = seed in existing
            if not already_solvable or seed not in difficulty:
                tried += 1
                states = solve_seed(args.solver, seed, args.max_states)
                if states is not None:
                    found.add(seed)
                    difficulty[seed] = states
                    if already_solvable:
                        backfilled += 1
                        print(f"{seed}: backfilled, {states} states "
                              f"({backfilled} backfilled so far)")
                    else:
                        new_solvable += 1
                        print(f"{seed}: solvable, {states} states "
                              f"({new_solvable} new so far)")
                elif already_solvable:
                    print(f"{seed}: WARNING -- previously confirmed "
                          f"solvable but the solver couldn't reconfirm "
                          f"it now; kept in the pool, difficulty left "
                          f"unscored")
                else:
                    print(f"{seed}: no solution / gave up")
            seed += 1
            if time.monotonic() - last_checkpoint > CHECKPOINT_SECONDS:
                checkpoint(seed - 1)
                last_checkpoint = time.monotonic()
    except KeyboardInterrupt:
        print("\nInterrupted -- saving progress before exit.")
    finally:
        checkpoint(seed - 1)
        print(f"Wrote {len(found)} seeds ({new_solvable} new) to "
              f"{SEEDS_FILE}")
        print(f"Wrote difficulty data for {len(difficulty)} seeds "
              f"({backfilled} backfilled) to {DIFFICULTY_FILE}")


if __name__ == "__main__":
    main()
