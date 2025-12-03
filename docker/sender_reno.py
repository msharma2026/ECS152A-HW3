#!/usr/bin/env python3
"""
Minimal sender skeleton for ECS 152A project.

Purpose:
    - Send two demo packets (plus EOF marker) to verify your environment,
      receiver, and test scripts are wired up correctly.
    - Provide a tiny Stop-and-Wait style template students can extend.

Usage:
    ./test_sender.sh sender_skeleton.py [payload.zip]

Notes:
    - This is NOT a full congestion-control implementation.
    - It intentionally sends only a couple of packets so you can smoke-test
      the simulator quickly before investing time in your own sender.
    - Delay, jitter, and score calculations are hardcoded placeholders.
      Students should implement their own metrics tracking.
"""

from __future__ import annotations

import os
import socket
import sys
import time
from typing import List, Tuple, Dict

PACKET_SIZE = 1024
SEQ_ID_SIZE = 4
MSS = PACKET_SIZE - SEQ_ID_SIZE
ACK_TIMEOUT = 0.5
MAX_TIMEOUTS = 10

HOST = os.environ.get("RECEIVER_HOST", "127.0.0.1")
PORT = int(os.environ.get("RECEIVER_PORT", "5001"))

def verify_transfer() -> bool:
    """Verify the received file matches the original."""
    # Get original file path
    original_file = (
        os.environ.get("TEST_FILE") or os.environ.get("PAYLOAD_FILE") or "/hdd/file.zip"
    )

    basename = os.path.basename(original_file)
    if "." in basename:
        name, ext = basename.rsplit(".", 1)
        received_basename = f"{name}_received.{ext}"
    else:
        received_basename = f"{basename}_received"

    received_file = f"/hdd/{received_basename}"

    if not os.path.exists(received_file):
        print(f"✗ Received file not found: {received_file}")
        return False

    original_size = os.path.getsize(original_file)
    received_size = os.path.getsize(received_file)

    if original_size != received_size:
        print(
            f"✗ Size mismatch: original={original_size:,}, received={received_size:,}"
        )
        return False

    with open(original_file, "rb") as f1, open(received_file, "rb") as f2:
        if f1.read() == f2.read():
            print(f"✓ Transfer verified! {original_size:,} bytes sent successfully.")
            return True
        else:
            print("✗ Content mismatch")
            return False

def load_payload_chunks() -> List[bytes]:
    """
    Reads the selected payload file (or falls back to file.zip) and returns
    up to two MSS-sized chunks for the demo transfer.
    """
    candidates = [
        os.environ.get("TEST_FILE"),
        os.environ.get("PAYLOAD_FILE"),
        "/hdd/file.zip",
        "file.zip",
    ]

    for path in candidates:
        if not path:
            continue
        expanded = os.path.expanduser(path)
        if os.path.exists(expanded):
            with open(expanded, "rb") as f:
                data = f.read()
            break
    else:
        print(
            "Could not find payload file (tried TEST_FILE, PAYLOAD_FILE, file.zip)",
            file=sys.stderr,
        )
        sys.exit(1)

    return [data[i : i + MSS] for i in range(0, len(data), MSS)]


def make_packet(seq_id: int, payload: bytes) -> bytes:
    return int.to_bytes(seq_id, SEQ_ID_SIZE, byteorder="big", signed=True) + payload


def parse_ack(packet: bytes) -> Tuple[int, str]:
    seq = int.from_bytes(packet[:SEQ_ID_SIZE], byteorder="big", signed=True)
    msg = packet[SEQ_ID_SIZE:].decode(errors="ignore")
    return seq, msg


def print_metrics(total_bytes: int, duration: float, delays: List[float]) -> None:
    """
    Print transfer metrics in the format expected by test scripts.

    TODO: Students should replace the hardcoded delay/jitter/score values
    with actual calculated metrics from their implementation.
    """
    throughput = total_bytes / duration
    avg_delay = 0.0
    avg_jitter = 0.0

    if delays:
        avg_delay = sum(delays) / len(delays) 

    if len(delays) > 1:
        jitter_sum = sum(abs(delays[i] - delays[i-1]) for i in range(1, len(delays)))
        avg_jitter = jitter_sum / (len(delays) - 1)
 

    # Prevents divide by zero errors
    safe_jitter = avg_jitter if avg_jitter > 0 else 1e-6
    safe_delay = avg_delay if avg_delay > 0 else 1e-6
    score = (throughput/2000) + (15/safe_jitter) + (35/safe_delay)

    print("\nDemo transfer complete!")
    print(f"duration={duration:.3f}s throughput={throughput:.2f} bytes/sec")
    print(
        f"avg_delay={avg_delay:.6f}s avg_jitter={avg_jitter:.6f}s"
    )
    print(f"{throughput:.7f},{avg_delay:.7f},{avg_jitter:.7f},{score:.7f}")


def main() -> None:
    demo_chunks = load_payload_chunks()
    transfers: List[Tuple[int, bytes]] = []

    seq = 0
    for chunk in demo_chunks:
        transfers.append((seq, chunk))
        seq += len(chunk)

    # EOF marker
    transfers.append((seq, b""))
    total_bytes = sum(len(chunk) for chunk in demo_chunks)

    print(f"Connecting to receiver at {HOST}:{PORT}")
    print(
        f"Demo transfer will send {total_bytes} bytes across {len(demo_chunks)} packets (+EOF)."
    )

    start = time.time()
    packet_delays = []

    # Sliding Window variables
    base = 0
    next_seq_num = 0
    packet_start_times: Dict[int, float] = {}

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.settimeout(ACK_TIMEOUT)
        addr = (HOST, PORT)
        # Initial congestion window size of 1 for TCP Reno
        cwnd = 1.0
        # Initial slow start threshold of 64 for TCP Reno
        ssthresh = 64
        # Initial 0 duplicate ACKs
        dup_acks = 0
        prev_ack_id = None
        in_fast_recovery = False
        while base < len(transfers):
            
            # Send new packets while window is not full
            while next_seq_num < base + max(int(cwnd), 1) and next_seq_num < len(transfers):
                seq_id, payload = transfers[next_seq_num]
                pkt = make_packet(seq_id, payload)
                sock.sendto(pkt, addr)

                if seq_id not in packet_start_times:
                    packet_start_times[seq_id] = time.time()
                
                next_seq_num += 1

            # Wait for ACKs, then slide window
            try:
                ack_pkt, _ = sock.recvfrom(PACKET_SIZE)
                ack_id, msg = parse_ack(ack_pkt)

                if msg.startswith("fin"):
                    # Respond with FIN/ACK to let receiver exit cleanly
                    fin_ack = make_packet(ack_id, b"FIN/ACK")
                    sock.sendto(fin_ack, addr)
                    duration = max(time.time() - start, 1e-6)
                    print_metrics(total_bytes, duration, packet_delays)
                    verify_transfer()
                    return

                # If we get an ACK for a packet inside our window, assume all previous are received.
                current_base_seq = transfers[base][0]
                if ack_id > current_base_seq:
                    while base < len(transfers) and transfers[base][0] < ack_id:
                        # Calculate delay for the acknowledged packet
                        acked_seq = transfers[base][0]
                        if acked_seq in packet_start_times:
                            packet_delays.append(time.time() - packet_start_times[acked_seq])
                        base += 1

                if prev_ack_id is None or ack_id > prev_ack_id:
                    prev_ack_id = ack_id
                    # Exits fast recovery on new ACK and sets congestion window to the slow start threshold
                    if in_fast_recovery:
                        cwnd = float(ssthresh)
                        in_fast_recovery = False
                    else:
                        # Slow start phase
                        if cwnd < ssthresh:
                            cwnd += 1.0
                        # Congestion avoidance phase
                        else:
                            cwnd += 1.0 / cwnd
                    # Ensures congestion window size is never 0
                    cwnd = max(cwnd, 1.0)
                    dup_acks = 0
                # Detects duplicate ACKs and handles triple duplicate ACKs
                elif ack_id == prev_ack_id:
                    dup_acks += 1
                    if in_fast_recovery:
                        cwnd += 1.0
                        # Send a new packet if possible
                        if next_seq_num < base + int(cwnd) and next_seq_num < len(transfers):
                            seq_id, payload = transfers[next_seq_num]
                            pkt = make_packet(seq_id, payload)
                            sock.sendto(pkt, addr)

                            if seq_id not in packet_start_times:
                                packet_start_times[seq_id] = time.time()
                            
                            next_seq_num += 1

                    elif (dup_acks == 3):
                        # Triple duplicate ACKs, treat them as a timeout and enter fast recovery for TCP Reno
                        ssthresh = max(int(cwnd // 2), 1)
                        cwnd = float(ssthresh) + 3.0
                        dup_acks = 0
                        in_fast_recovery = True
                        
                        # Retransmit the lost packet
                        seq_id, payload = transfers[base]
                        pkt = make_packet(seq_id, payload)
                        sock.sendto(pkt, addr)
                        packet_start_times[seq_id] = time.time()

            except socket.timeout:
                next_seq_num = base
                # Resets congestion window and slow start threshold on timeout, enters slow start for TCP Reno
                ssthresh = max(int(cwnd // 2), 1)
                cwnd = 1.0
                dup_acks = 0
                in_fast_recovery = False
                # Retransmit the lost packet
                seq_id, payload = transfers[base]
                pkt = make_packet(seq_id, payload)
                sock.sendto(pkt, addr)
                packet_start_times[seq_id] = time.time()
                continue


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Skeleton sender hit an error: {exc}", file=sys.stderr)
        sys.exit(1)