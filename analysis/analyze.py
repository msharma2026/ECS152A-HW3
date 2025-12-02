import math
import statistics

def calculate_stats(filename="output.txt"):
    throughputs = []
    delays = []
    jitters = []
    scores = []

    print(f"Reading data from {filename}...\n")

    with open(filename, "r") as f:
        for line in f:
            line = line.strip()
            if line.count(",") == 3:
                try:
                    parts = line.split(",")
                    t = float(parts[0])
                    d = float(parts[1])
                    j = float(parts[2])
                    s = float(parts[3])

                    throughputs.append(t)
                    delays.append(d)
                    jitters.append(j)
                    scores.append(s)
                except ValueError:
                    continue

    def print_row(label, data):
        avg = statistics.mean(data)
        stdev = statistics.stdev(data) if len(data) > 1 else 0.0
        print(f"{label:<20} | Average: {avg:12.6f} | Std Dev: {stdev:10.6f}")

    print("-" * 65)
    print(f"{'Metric':<20} | {'Average':<12}      | {'Std Dev':<10}")
    print("-" * 65)

    print_row("Throughput", throughputs)
    print_row("Average Delay", delays)
    print_row("Average Jitter", jitters)
    print_row("Performance Metric", scores)
    
    print("-" * 65)
    print(f"\nTotal Runs Analyzed: {len(throughputs)}")

if __name__ == "__main__":
    calculate_stats()