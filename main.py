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

rtt_df = pd.DataFrame(rtt_matrix).fillna(0)
ip_hop_df = pd.DataFrame(ip_hop_matrix).fillna(0)

print(rtt_df)
print(ip_hop_df)
