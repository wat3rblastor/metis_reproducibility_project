import os
import json
import maxminddb
import pandas as pd
import re

# Path to the MaxMind ASN database (update this path as needed)
asn_db_path = "GeoLite2-ASN.mmdb"

# Directories to process
directory_paths = ["metis_like_results", "random_results"]

# Open the MaxMind database
with maxminddb.open_database(asn_db_path) as reader:
    # Dictionary to store results
    folder_stats = {}

    for path in directory_paths:
        folder_stats[path] = {}

        # Walk through the directory structure
        for root, _, files in os.walk(path):
            parts = root.split(os.sep)
            if len(parts) < 2:
                continue  # Skip root-level directory

            second_level_folder = parts[1]

            if second_level_folder not in folder_stats[path]:
                folder_stats[path][second_level_folder] = {
                    "unique_asns": set(),
                    "total_ip_hops": 0,
                    "total_rtt": 0,
                    "trace_count": 0
                }

            # Process JSON files in the current directory
            for file in files:
                if file.endswith(".json"):
                    file_path = os.path.join(root, file)

                    try:
                        with open(file_path, "r") as f:
                            for line in f:
                                try:
                                    data = json.loads(line.strip())

                                    ip_hops = 0
                                    total_rtt = 0
                                    rtt_count = 0

                                    for hop in data.get("result", []):
                                        for result in hop.get("result", []):
                                            ip = result.get("from")
                                            rtt = result.get("rtt")

                                            if ip:
                                                ip_hops += 1  # Count IP hops

                                                # Lookup ASN in MaxMind database
                                                asn_info = reader.get(ip)
                                                if asn_info and "autonomous_system_number" in asn_info:
                                                    asn = asn_info["autonomous_system_number"]
                                                    folder_stats[path][second_level_folder]["unique_asns"].add(asn)

                                            if rtt:
                                                total_rtt += rtt
                                                rtt_count += 1

                                    if ip_hops > 0:
                                        folder_stats[path][second_level_folder]["total_ip_hops"] += ip_hops
                                        folder_stats[path][second_level_folder]["trace_count"] += 1

                                    if rtt_count > 0:
                                        folder_stats[path][second_level_folder]["total_rtt"] += total_rtt

                                except json.JSONDecodeError:
                                    pass  # Skip malformed JSON entries

                    except Exception:
                        pass  # Skip files that can't be read

    # Convert sets to counts and calculate averages
    results = []
    grouped_random_results = {}

    for path, folder_data in folder_stats.items():
        for folder, stats in folder_data.items():
            trace_count = stats["trace_count"]
            avg_ip_hops = stats["total_ip_hops"] / trace_count if trace_count > 0 else 0
            avg_rtt = stats["total_rtt"] / trace_count if trace_count > 0 else 0
            unique_asn_count = len(stats["unique_asns"])

            results.append([path, folder, unique_asn_count, avg_ip_hops, avg_rtt])

            # Aggregate results for "random_results" folders starting with the same number
            if path == "random_results":
                match = re.match(r"^(\d+)-", folder)
                if match:
                    prefix = match.group(1)  # Extract number prefix
                    if prefix not in grouped_random_results:
                        grouped_random_results[prefix] = {
                            "unique_asns": 0,
                            "total_ip_hops": 0,
                            "total_rtt": 0,
                            "trace_count": 0,
                        }
                    grouped_random_results[prefix]["unique_asns"] += unique_asn_count
                    grouped_random_results[prefix]["total_ip_hops"] += stats["total_ip_hops"]
                    grouped_random_results[prefix]["total_rtt"] += stats["total_rtt"]
                    grouped_random_results[prefix]["trace_count"] += trace_count

    # Compute grouped averages
    grouped_results = []
    for prefix, stats in grouped_random_results.items():
        trace_count = stats["trace_count"]
        avg_ip_hops = stats["total_ip_hops"] / trace_count if trace_count > 0 else 0
        avg_rtt = stats["total_rtt"] / trace_count if trace_count > 0 else 0
        grouped_results.append(["random_results", f"{prefix}-*", stats["unique_asns"], avg_ip_hops, avg_rtt])

# Convert results to DataFrame
df = pd.DataFrame(results, columns=["Directory", "Second-Level Folder", "Unique ASN Count", "Avg IP Hops", "Avg RTT (ms)"])
grouped_df = pd.DataFrame(grouped_results, columns=["Directory", "Grouped Folders", "Total Unique ASNs", "Avg IP Hops", "Avg RTT (ms)"])

# Display results
print("\nAggregated Results:")
print(df.to_string(index=False))

print("\nGrouped Averages for Random Results:")
print(grouped_df.to_string(index=False))
