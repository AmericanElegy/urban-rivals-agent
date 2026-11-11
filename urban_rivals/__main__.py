import argparse
import json
import random
import time
from pathlib import Path
from dataclasses import asdict
from .engine import resolve, legal_moves
from .io import load_state
from .solver import advise


def sample(advice, rng):
    return rng.choices(advice.moves, weights=advice.probabilities, k=1)[0]


def main():
    parser = argparse.ArgumentParser(description="Urban Rivals local strategy agent")
    parser.add_argument("command", choices=("advise", "simulate", "serve", "inspect", "replay"))
    parser.add_argument("state", nargs="?", help="JSON state file (advise/simulate only)")
    parser.add_argument("--side", type=int, choices=(0, 1), default=0)
    parser.add_argument("--observed-card", type=int)
    parser.add_argument("--iterations", type=int, default=1000)
    parser.add_argument("--games", type=int, default=1)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--execute", action="store_true", help="Allow extension clicks; serve defaults to inspect only")
    parser.add_argument("--reuse-pairing-token", action="store_true", help="Reuse the existing local token for a diagnostic server restart")
    parser.add_argument("--port", type=int, default=8876)
    parser.add_argument("--output", default="local", help="Local canvas/receipt directory")
    args = parser.parse_args()
    try:
        if args.command=="replay":
            if args.state is None:
                raise ValueError("replay requires a labeled manifest JSON")
            from .replay import replay
            result=replay(args.state,output_path=str(Path(args.output)/"ocr-replay-report.json"))
            print(json.dumps({"passed":result["passed"],"groups":result["groups"],"missing":result["missing"]},indent=2))
            if not result["passed"]:
                parser.exit(1)
            return
        if args.command == "inspect":
            if args.state is None:
                raise ValueError("inspect requires a saved canvas PNG")
            from .vision import CanvasReader
            from PIL import Image
            report=CanvasReader().diagnostics(Image.open(args.state).convert("RGB").resize((1318,744)))
            print(json.dumps(report,indent=2,ensure_ascii=True))
            return
        if args.command == "serve":
            from .bridge import serve
            serve(port=args.port,execute=args.execute,output=args.output,reuse_token=args.reuse_pairing_token)
            return
        if args.state is None:
            raise ValueError("advise/simulate require a JSON state file")
        if args.iterations < 1 or args.games < 1:
            raise ValueError("Iterations and games must be positive")
        state = load_state(args.state)
        rng = random.Random(args.seed)
        start = time.perf_counter()
        if args.command == "advise":
            advice = advise(state, args.side, args.observed_card, args.iterations)
            choices = sorted(zip(advice.moves, advice.probabilities), key=lambda x: -x[1])
            print(json.dumps({"horizon": "one round; heuristic continuation",
                              "value": advice.value, "equilibrium_gap": advice.gap,
                              "sampled_move": asdict(sample(advice, rng)),
                              "strategy": [{**asdict(m), "name": state.players[args.side].hand[m.card].name,
                                            "probability": p} for m, p in choices if p > .001],
                              "seconds": time.perf_counter() - start}, indent=2))
        else:
            outcomes = [0, 0, 0]
            for game in range(args.games):
                current = state
                while not current.terminal:
                    leader = current.leader
                    # Agent controls side 0; legal random opponent is a smoke-test baseline.
                    if leader == 0:
                        a = sample(advise(current, 0, iterations=args.iterations), rng)
                        b = rng.choice(legal_moves(current, 1))
                    else:
                        b = rng.choice(legal_moves(current, 1))
                        a = sample(advise(current, 0, b.card, args.iterations), rng)
                    before = current
                    current = resolve(current, a, b)
                    print(json.dumps({"game": game + 1, "round": before.round,
                                      "moves": [asdict(a), asdict(b)],
                                      "life": [p.life for p in current.players],
                                      "pillz": [p.pillz for p in current.players]}))
                a, b = current.players
                outcomes[0 if a.life > b.life else 1 if a.life < b.life else 2] += 1
            print(json.dumps({"wins": outcomes[0], "losses": outcomes[1], "draws": outcomes[2],
                              "seconds": time.perf_counter() - start,
                              "opponent": "uniform legal random; not a strength benchmark"}))
    except (ValueError, KeyError, TypeError, OSError, ImportError) as error:
        parser.exit(2, f"Cannot run: {error}\n")


if __name__ == "__main__":
    main()
