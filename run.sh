cd /home/hm5701/Documents/PINN/Trial02_Conduction

python3 adaptive_conduction_mapping.py \
  --root "/home/hm5701/Documents/PINN/Trial02_Conduction/raw_data" \
  --devices S1 \
  --out "/home/hm5701/Documents/PINN/Trial02_Conduction/adaptive_results_S1_relaxed2" \
  --min-r2 0.95 \
  --min-signal-current 1e-8 \
  --min-dynamic-decades 0.3 \
  --min-set-ratio 1.05 \
  --min-reset-ratio 1.05 \
  --grid-step 0.1 \
  --plot
