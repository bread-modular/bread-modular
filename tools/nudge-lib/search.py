#!/usr/bin/env python3
"""
search.py — search drivers for the Nudge Tool.

Implements the lexicographic objective and the greedy / grid / random drivers
(plan section 7). The search is *build-bound* (each full autoroute is ~35-60s),
so every design choice here minimizes the number of full `tsci build` calls.

Objective (minimize, lexicographic):
    score = (router_failed, n_clearance, n_incomplete)
Solved when score == (0, 0, 0).

Stdlib only. The driver is testable against a pure `evaluate` callback; the CLI
supplies the real one (build + classify). No file I/O or subprocess here.
"""

from __future__ import annotations

import random
import time


# Config axes are lowercase ('x'/'y'); locate.mjs positions use 'pcbX'/'pcbY'.
PCB_AXIS = {"x": "pcbX", "y": "pcbY"}


def better(a, b) -> bool:
    """True if score `a` is lexicographically better (lower) than `b`."""
    return tuple(a) < tuple(b)


def is_solved(score) -> bool:
    return tuple(score) == (0, 0, 0)


def _axis_step(cfg, axis) -> float:
    step = cfg.get("step", 0.4)
    if isinstance(step, dict):
        return step.get(axis, 0.4)
    return step


def gen_candidate_moves(config, positions, implicated, displacement, strategy, rng, full=False):
    """Yield (name, axis, delta) candidate moves, deterministic for greedy/grid.

    Ordering: implicated components first (in the order the classifier reported
    them), then the remaining whitelist in config order. A move is only yielded
    if it stays within the component's `range` (total displacement bound from
    the original position, plan section 4).

    `full=False` scopes to the implicated whitelisted components (falling back
    to the whole whitelist when none are implicated or none are whitelisted —
    plan section 7). `full=True` always includes the whole whitelist (implicated
    first, then the rest) and is used as a plateau fallback.
    """
    whitelist = config["components"]

    if full:
        # Whole whitelist, implicated components first.
        order = []
        if implicated:
            order.extend(c for c in implicated if c in whitelist)
        order.extend(c for c in whitelist if c not in order)
    elif implicated:
        order = [c for c in implicated if c in whitelist]
        if not order:
            order = list(whitelist)
    else:
        order = list(whitelist)

    def _move_for(name, axis, delta):
        rng_mm = whitelist[name].get("range")
        if rng_mm is not None:
            cur = displacement.get(name, {}).get(axis, 0.0)
            if abs(cur + delta) > rng_mm + 1e-9:
                return None
        return (name, axis, delta)

    if strategy == "random":
        # Sample K random single-axis moves from the whitelist (plan section 7).
        k = config.get("search", {}).get("randomK", 12)
        pool = []
        for name in order:
            axes = whitelist[name].get("axes", ["x", "y"])
            for axis in axes:
                s = _axis_step(whitelist[name], axis)
                for delta in (s, -s):
                    pool.append((name, axis, delta))
        rng.shuffle(pool)
        for name, axis, delta in pool[:k]:
            mv = _move_for(name, axis, delta)
            if mv:
                yield mv
        return

    # greedy / grid: exhaustive single-step neighborhood, deterministic.
    for name in order:
        cfg = whitelist[name]
        axes = cfg.get("axes", ["x", "y"])
        for axis in axes:
            s = _axis_step(cfg, axis)
            for delta in (s, -s):
                mv = _move_for(name, axis, delta)
                if mv:
                    yield mv


def run_search(
    config,
    initial_content,
    initial_positions,
    initial_analysis,
    write,
    build_score,
    relocate,
    splice,
    strategy="greedy",
    max_iters=None,
    time_budget=None,
    rng=None,
    verbose=False,
    log=None,
):
    """Run the nudge search and return a result dict.

    `max_iters` is a hard cap on the TOTAL number of full autoroute builds
    performed by the search (across all phases: scoped descent + fallback),
    not merely the number of committed passes. `time_budget` is an independent
    wall-clock cap checked before each build.

    Callbacks (supplied by the CLI):
      write(content_bytes)          write bytes to the .circuit.tsx file
      build_score()                 rm cache + tsci build + classify -> analysis
      relocate()                    re-run locate.mjs on the current file
      splice(content, pos, n, a, v) pure editor (edit.splice)

    Returns:
      { "best_content", "best_positions", "best_analysis", "displacement",
        "iterations", "builds", "log": [lines], "solved": bool, "early_exit": bool }
    """
    search_cfg = config.get("search", {})
    max_iters = max_iters if max_iters is not None else search_cfg.get("maxIterations", 60)
    time_budget = time_budget if time_budget is not None else search_cfg.get("timeBudgetSec", 900)
    rng = rng or random.Random(0)
    log = log if log is not None else []

    def note(msg):
        log.append(msg)
        if verbose:
            print(msg)

    start = time.time()

    best_content = initial_content
    best_positions = initial_positions
    best_analysis = initial_analysis
    displacement = {}  # name -> {axis: cumulative delta from original}

    result = {
        "best_content": best_content,
        "best_positions": best_positions,
        "best_analysis": best_analysis,
        "displacement": displacement,
        "iterations": 0,
        "builds": 0,
        "log": log,
        "solved": False,
        "early_exit": False,
    }

    if best_analysis.get("broken"):
        raise RuntimeError("BROKEN build (pcb_missing_footprint_error) — cannot nudge")

    # Early exit: already clean (applies to every strategy, not just greedy).
    if is_solved(best_analysis["score"]):
        note(f"[search] baseline already DRC-clean {tuple(best_analysis['score'])} — no candidates")
        result["solved"] = True
        result["early_exit"] = True
        return result

    max_scoped_passes = 1 if strategy == "grid" else max_iters
    passes = 0
    builds = 0

    def commit_candidate(cand):
        # cand = (score, name, axis, delta, new_value, new_content, analysis)
        nonlocal best_content, best_positions, best_analysis
        _, name, axis, delta, new_value, new_content, analysis = cand
        best_content = new_content
        best_analysis = analysis
        disp = displacement.setdefault(name, {})
        disp[axis] = round(disp.get(axis, 0.0) + delta, 4)
        write(best_content)
        best_positions = relocate()
        note(f"[search] commit {name}.{axis} {delta:+g} -> {tuple(analysis['score'])}")

    def evaluate_moves(moves):
        nonlocal builds
        best_candidate = None  # (score, name, axis, delta, new_value, new_content, analysis)
        for (name, axis, delta) in moves:
            if builds >= max_iters:
                note(f"[search] build budget exhausted ({max_iters} builds) — stopping")
                break
            if time.time() - start > time_budget:
                note("[search] time budget exceeded (mid-pass)")
                break
            pcb_axis = PCB_AXIS.get(axis, axis)
            new_value = round(best_positions[name][pcb_axis]["value"] + delta, 4)
            new_content = splice(best_content, best_positions, name, pcb_axis, new_value)

            write(new_content)
            analysis = build_score()
            builds += 1
            write(best_content)  # revert to committed layout

            if analysis.get("broken"):
                write(best_content)
                raise RuntimeError(
                    f"BROKEN build while nudging {name}.{axis} {delta:+g} — cannot nudge")

            note(f"    {name}.{axis} {delta:+g} -> {tuple(analysis['score'])}")
            if best_candidate is None or better(analysis["score"], best_candidate[0]):
                best_candidate = (analysis["score"], name, axis, delta, new_value, new_content, analysis)

            if is_solved(analysis["score"]):
                break  # zero found inside this pass
        return best_candidate

    # Phase 1: scoped (implicated) steepest descent.
    while builds < max_iters and passes < max_scoped_passes and not is_solved(best_analysis["score"]):
        if time.time() - start > time_budget:
            note("[search] time budget exceeded")
            break

        moves = list(gen_candidate_moves(
            config, best_positions, best_analysis.get("implicated"), displacement, strategy, rng))
        note(f"[search] pass {passes + 1}: {len(moves)} candidates "
             f"(implicated={sorted(best_analysis.get('implicated', {}))})")

        best_candidate = evaluate_moves(moves)
        if best_candidate is None:
            note("[search] no candidates to evaluate — stopping")
            break

        cand_score = best_candidate[0]
        if better(cand_score, best_analysis["score"]):
            commit_candidate(best_candidate)
            passes += 1
        else:
            note(f"[search] plateau (best {tuple(cand_score)} not < {tuple(best_analysis['score'])})")
            break

    # Phase 2 (fallback): if still not solved, one full-whitelist pass
    # (implicated first, then the rest) so the search can escape a scoped local
    # minimum where the true culprit is not directly implicated by the errors.
    if not is_solved(best_analysis["score"]) and builds < max_iters and time.time() - start <= time_budget:
        moves = list(gen_candidate_moves(
            config, best_positions, best_analysis.get("implicated"), displacement, strategy, rng, full=True))
        note(f"[search] fallback: full-whitelist pass ({len(moves)} candidates)")
        best_candidate = evaluate_moves(moves)
        if best_candidate is not None and better(best_candidate[0], best_analysis["score"]):
            commit_candidate(best_candidate)
        elif best_candidate is None:
            note("[search] no candidates in fallback — stopping")

    result.update({
        "best_content": best_content,
        "best_positions": best_positions,
        "best_analysis": best_analysis,
        "displacement": displacement,
        "iterations": passes,
        "builds": builds,
        "solved": is_solved(best_analysis["score"]),
    })
    return result
