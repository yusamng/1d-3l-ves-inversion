import itertools
import base64
import io
import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from flask import Flask, jsonify, redirect, render_template, request, url_for
import torch
import torch.nn as nn
from flask import Response
from matplotlib.ticker import FuncFormatter, NullFormatter
from sklearn.ensemble import RandomForestRegressor

matplotlib.use("Agg")

app = Flask(__name__)

# Global dataframe shared across modules
global_df = None





def generate_ves_curve(L, rho_list, h_list):
  rho = torch.tensor(rho_list, dtype=torch.float32)
  h = torch.tensor(h_list, dtype=torch.float32)
  a = torch.tensor(
      [-0.064, 0.040, -0.015, 0.334, 1.130, 0.334, -0.015, 0.040, -0.064]
  )
  offsets = torch.tensor([10 ** (j / 6.0) for j in range(-4, 5)])
  lambdas = 1.0 / (L.view(-1, 1) * offsets)

  T = rho[2]  # Basement
  for i in range(1, -1, -1):
    tan_h = torch.tanh(lambdas * h[i])
    T = rho[i] * (T + rho[i] * tan_h) / (rho[i] + T * tan_h + 1e-7)

  return torch.sum(a * T, dim=1).numpy()

# INVERSION SECTION HERE
def compute_forward_physics_NL(L, log_rho, log_h):
    rho = torch.pow(10, log_rho)
    h = torch.pow(10, log_h)
    
    a = torch.tensor([-0.064, 0.040, -0.015, 0.334, 1.130, 0.334, -0.015, 0.040, -0.064], dtype=torch.float32)
    offsets = torch.tensor([10**(j / 6.0) for j in range(-4, 5)], dtype=torch.float32)
    lambdas = 1.0 / (L.view(-1, 1) * offsets + 1e-7)
    
    T = rho[-1]
    for i in range(len(h) - 1, -1, -1):
        arg = torch.clamp(lambdas * h[i], max=40.0) 
        tan_h = torch.tanh(arg)
        denom = rho[i] + T * tan_h + 1e-12
        T = rho[i] * (T + rho[i] * tan_h) / denom 
        
    return torch.sum(a * T, dim=1)
  
class GeoelectricPINNNL(nn.Module):
    def __init__(self, init_rhos, init_thicknesses):
        super().__init__()
        self.log_rho = nn.Parameter(torch.log10(torch.tensor(init_rhos, dtype=torch.float32)))
        self.log_h = nn.Parameter(torch.log10(torch.tensor(init_thicknesses, dtype=torch.float32)))
        self.net = nn.Sequential(
            nn.Linear(1, 64), nn.Tanh(),
            nn.Linear(64, 64), nn.Tanh(),
            nn.Linear(64, 1)
        )

    def forward(self, L):
        rho_phys = compute_forward_physics_NL(L, self.log_rho, self.log_h)
        rho_net_log = self.net(torch.log10(L).view(-1, 1)).flatten()
        return rho_phys, rho_net_log

def compute_curvature_weights_torch(AB2_np, rho_np, alpha=2.5):
    """
    Computes log-space second derivative weights to emphasize inflection 
    points (peaks/troughs) to resolve equivalence in 5+ layer models.
    """
    log_ab2 = np.log10(AB2_np)
    log_rho = np.log10(rho_np)
    d1 = np.gradient(log_rho, log_ab2)
    d2 = np.gradient(d1, log_ab2)
    weights = 1.0 + alpha * (np.abs(d2) / (np.max(np.abs(d2)) + 1e-6))
    return torch.tensor(weights, dtype=torch.float32)

def ves_forward_numpy_NL(AB2, rhos, thicknesses):
    a = np.array([-0.064, 0.040, -0.015, 0.334, 1.130, 0.334, -0.015, 0.040, -0.064])
    offsets = np.array([10**(j / 6.0) for j in range(-4, 5)])
    lambdas = 1.0 / (AB2.reshape(-1, 1) * offsets + 1e-7)
    # lambdas = 1.0 / (AB2.reshape(-1, 1) * offsets + 1e-7)
    
    T = np.full_like(lambdas, rhos[-1])
    for r, h in zip(reversed(rhos[:-1]), reversed(thicknesses)):
        arg = np.clip(lambdas * h, None, 40.0)
        tan_h = np.tanh(arg)
        T = r * (T + r * tan_h) / (r + T * tan_h + 1e-12)
        
    return np.sum(a * T, axis=1)
  
def generate_synthetic_data(AB2, n_layers=3, samples_per_type=1500, seed=42):
    np.random.seed(seed)
    
    transitions_list = list(itertools.product(['D', 'U'], repeat=n_layers - 1))
    
    X_train, Y_train = [], []
    for transitions in transitions_list:
        for _ in range(samples_per_type):
            rhos = [10**np.random.uniform(np.log10(15.0), np.log10(500.0))]
            for move in transitions:
                prev = rhos[-1]
                if move == 'D':
                    r_next = 10**np.random.uniform(np.log10(5.0), np.log10(max(prev / 1.3, 5.1)))
                else:
                    r_next = 10**np.random.uniform(np.log10(prev * 1.3), np.log10(5000.0))
                
                # Enforce distinct adjacent resistivities (|rho_i - rho_{i-1}| >= 1.0)
                if abs(r_next - prev) < 1.0:
                    r_next += 2.0
                rhos.append(r_next)

            thicknesses = 10**np.random.uniform(np.log10(0.5), np.log10(20.0), size=n_layers - 1)
            rho_a = ves_forward_numpy_NL(AB2, rhos, thicknesses)
            noise = np.random.normal(0.0, 0.03, size=rho_a.shape)
            rho_a_noisy = np.maximum(rho_a * (1.0 + noise), 1e-3)
            
            X_train.append(np.log10(rho_a_noisy))
            Y_train.append(np.log10(np.concatenate([rhos, thicknesses])))

    return np.array(X_train), np.array(Y_train)

def run_pinn_inversion(AB2_np, rho_np, n_layers=3, epochs=3000, h_min=0.5):
    # Warm start initialization via Random Forest
    X_train, Y_train = generate_synthetic_data(AB2_np, n_layers=n_layers, samples_per_type=2000)
    rf_reg = RandomForestRegressor(n_estimators=250, max_depth=22, random_state=42, n_jobs=-1)
    rf_reg.fit(X_train, Y_train)

    X_field_log = np.log10(rho_np).reshape(1, -1)
    init_params = 10**rf_reg.predict(X_field_log)[0]
    init_rhos = init_params[:n_layers]
    init_thicknesses = init_params[n_layers:]

    # PINN Optimization Initialization
    model = GeoelectricPINNNL(init_rhos, init_thicknesses)
    L_obs = torch.tensor(AB2_np, dtype=torch.float32)
    rho_obs = torch.tensor(rho_np, dtype=torch.float32)
    log_rho_obs = torch.log10(rho_obs)

    L_RATE = 0.003
    # L_RATE = 0.003
    weights_t = compute_curvature_weights_torch(AB2_np, rho_np, alpha=2.5)
    optimizer = torch.optim.Adam(model.parameters(), lr=L_RATE, weight_decay=1e-5)
    
    for epoch in range(epochs + 1):
        optimizer.zero_grad()
        rho_p, rho_n_log = model(L_obs)
        log_p = torch.log10(rho_p + 1e-12)
        
        
        # loss_physics
        # loss_physics = torch.mean((log_p - log_rho_obs)**2)
        loss_physics = torch.mean(weights_t * ((log_p - log_rho_obs)**2))
        
        # Network Consistency Loss
        loss_cons = torch.mean((rho_n_log - log_p)**2)
        
        # Regularization Penalty: Layer Collapse Prevention (h < h_min)
        h_curr = torch.pow(10, model.log_h)
        loss_thick = torch.sum(torch.relu(h_min - h_curr)**2)
        
        # Regularization Penalty: Prevent Identical Adjacent Resistivities
        rho_curr = torch.pow(10, model.log_rho)
        adj_diff = torch.abs(rho_curr[1:] - rho_curr[:-1])
        loss_adj = torch.sum(torch.relu(1.0 - adj_diff)**2)
        
        # Total Weighted Loss Computation
        # total_loss = loss_physics + 0.05 * loss_cons + 10.0 * loss_thick + 5.0 * loss_adj
        total_loss = loss_physics + 0.05 * loss_cons + 0.05 * loss_adj
        
        total_loss.backward()
        optimizer.step()

        if epoch % 1000 == 0:
            with torch.no_grad():
                res = torch.pow(10, model.log_rho).numpy()
                thick = torch.pow(10, model.log_h).numpy()
                res_overburden = res[: len(thick)]
                S_layers = thick / res_overburden
                S_total = np.sum(S_layers)
                rmse_val = np.sqrt(np.mean(((rho_p.numpy() - rho_np) / rho_np)**2)) * 100
    with torch.no_grad():
        res_final = torch.pow(10, model.log_rho).numpy()
        thk_final = torch.pow(10, model.log_h).numpy()
        rho_p_final, _ = model(L_obs)
        rho_p_final_np = rho_p_final.numpy()
        rmse_pct = np.sqrt(np.mean(((rho_p_final_np - rho_np) / rho_np)**2)) * 100

    return {
        'n_layers': n_layers,
        'res_final': res_final,
        'thk_final': thk_final,
        'rho_pred': rho_p_final_np,
        'rmse': rmse_pct
    }

@app.route("/")
def home():
  return redirect(url_for("inversion_page"))

@app.route("/download-synthetic-csv", methods=["GET"])
def download_synthetic_csv():
    global global_df
    if global_df is None:
        return jsonify({"error": "No synthetic data available to export."}), 400
    
    csv_data = global_df.to_csv(index=False)
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-disposition": "attachment; filename=synthetic_ves_data.csv"}
    )

@app.route("/inversion")
def inversion_page():
  return render_template("inversion.html")

@app.route("/run-inversion", methods=["POST"])
def run_inversion():
  global global_df
  if global_df is None:
    return jsonify({"error": "No dataset loaded. Please upload data first."}), 400

  data = request.get_json() or {}
  plot_title = data.get("plotTitle", "1D VES Inversion Result")

  try:
    df_clean = global_df.groupby('AB2', as_index=False)['Rho'].mean().sort_values('AB2')
    AB2_np = df_clean["AB2"].values.astype(float)
    rho_np = df_clean["Rho"].values.astype(float)
    TARGET_LAYERS = 3
    EPOCHS_NUM = 3000
    best_res = run_pinn_inversion(AB2_np, rho_np, n_layers=TARGET_LAYERS, epochs=EPOCHS_NUM)
    res_final = best_res['res_final']
    thk_final = best_res['thk_final']
    rho_p_final_np = best_res['rho_pred']
    rmse_pct = best_res['rmse']
    depths = np.cumsum(thk_final)
    
    H_t = np.sum(thk_final)
    rho_strings = [f"\\rho_{{{i+1}}}={val:.1f}" for i, val in enumerate(res_final)]
    h_strings = [f"h_{{{i+1}}}={val:.1f}" for i, val in enumerate(thk_final)]
    
    rho_legend_label = f"${', '.join(rho_strings)}$ $\\Omega m$"
    h_legend_label = f"${', '.join(h_strings)}$ $m$"
    
    fig, ax = plt.subplots(figsize=(8, 6))
    
    plt.loglog(AB2_np, rho_np, 'ks', alpha=0.7, markersize=5, 
               markerfacecolor='white', markeredgecolor='black',label="Measured Data")
    plt.loglog(AB2_np, rho_np, color='black', linestyle='-', linewidth=1, 
               label='Observed Curve')
    
    # PINN Response Fit
    plt.loglog(AB2_np, rho_p_final_np, 'r-', linewidth=2, 
               label=f'Predicted Curve (RMSE: {rmse_pct:.2f}%)')
    
    # Inferred Model Step Function
    plot_d = np.concatenate(([0.1], np.repeat(depths, 2), [AB2_np.max()]))
    plot_r = np.repeat(res_final, 2)
    plt.step(plot_d, plot_r, 'b--', alpha=0.6, where='post', 
             label=f'Inferred Model Parameters:\n {rho_legend_label}\n {h_legend_label}')
    
    def log_formatter(x, pos):
        if x < 1:
            return f'{x:g}'
        return f'{x:.0f}'

    ax.xaxis.set_major_formatter(FuncFormatter(log_formatter))
    ax.yaxis.set_major_formatter(FuncFormatter(log_formatter))
    ax.xaxis.set_minor_formatter(NullFormatter())
    ax.yaxis.set_minor_formatter(NullFormatter())

    plt.xlabel("AB/2 ($m$)")
    plt.ylabel("Apparent Resistivity ($\\Omega m$)")
    plt.title(plot_title, fontsize=12)
    plt.grid(True, which="both", linestyle='--', alpha=0.5)
    plt.tight_layout()
    plt.legend(frameon=True, shadow=True, loc='best')
    
    img = io.BytesIO()
    plt.savefig(img, format="png", bbox_inches="tight")
    img.seek(0)
    plt.close(fig)
    plot_url = base64.b64encode(img.getvalue()).decode("utf-8")
    return jsonify({"plot_url": plot_url, "message": "Inversion executed successfully."})

  except Exception as e:
    return jsonify({"error": f"Inversion execution error: {str(e)}"}), 500

@app.route("/synthetic")
def synthetic_page():
  return render_template("synthetic.html")

@app.route("/contact")
def contact_page():
    return render_template("index.html")
  
@app.route("/how-to")
def how_to_page():
    return render_template("how_to.html")

@app.route("/upload", methods=["POST"])
def upload_file():
  global global_df
  if "file" not in request.files:
    return jsonify({"error": "No file part in the request."}), 400

  file = request.files["file"]
  if file.filename == "":
    return jsonify({"error": "No selected file."}), 400

  if file and file.filename.endswith(".csv"):
    try:
      global_df = pd.read_csv(file)
      if "AB2" in global_df.columns and "Rho" in global_df.columns:
        fig, ax = plt.subplots(figsize=(8, 6))
        ax.plot(
            global_df["AB2"],
            global_df["Rho"],
            marker="o",
            linestyle="-",
            color="teal",
            linewidth=2,
            markersize=6,
        )
        ax.set_xscale("log")
        ax.set_yscale("log")
        ax.set_xlabel("AB/2 (m)", fontsize=12)
        ax.set_ylabel(
            "Apparent Resistivity ($\Omega$m)", fontsize=12
        )
        ax.set_title("VES Field Curve", fontsize=14)
        ax.grid(True, which="both", ls="--", alpha=0.7)

        img = io.BytesIO()
        plt.savefig(img, format="png", bbox_inches="tight")
        img.seek(0)
        plt.close(fig)

        plot_url = base64.b64encode(img.getvalue()).decode("utf-8")
        return jsonify({"plot_url": plot_url})
      else:
        global_df = None
        return jsonify({
            "error": "CSV must contain columns named 'AB2' and 'Rho'."
        }), 400
    except Exception as e:
      global_df = None
      return jsonify({"error": f"Processing error: {str(e)}"}), 500
  else:
    return jsonify({"error": "Please upload a valid .csv file."}), 400


@app.route("/generate-synthetic", methods=["POST"])
def generate_synthetic():
  global global_df
  data = request.get_json()
  if not data:
    return jsonify({"error": "No data payload provided."}), 400

  try:
    noise_level = float(data.get("noiseLevel", 0)) / 100.0
    rho_list = [
        float(data.get("rho1", 50)),
        float(data.get("rho2", 310)),
        float(data.get("rho3", 980)),
    ]
    h_list = [float(data.get("h1", 1.5)), float(data.get("h2", 15))]
    L = torch.tensor(np.logspace(0, 2.4, 20), dtype=torch.float32)
    rho_clean = generate_ves_curve(L, rho_list, h_list)
    rho_clean = np.maximum(rho_clean, 0.1)

    if noise_level > 0:
      noise = np.random.normal(0, noise_level, size=rho_clean.shape)
      rho_noisy = rho_clean * (1 + noise)
    else:
      rho_noisy = rho_clean

    ab2_numpy = L.numpy()
    global_df = pd.DataFrame({"AB2": ab2_numpy, "Rho": rho_noisy})
    # Draw Plot Here
    fig, ax = plt.subplots(figsize=(8, 6))
    plt.loglog(ab2_numpy, rho_noisy, 'ko',linestyle="-",
            alpha=0.7,markersize=4, markerfacecolor='white',
            markeredgecolor='black',
            label=f'Synthetic Data\n$\\rho_1={rho_list[0]:.1f} \\Omega m, \\rho_2={rho_list[1]:.1f} \\Omega m, \\rho_3={rho_list[2]:.1f} \\Omega m$ \n $h_1={h_list[0]:.1f}m$, $h_2={h_list[1]:.1f}m$')
    
    # ax.plot(
    #     ab2_numpy,
    #     rho_noisy,
    #     marker="o",
    #     linestyle="-",
    #     color="indigo",
    #     linewidth=2,
    #     markersize=6,
    # )
    # ax.set_xscale("log")
    # ax.set_yscale("log")
    
    def log_formatter(x, pos):
        if x < 1:
          return f'{x:g}'
        return f'{x:.0f}'
    ax.xaxis.set_major_formatter(FuncFormatter(log_formatter))
    ax.yaxis.set_major_formatter(FuncFormatter(log_formatter))

    ax.xaxis.set_minor_formatter(NullFormatter())
    ax.yaxis.set_minor_formatter(NullFormatter())
    
    
    plt.xlabel("AB/2 (m)")
    plt.ylabel("Apparent Resistivity (Ωm)")
    plt.title(f"Synthetic 3-Layer VES Data Curve @{noise_level*100:.0f}% Noise Level")
    plt.grid(True, which="both", alpha=0.3)
    plt.tight_layout()
    plt.legend(frameon=True, shadow=True)
    
    img = io.BytesIO()
    plt.savefig(img, format="png", bbox_inches="tight")
    img.seek(0)
    plt.close(fig)

    plot_url = base64.b64encode(img.getvalue()).decode("utf-8")
    return jsonify({"plot_url": plot_url})

  except Exception as e:
    return jsonify({"error": f"Synthetic generation error: {str(e)}"}), 500


if __name__ == "__main__":
  app.run(debug=True, port=5001)