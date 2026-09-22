<template>
    <div class="bg-white p-6 sm:p-8 rounded-2xl shadow-sm border border-slate-200 space-y-6">
        <!-- Main Section Header -->
        <div>
            <h1 class="text-2xl font-bold text-slate-800 tracking-tight mb-2">Run 1D 3-Layer VES Inversion</h1>
            <p class="text-slate-600 text-sm">Upload Vertical Electrical Sounding (VES) CSV file, upload the data, and run inversion.</p>
        </div>

        <!-- Step 1: File Uploader Area (Standalone input) -->
        <div class="bg-slate-50 p-6 rounded-xl border border-slate-200/80 space-y-3">
            <h3 class="text-sm font-semibold text-slate-700">Step 1: Select VES Data File (.csv)</h3>
            <input 
                type="file" 
                @change="handleFileChange" 
                accept=".csv" 
                required 
                class="block w-full text-sm text-slate-500 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-semibold file:bg-sky-50 file:text-sky-700 hover:file:bg-sky-100 cursor-pointer bg-white p-3 rounded-lg border border-slate-300"
            >
        </div>

        <!-- Spinner Loading Animation -->
        <div v-if="loading" class="text-center py-6">
            <div class="inline-block animate-spin rounded-full h-8 w-8 border-4 border-slate-200 border-t-sky-600 mb-2"></div>
            <p class="text-xs text-slate-500 font-medium">Processing CSV and configuring dataset...</p>
        </div>

        <!-- Error Message Display -->
        <div v-if="errorMessage" class="bg-red-50 border border-red-200 text-red-700 p-4 rounded-xl text-sm font-medium">
            {{ errorMessage }}
        </div>

        <!-- Step 2: Upload Action & Optional Plot View -->
        <div class="bg-slate-50/50 p-6 rounded-xl border border-slate-200 space-y-4">
            <div class="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
                <div>
                    <h3 class="text-sm font-semibold text-slate-700 mb-1">Step 2: Upload Data & Inspect Curve</h3>
                    <p class="text-xs text-slate-500">Send data to the backend model and optionally toggle the apparent resistivity plot.</p>
                </div>
                <div class="flex items-center gap-3 w-full sm:w-auto">
                    <button 
                        @click="uploadData"
                        :disabled="!selectedFile || loading"
                        class="flex-1 sm:flex-none px-5 py-2.5 bg-sky-600 text-white font-medium text-sm rounded-lg shadow-sm hover:bg-sky-700 transition disabled:bg-slate-300 disabled:cursor-not-allowed"
                    >
                        <span v-if="loading">Uploading...</span>
                        <span v-else>Upload Data</span>
                    </button>
                    <button 
                        v-if="dataLoaded"
                        @click="togglePlot"
                        class="px-4 py-2.5 bg-slate-200 text-slate-700 font-medium text-sm rounded-lg hover:bg-slate-300 transition"
                    >
                        {{ showPlot ? 'Hide Plot' : 'View Plot' }}
                    </button>
                </div>
            </div>

            <!-- Success Indicator -->
            <div v-if="dataLoaded" class="text-xs font-semibold text-emerald-600 flex items-center gap-1.5 pt-1">
                ✓ Data successfully loaded and ready for inversion.
            </div>

            <!-- Plot Display Container -->
            <div v-if="showPlot && plotUrl" class="mt-4 pt-4 border-t border-slate-200 text-center">
                <h4 class="text-xs font-semibold text-slate-600 mb-3 uppercase tracking-wider">Apparent Resistivity Curve</h4>
                <img :src="'data:image/png;base64,' + plotUrl" alt="VES Log-Log Curve" class="mx-auto max-w-full h-auto rounded-lg border border-slate-200 bg-white shadow-xs">
            </div>
        </div>

        <hr class="border-slate-200">

        <!-- Step 3: Run Inversion Section -->
        <div class="space-y-4">
            <h3 class="text-sm font-semibold text-slate-700">Step 3: Execute Inversion</h3>
            
            <!-- Plot Title Input -->
            <div>
                <label class="block text-xs font-semibold text-slate-600 mb-1">Plot Title</label>
                <input 
                    type="text" 
                    v-model="plotTitle" 
                    :disabled="!dataLoaded || inversionLoading"
                    placeholder="Enter plot title..." 
                    class="w-full sm:w-96 px-3 py-2 bg-white border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500"
                >
            </div>

            <div>
                <button 
                    @click="executeInversion"
                    :disabled="!dataLoaded || inversionLoading"
                    class="px-6 py-2.5 bg-emerald-600 text-white font-medium rounded-lg shadow-sm hover:bg-emerald-700 transition disabled:bg-slate-300 disabled:cursor-not-allowed"
                >
                    <span v-if="inversionLoading">Running ...</span>
                    <span v-else>Run Inversion</span>
                </button>
            </div>

            <!-- Inversion Loading Spinner -->
            <div v-if="inversionLoading" class="text-center py-4">
                <div class="inline-block animate-spin rounded-full h-6 w-6 border-3 border-slate-200 border-t-emerald-600 mb-1"></div>
                <p class="text-xs text-slate-500 font-medium">Executing optimization...</p>
            </div>

            <!-- Inversion Test Plot Result & Export Option -->
            <div v-if="inversionPlotUrl" class="mt-4 pt-4 border-t border-slate-200 text-center bg-slate-50/50 p-4 rounded-xl border space-y-4">
                <h4 class="text-xs font-semibold text-slate-600 uppercase tracking-wider">Inversion Result Plot</h4>
                <img :src="'data:image/png;base64,' + inversionPlotUrl" alt="Inversion Test Plot" class="mx-auto max-w-full h-auto rounded-lg border border-slate-200 bg-white shadow-xs">
                
                <div>
                    <button 
                        @click="exportInversionPng"
                        class="inline-flex items-center gap-2 px-4 py-2 bg-sky-600 text-white font-medium text-xs rounded-lg shadow-sm hover:bg-sky-700 transition"
                    >
                        📥 Export Figure (.png)
                    </button>
                </div>
            </div>
        </div>
    </div>
</template>

<script>
import { ref } from 'vue';

export default {
    name: 'InversionView',
    setup() {
        const selectedFile = ref(null);
        const plotUrl = ref(null);
        const errorMessage = ref(null);
        const loading = ref(false);
        const dataLoaded = ref(false);
        const showPlot = ref(false);

        // Step 3 state properties
        const plotTitle = ref('');
        const inversionLoading = ref(false);
        const inversionPlotUrl = ref(null);

        const handleFileChange = (event) => {
            selectedFile.value = event.target.files[0];
            dataLoaded.value = false;
            plotUrl.value = null;
            showPlot.value = false;
            errorMessage.value = null;
            inversionPlotUrl.value = null;
        };

        const uploadData = async () => {
            if (!selectedFile.value) return;

            loading.value = true;
            errorMessage.value = null;
            dataLoaded.value = false;
            plotUrl.value = null;
            showPlot.value = false;
            inversionPlotUrl.value = null;

            const formData = new FormData();
            formData.append('file', selectedFile.value);

            try {
                const response = await fetch('/upload', {
                    method: 'POST',
                    body: formData
                });

                const data = await response.json();

                if (!response.ok) {
                    throw new Error(data.error || 'Failed to process file.');
                }

                plotUrl.value = data.plot_url;
                dataLoaded.value = true; // Activates Run Inversion button
            } catch (err) {
                errorMessage.value = err.message;
            } finally {
                loading.value = false;
            }
        };

        const togglePlot = () => {
            showPlot.value = !showPlot.value;
        };

        const executeInversion = async () => {
            inversionLoading.value = true;
            inversionPlotUrl.value = null;

            try {
                const response = await fetch('/run-inversion', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ plotTitle: plotTitle.value })
                });

                const data = await response.json();

                if (!response.ok) {
                    throw new Error(data.error || 'Failed to execute inversion.');
                }

                inversionPlotUrl.value = data.plot_url;
            } catch (err) {
                errorMessage.value = err.message;
            } finally {
                inversionLoading.value = false;
            }
        };

        const exportInversionPng = () => {
            const filename = prompt("Enter filename for figure export:", "ves_inversion_result.png");
            if (!filename) return;

            try {
                const byteCharacters = atob(inversionPlotUrl.value);
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
            selectedFile,
            plotUrl,
            errorMessage,
            loading,
            dataLoaded,
            showPlot,
            plotTitle,
            inversionLoading,
            inversionPlotUrl,
            handleFileChange,
            uploadData,
            togglePlot,
            executeInversion,
            exportInversionPng
        };
    }
};
</script>