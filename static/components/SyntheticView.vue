<template>
    <div class="bg-white p-6 sm:p-8 rounded-2xl shadow-sm border border-slate-200 space-y-6">
        <!-- Main Section Header -->
        <div>
            <h1 class="text-2xl font-bold text-slate-800 tracking-tight mb-2">3-Layer Synthetic Data Generation</h1>
            <p class="text-slate-600 text-sm">Configure subsurface layer resistivities, thicknesses, and noise levels to generate a synthetic 3-layer VES curve.</p>
        </div>

        <!-- Layer & Noise Configuration Form -->
        <form @submit.prevent="generateSyntheticData" class="space-y-4 bg-slate-50 p-6 rounded-xl border border-slate-200/80">
            <h3 class="text-sm font-semibold text-slate-700 mb-2">Model Parameters</h3>
            
            <div class="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <div>
                    <label class="block text-xs font-semibold text-slate-600 mb-1">Layer 1 Resistivity (ρ₁)</label>
                    <input type="number" v-model.number="form.rho1" step="any" required class="w-full px-3 py-2 bg-white border border-slate-300 rounded-lg text-sm">
                </div>
                <div>
                    <label class="block text-xs font-semibold text-slate-600 mb-1">Layer 2 Resistivity (ρ₂)</label>
                    <input type="number" v-model.number="form.rho2" step="any" required class="w-full px-3 py-2 bg-white border border-slate-300 rounded-lg text-sm">
                </div>
                <div>
                    <label class="block text-xs font-semibold text-slate-600 mb-1">Basement Resistivity (ρ₃)</label>
                    <input type="number" v-model.number="form.rho3" step="any" required class="w-full px-3 py-2 bg-white border border-slate-300 rounded-lg text-sm">
                </div>
            </div>

            <div class="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <div>
                    <label class="block text-xs font-semibold text-slate-600 mb-1">Layer 1 Thickness (h₁)</label>
                    <input type="number" v-model.number="form.h1" step="any" required class="w-full px-3 py-2 bg-white border border-slate-300 rounded-lg text-sm">
                </div>
                <div>
                    <label class="block text-xs font-semibold text-slate-600 mb-1">Layer 2 Thickness (h₂)</label>
                    <input type="number" v-model.number="form.h2" step="any" required class="w-full px-3 py-2 bg-white border border-slate-300 rounded-lg text-sm">
                </div>
                <div>
                    <label class="block text-xs font-semibold text-slate-600 mb-1">Gaussian Noise Level (%)</label>
                    <select v-model.number="form.noiseLevel" class="w-full px-3 py-2 bg-white border border-slate-300 rounded-lg text-sm">
                        <option v-for="n in [0,1,2,3,4,5,6,7,8,9,10]" :key="n" :value="n">{{ n }}%</option>
                    </select>
                </div>
            </div>

            <div class="pt-2">
                <button 
                    type="submit" 
                    :disabled="loading"
                    class="px-6 py-2.5 bg-sky-600 text-white font-medium text-sm rounded-lg shadow-sm hover:bg-sky-700 transition disabled:bg-slate-300 disabled:cursor-not-allowed"
                >
                    <span v-if="loading">Generating...</span>
                    <span v-else>Generate Synthetic Curve</span>
                </button>
            </div>
        </form>

        <!-- Spinner Loading Animation -->
        <div v-if="loading" class="text-center py-6">
            <div class="inline-block animate-spin rounded-full h-8 w-8 border-4 border-slate-200 border-t-sky-600 mb-2"></div>
            <p class="text-xs text-slate-500 font-medium">Computing forward modeling response...</p>
        </div>

        <!-- Error Message Display -->
        <div v-if="errorMessage" class="bg-red-50 border border-red-200 text-red-700 p-4 rounded-xl text-sm font-medium">
            {{ errorMessage }}
        </div>

        <!-- Plot Display Container & Custom Export Buttons -->
        <div v-if="plotUrl" class="bg-slate-50/50 p-6 rounded-xl border border-slate-200 text-center space-y-4">
            <h4 class="text-xs font-semibold text-slate-600 uppercase tracking-wider">Synthetic Apparent Resistivity Curve</h4>
            <img :src="'data:image/png;base64,' + plotUrl" alt="Synthetic VES Curve" class="mx-auto max-w-full h-auto rounded-lg border border-slate-200 bg-white shadow-xs">
            
            <div class="flex flex-wrap items-center justify-center gap-3 pt-2">
                <button 
                    @click="exportCsv"
                    class="inline-flex items-center gap-2 px-4 py-2 bg-emerald-600 text-white font-medium text-xs rounded-lg shadow-sm hover:bg-emerald-700 transition"
                >
                    📥 Export Synthetic Data (.csv)
                </button>
                <button 
                    @click="exportPng"
                    class="inline-flex items-center gap-2 px-4 py-2 bg-sky-600 text-white font-medium text-xs rounded-lg shadow-sm hover:bg-sky-700 transition"
                >
                    🖼️ Export Figure (.png)
                </button>
            </div>
        </div>
    </div>
</template>

<script>
import { reactive, ref } from 'vue';

export default {
    name: 'SyntheticView',
    setup() {
        const form = reactive({
            rho1: 50,
            rho2: 310,
            rho3: 980,
            h1: 1.5,
            h2: 15,
            noiseLevel: 0
        });

        const plotUrl = ref(null);
        const errorMessage = ref(null);
        const loading = ref(false);

        const generateSyntheticData = async () => {
            loading.value = true;
            errorMessage.value = null;
            plotUrl.value = null;

            try {
                const response = await fetch('/generate-synthetic', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(form)
                });

                const data = await response.json();

                if (!response.ok) {
                    throw new Error(data.error || 'Failed to generate synthetic data.');
                }

                plotUrl.value = data.plot_url;
            } catch (err) {
                errorMessage.value = err.message;
            } finally {
                loading.value = false;
            }
        };

        const exportCsv = async () => {
            const filename = prompt("Enter filename for CSV export:", "synthetic_ves_data.csv");
            if (!filename) return;

            try {
                const response = await fetch('/download-synthetic-csv');
                if (!response.ok) throw new Error('Failed to fetch CSV data.');
                
                const blob = await response.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = filename.endsWith('.csv') ? filename : filename + '.csv';
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                window.URL.revokeObjectURL(url);
            } catch (err) {
                alert(err.message);
            }
        };

        const exportPng = () => {
            const filename = prompt("Enter filename for figure export:", "synthetic_ves_curve.png");
            if (!filename) return;

            try {
                const byteCharacters = atob(plotUrl.value);
                const byteNumbers = new Array(byteCharacters.length);
                for (let i = 0; i < byteCharacters.length; i++) {
                    byteNumbers[i] = byteCharacters.charCodeAt(i);
                }
                const byteArray = new Uint8Array(byteNumbers);
                const blob = new Blob([byteArray], { type: 'image/png' });
                const url = window.URL.createObjectURL(blob);
                
                const a = document.createElement('a');
                a.href = url;
                a.download = filename.endsWith('.png') ? filename : filename + '.png';
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                window.URL.revokeObjectURL(url);
            } catch (err) {
                alert('Failed to export figure.');
            }
        };

        return {
            form,
            plotUrl,
            errorMessage,
            loading,
            generateSyntheticData,
            exportCsv,
            exportPng
        };
    }
};
</script>