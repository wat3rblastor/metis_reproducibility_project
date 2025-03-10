import json
import numpy as np
import pandas as pd
import os
from math import inf

ip_list = []
rtt_matrix = {}
ip_hop_matrix = {}

for root, dirs, files in os.walk("PT"):
    for file in files:
        if file.endswith(".json"):
            file_path = os.path.join(root, file)

            with open(file_path, "r") as f:
                try:
                    for line in f:
                        try:
                            data = json.loads(line)
                            destination_ip_responded = data["destination_ip_responded"]

                            if not destination_ip_responded:
                                continue

                            src_ip = data["src_addr"]
                            dst_ip = data["dst_addr"]

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

rtt_df = pd.DataFrame(rtt_matrix).fillna(np.inf)
ip_hop_df = pd.DataFrame(ip_hop_matrix).fillna(np.inf)

print(rtt_df)
print(ip_hop_df)

# filter our using the distance calculation
rtt_df = rtt_df.replace("NA", np.nan).astype(float)
ip_hop_df = ip_hop_df.replace("NA", np.nan).astype(float)

# choose the number of neighbors we want
k = 5

def compute_closeness(matrix):
    avg_distances = []
    for probe in matrix.index:
        distances = matrix.loc[probe].dropna().sort_values()
        nearest_distances = distances[:k]  # Take k-nearest
        avg_dist = nearest_distances.mean()
        avg_distances.append((probe, avg_dist))
    
    return pd.DataFrame(avg_distances, columns=["Probe", "AvgDistance"]).set_index("Probe")



# compute redundancy scores (lower = more redundant)
rtt_scores = compute_closeness(rtt_df)
ip_hop_scores = compute_closeness(ip_hop_df)

# Combine scores (simple average of RTT and IP hop count scores)
combined_scores = (rtt_scores + ip_hop_scores) / 2
combined_scores = combined_scores.sort_values(by="AvgDistance")

def metis_selection(matrix, target_size):
    selected_probes = matrix.copy()
    
    while len(selected_probes) > target_size:
        scores = compute_closeness(selected_probes)  # Recalculate scores
        probe_to_remove = scores.idxmin()["AvgDistance"]  # Remove the most redundant probe
        selected_probes = selected_probes.drop(index=probe_to_remove, columns=probe_to_remove)
    
    return selected_probes

# Define the final number of probes (adjust as needed)
final_probe_count = 5

# Apply Metis probe selection
selected_probes = metis_selection(rtt_df, final_probe_count)

# Save results
selected_probes.to_csv("selected_probes.csv")
print(f"Final {final_probe_count} probes saved to 'selected_probes.csv'")



