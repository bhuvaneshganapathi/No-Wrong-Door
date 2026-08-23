#!/usr/bin/env python3
"""
No Wrong Door - Interactive Command-Line Demonstration Tool
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import json
import argparse
from app.services.aggregator import ResidentAggregator

def print_header(title: str):
    print("\n" + "=" * 70)
    print(f" {title}")
    print("=" * 70)

def main():
    parser = argparse.ArgumentParser(description="No Wrong Door Unified Resident View CLI")
    parser.add_argument("--page", type=int, default=1, help="Page number to view (default 1)")
    parser.add_argument("--page-size", type=int, default=10, help="Page size (default 10)")
    parser.add_argument("--id", type=str, default=None, help="Resident ID to query")
    parser.add_argument("--stats", action="store_true", help="Display failure rate statistics")
    parser.add_argument("--simulate", type=int, default=0, help="Run simulation of N calls to demonstrate 40%% failure handling")
    args = parser.parse_args()

    aggregator = ResidentAggregator()

    if args.simulate > 0:
        print_header(f"Simulating {args.simulate} Requests to Test 40% Failure Rate Resilience")
        successes = 0
        degraded = 0
        failures = 0
        for i in range(1, args.simulate + 1):
            sys.stdout.write(f"\rExecuting request {i}/{args.simulate}...")
            sys.stdout.flush()
            res = aggregator.get_unified_view(page=1, page_size=5)
            status = res.get('status')
            if status == 'ok':
                successes += 1
            elif status == 'degraded':
                degraded += 1
            else:
                failures += 1
        print("\n")
        print(f"Simulation Summary:")
        print(f"  Total Requests Executed : {args.simulate}")
        print(f"  Full Successes ('ok')   : {successes}")
        print(f"  Degraded Payloads       : {degraded} (Partial data delivered, no 500 thrown!)")
        print(f"  Complete Failures       : {failures}")

        stats = aggregator.xml_adapter.get_stats()
        print_header("Upstream Failure Rate Statistics")
        print(f"  Total XML Calls Made    : {stats['total_calls']}")
        print(f"  XML Failures Encountered: {stats['total_failures']}")
        print(f"  Observed Failure Rate   : {stats['failure_rate_percent']}%")
        print(f"  Retries Succeeded       : {stats['retries_succeeded']}")
        print(f"  Retries Failed          : {stats['retries_failed']}")
        return

    if args.stats:
        stats = aggregator.xml_adapter.get_stats()
        print_header("Upstream XML Benefits Register Failure Statistics")
        print(f"  Total Calls          : {stats['total_calls']}")
        print(f"  Total Failures       : {stats['total_failures']}")
        print(f"  Failure Rate         : {stats['failure_rate_percent']}%")
        print(f"  Retries Succeeded    : {stats['retries_succeeded']}")
        print(f"  Retries Failed       : {stats['retries_failed']}")
        return

    if args.id:
        print_header(f"Querying Resident ID: {args.id}")
        res = aggregator.get_unified_view(resident_id=args.id)
    else:
        print_header(f"Unified Resident View (Page {args.page}, Size {args.page_size})")
        res = aggregator.get_unified_view(page=args.page, page_size=args.page_size)

    # Display System Metadata & Degradation Status
    print(f"\n[SYSTEM STATUS: {res['status'].upper()}]")
    print(f"Latency: {res['total_latency_ms']} ms | Timestamp: {res['timestamp']}")

    print("\nSource Adapter Status:")
    for src_key, src_info in res['sources'].items():
        st_symbol = "[OK]" if src_info['status'] == 'ok' else "[DEGRADED/FAILED]"
        from_c = " (FROM CACHE)" if src_info.get('from_cache') else ""
        attempts = f" [{src_info.get('attempts_made', 1)} attempts]" if 'attempts_made' in src_info else ""
        print(f"  - {src_key:18}: {st_symbol}{from_c}{attempts} | Count: {src_info['record_count']} | Latency: {src_info['latency_ms']} ms")
        if src_info.get('error'):
            print(f"    ---> Warning/Reason: {src_info['error']}")
        if src_info.get('duplicates_removed', 0) > 0:
            print(f"    ---> Deduplication : {src_info['duplicates_removed']} duplicate records removed across page boundaries")

    stats = res.get('failure_rate_stats', {})
    print(f"\nBenefits Register Health: {stats.get('failure_rate_percent', 0.0)}% failure rate observed ({stats.get('retries_succeeded', 0)} retries succeeded)")

    residents = res.get('residents', [])
    print_header(f"Resident Records Returned ({len(residents)})")
    
    for r in residents:
        print(f"ID: {r['id']:<8} | Name: {r['first_name']} {r['last_name']:<12} | DOB: {r['date_of_birth']} | Address: {r['address_line']}, {r['city']}")
        b_list = r.get('benefits', [])
        if b_list:
            for b in b_list:
                conf = b.get('match_confidence', {})
                print(f"   ---> [MATCHED BENEFIT] Ref: {b['ref']} | Code: {b['benefit_code']} | Match Score: {conf.get('score')} ({conf.get('level')}) | Reasons: {', '.join(conf.get('reasons', []))}")
        else:
            print(f"   ---> [NO MATCHED BENEFITS]")

if __name__ == "__main__":
    main()
