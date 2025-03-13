import json
import numpy as np
import pandas as pd
import os
from math import inf

ip_list = []
rtt_matrix = {}
ip_hop_matrix = {}
probe_id_map = {}  # Stores {IP: Probe_ID}
finalprobes = []

# Data Extraction
for root, dirs, files in os.walk("PT"):
    for file in files:
        if file.endswith(".json"):
            file_path = os.path.join(root, file)
            probe_id = os.path.splitext(file)[0]
            with open(file_path, "r") as f:
                try:
                    for line in f:
                        try:
                            data = json.loads(line)
                            destination_ip_responded = data["destination_ip_responded"]

                            if not destination_ip_responded:
                                continue

                            src_ip = data["from"]
                            dst_ip = data["dst_addr"]
                            if src_ip not in probe_id_map:
                                probe_id_map[src_ip] = probe_id

                            if src_ip not in ip_list:
                                ip_list.append(src_ip)
                                rtt_matrix[src_ip] = {}
                                ip_hop_matrix[src_ip] = {}

                            if dst_ip not in ip_list:
                                ip_list.append(dst_ip)
                                rtt_matrix[dst_ip] = {}
                                ip_hop_matrix[dst_ip] = {}

                            last_hop = data["result"][-1]
                            num_ip_hop = last_hop["hop"]
                            rtt = min(hop.get("rtt", inf) for hop in last_hop["result"])

                            min_rtt = min(rtt, rtt_matrix[src_ip].get(dst_ip, inf))
                            min_ip_hop = min(num_ip_hop, ip_hop_matrix[src_ip].get(dst_ip, inf))

                            rtt_matrix[src_ip][dst_ip] = min_rtt
                            rtt_matrix[dst_ip][src_ip] = min_rtt

                            ip_hop_matrix[src_ip][dst_ip] = min_ip_hop    
                            ip_hop_matrix[dst_ip][src_ip] = min_ip_hop                    

                        except json.JSONDecodeError:
                            print(f"Skipping invalid JSON line in {file_path}")

                except Exception as e:
                    print(f"Error reading {file_path}: {e}")

# DataFrame Construction (Remove infinities now)
rtt_df = pd.DataFrame(rtt_matrix).replace(np.inf, np.nan)
ip_hop_df = pd.DataFrame(ip_hop_matrix).replace(np.inf, np.nan)

# Drop rows/columns that are fully NaN (probes with no connections)
rtt_df.dropna(how='all', inplace=True)
rtt_df.dropna(axis=1, how='all', inplace=True)

ip_hop_df.dropna(how='all', inplace=True)
ip_hop_df.dropna(axis=1, how='all', inplace=True)

print("Cleaned RTT Matrix:\n", rtt_df)
print("Cleaned IP Hop Matrix:\n", ip_hop_df)

# Closeness Calculation
def compute_closeness(matrix):
    avg_distances = []
    for probe in matrix.index:
        distances = matrix.loc[probe].dropna()  # Ignore NaN entries
        total_distance = distances.sum()  # Sum all reachable probes

        # If no valid distances remain, mark the probe as unreachable
        avg_dist = total_distance if total_distance > 0 else inf

        avg_distances.append((probe, avg_dist))

    return pd.DataFrame(avg_distances, columns=["Probe", "AvgDistance"]).set_index("Probe")

# Compute redundancy scores (lower = more redundant)
rtt_scores = compute_closeness(rtt_df)
ip_hop_scores = compute_closeness(ip_hop_df)

# Probe Selection Algorithm (Metis)
def metis_selection(matrix, target_size):
    selected_probes = matrix.copy()

    while len(selected_probes) > target_size:
        scores = compute_closeness(selected_probes).dropna()

        if scores.empty:
            print("All remaining probes are unreachable. Stopping selection.")
            break

        probe_to_remove = scores.idxmin()["AvgDistance"]
        selected_probes.drop(index=probe_to_remove, columns=probe_to_remove, inplace=True)

    return selected_probes

# Define the final number of probes
final_probe_count = 100

# Select probes separately for RTT and IP Hops
selected_probes_rtt = metis_selection(rtt_df, final_probe_count)
selected_probes_ip_hop = metis_selection(ip_hop_df, final_probe_count)

# Save results in a clearer format
def save_results(selected_probes, distance_df, filename):
    # Section 1: List of Selected Probes (IP and Probe ID)
    selected_probes_list = pd.DataFrame(
        [(probe, probe_id_map.get(probe, "Unknown")) for probe in selected_probes.index],
        columns=["IP Address", "Probe ID"]
    )

    # Section 2: Distance Matrix for Selected Probes
    selected_distance_matrix = distance_df.loc[selected_probes.index, selected_probes.index].fillna("No Connection")
    
    # Combine both sections in one CSV
    with open(filename, "w") as f:
        f.write("### Selected Probes ###\n")
        selected_probes_list.to_csv(f, index=False)
        
        f.write("\n### Distance Matrix ###\n")
        selected_distance_matrix.to_csv(f, index=True)  

    print(f"Results saved to '{filename}'")

# Save only the probe IDs to separate text files
def save_probe_ids(selected_probes, filename):
    with open(filename, "w") as f:
        f.write("[")
        for probe in selected_probes.index:
            f.write(f"{probe_id_map.get(probe, 'Unknown')},\n")
        f.write("]")
    print(f"Probe IDs saved to '{filename}'")

# Save RTT and IP Hop Probe IDs
save_probe_ids(selected_probes_rtt, "selected_probe_ids_rtt.txt")
save_probe_ids(selected_probes_ip_hop, "selected_probe_ids_ip_hop.txt")


# Save RTT and IP Hop Results Separately
save_results(selected_probes_rtt, rtt_df, "selected_probes_rtt.csv")
save_results(selected_probes_ip_hop, ip_hop_df, "selected_probes_ip_hop.csv")

print(f"Final {final_probe_count} probes saved in separate RTT and IP Hop files.")
