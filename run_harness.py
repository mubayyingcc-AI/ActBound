import argparse
import json
from actbound.scenarios import write_results

parser = argparse.ArgumentParser(description="Run ActBound local sandbox experiments")
parser.add_argument("--trials", type=int, default=1000)
parser.add_argument("--output", default="results")
args = parser.parse_args()
if args.trials < 1:
    parser.error("--trials must be positive")
print(json.dumps(write_results(args.output, args.trials), indent=2))
