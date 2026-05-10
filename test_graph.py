import pandas as pd
import matplotlib.pyplot as plt
import os

file_list = ['lan.dat', 'wan.dat', 'sat.dat']
colors = {'lan': 'blue', 'wan': 'green', 'sat': 'red'}

# --- ADJUST THIS FOR TPUT SMOOTHNESS ---
TPUT_SMOOTHING_WINDOW = 10 

def parse_data(filename):
    tput_list = []
    cwnd_list = []
    mss_list = [] # Added for MSS tracking
    
    if not os.path.exists(filename):
        print(f"❌ File '{filename}' not found.")
        return None, None, None

    with open(filename, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            parts = line.strip().split()
            if not parts: continue
            
            if 'TPUT' in parts:
                idx = parts.index('TPUT')
                try: 
                    # Mbps as per raw data
                    tput_list.append([float(parts[idx+1]), float(parts[idx+2])])
                except: continue
            elif 'CWND' in parts:
                idx = parts.index('CWND')
                try: 
                    raw_bytes = float(parts[idx+2])
                    # Convert Bytes to KB (1024 bytes = 1 KB)
                    kb_cwnd = raw_bytes / 1024.0
                    cwnd_list.append([float(parts[idx+1]), kb_cwnd])
                    
                    # Convert Bytes to MSS (1 MSS = 536 bytes)
                    mss_val = raw_bytes / 536.0
                    mss_list.append([float(parts[idx+1]), mss_val])
                except: continue

    def finalize_df(data_list, smooth=False, mode='tput'):
        if not data_list:
            return pd.DataFrame(columns=['time', 'value'])
        
        df = pd.DataFrame(data_list, columns=['time', 'value']).sort_values('time')
        
        # 1. Apply smoothing (Throughput only)
        if smooth and len(df) > TPUT_SMOOTHING_WINDOW:
            df['value'] = df['value'].rolling(window=TPUT_SMOOTHING_WINDOW, center=True).mean()
            df['value'] = df['value'].ffill().bfill()

        # 2. Origin/Padding Logic
        min_time = df['time'].min()
        
        if mode == 'tput':
            # Throughput: Simply connect to (0,0)
            if min_time > 0:
                new_row = pd.DataFrame({'time': [0.0], 'value': [0.0]})
                df = pd.concat([new_row, df], ignore_index=True).sort_values('time')
            else:
                df.loc[df['time'] == 0, 'value'] = 0.0
                
        elif mode == 'cwnd':
            # CWND/MSS: Fill with 0 until the first real data point to show idle wire
            if min_time > 0:
                padding = pd.DataFrame({
                    'time': [0.0, min_time],
                    'value': [0.0, 0.0]
                })
                df = pd.concat([padding, df], ignore_index=True).sort_values(['time', 'value'])
            
        return df

    # Finalize all three dataframes
    df_tput = finalize_df(tput_list, smooth=True, mode='tput')
    df_cwnd = finalize_df(cwnd_list, smooth=False, mode='cwnd')
    df_mss = finalize_df(mss_list, smooth=False, mode='cwnd')
    
    return df_tput, df_cwnd, df_mss

script_dir = os.path.dirname(os.path.abspath(__file__))
all_tput_dfs, all_cwnd_dfs, all_mss_dfs = {}, {}, {}

print("--- Calculating Network Statistics ---")

for fname in file_list:
    label = fname.replace('.dat', '')
    df_tput, df_cwnd, df_mss = parse_data(fname)
    if df_tput is None or df_tput.empty: continue
    
    all_tput_dfs[label], all_cwnd_dfs[label], all_mss_dfs[label] = df_tput, df_cwnd, df_mss
    
    # Calculate and print average throughput to terminal in Mbps
    avg_tput = df_tput['value'].mean()
    print(f"Average Throughput ({label.upper()}): {avg_tput:.4f} Mbps")
    
    # Individual Throughput (Mbps)
    plt.figure(figsize=(10, 5))
    plt.plot(df_tput['time'], df_tput['value'], color=colors.get(label, 'black'))
    plt.title(f'Throughput: {label.upper()} (Mbps - Smoothed)')
    plt.xlabel('Time (s)')
    plt.ylabel('Throughput (Mbps)')
    plt.xlim(0, 30); plt.ylim(bottom=0); plt.grid(True, alpha=0.3)
    plt.savefig(os.path.join(script_dir, f'{label}_throughput.png'))
    plt.close()

    # Individual CWND (KB)
    plt.figure(figsize=(10, 5))
    plt.plot(df_cwnd['time'], df_cwnd['value'], color=colors.get(label, 'black'))
    plt.title(f'CWND: {label.upper()} (KB)')
    plt.xlabel('Time (s)')
    plt.ylabel('CWND size (KB)')
    plt.xlim(0, 30); plt.ylim(bottom=0); plt.grid(True, alpha=0.3)
    plt.savefig(os.path.join(script_dir, f'{label}_cwnd.png'))
    plt.close()

# Stacked Throughput Comparison (Mbps)
if all_tput_dfs:
    plt.figure(figsize=(12, 6))
    for label, df in all_tput_dfs.items():
        plt.plot(df['time'], df['value'], label=label, color=colors[label], alpha=1.0)
    plt.title('Stacked Throughput Comparison (Mbps)')
    plt.xlabel('Time (s)'); plt.ylabel('Throughput (Mbps)')
    plt.legend(); plt.xlim(0, 30); plt.ylim(bottom=0); plt.grid(True, alpha=0.3)
    plt.savefig(os.path.join(script_dir, 'stacked_throughput.png'))
    plt.close()

# Stacked CWND Comparison (KB)
if all_cwnd_dfs:
    plt.figure(figsize=(12, 6))
    for label, df in all_cwnd_dfs.items():
        plt.plot(df['time'], df['value'], label=label, color=colors[label], alpha=1.0)
    plt.title('Stacked CWND Comparison (KB)')
    plt.xlabel('Time (s)'); plt.ylabel('CWND Size (KB)')
    plt.legend(); plt.xlim(0, 30); plt.ylim(bottom=0); plt.grid(True, alpha=0.3)
    plt.savefig(os.path.join(script_dir, 'stacked_cwnd.png'))
    plt.close()

# Stacked CWND Comparison (MSS)
if all_mss_dfs:
    plt.figure(figsize=(12, 6))
    for label, df in all_mss_dfs.items():
        plt.plot(df['time'], df['value'], label=label, color=colors[label], alpha=1.0)
    plt.title('Stacked CWND Comparison (MSS)')
    plt.xlabel('Time (s)'); plt.ylabel('CWND Size (MSS)')
    plt.legend(); plt.xlim(0, 30); plt.ylim(bottom=0); plt.grid(True, alpha=0.3)
    plt.savefig(os.path.join(script_dir, 'stacked_cwnd_mss.png'))
    plt.close()

print("\nSuccess. Throughput is in Mbps and CWND is in KB and MSS.")