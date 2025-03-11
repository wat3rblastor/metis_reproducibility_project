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

# Combine scores (simple average of RTT and IP hop count scores)
combined_scores = pd.concat([rtt_scores, ip_hop_scores], axis=1)
combined_scores.columns = ["RTT_Score", "IP_Hop_Score"]
combined_scores["AvgDistance"] = combined_scores.mean(axis=1)

combined_scores = combined_scores.sort_values(by="AvgDistance")

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
final_probe_count = 5

# Apply Metis probe selection
selected_probes = metis_selection(rtt_df, final_probe_count)

# Save results in a clearer format
# Save results in a clearer format
def save_results(selected_probes, rtt_df):
    # Section 1: List of Selected Probes
    selected_probes_list = pd.DataFrame(selected_probes.index, columns=["Selected_Probes"])
    
    # Section 2: Distance Matrix for Selected Probes
    selected_distance_matrix = rtt_df.loc[selected_probes.index, selected_probes.index].fillna("No Connection")
    
    # Combine both sections in one CSV
    with open("selected_probes.csv", "w") as f:
        f.write("### Selected Probes ###\n")
        selected_probes_list.to_csv(f, index=False)
        
        f.write("\n### Distance Matrix ###\n")
        selected_distance_matrix.to_csv(f, index=True)  # FIX: Add `index=True`

    print(f"Final results saved to 'selected_probes.csv' in a much better format. sorry ben :(")


save_results(selected_probes, rtt_df)

# Save results in correct format
print(f"Final {final_probe_count} probes saved to 'selected_probes.csv'")