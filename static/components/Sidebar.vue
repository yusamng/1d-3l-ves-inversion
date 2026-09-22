<template>
    <aside :class="[
        'fixed inset-y-0 left-0 z-50 w-64 bg-slate-900 text-slate-300 transform transition-transform duration-200 ease-in-out md:translate-x-0 md:sticky md:top-0 md:h-screen md:overflow-y-auto flex flex-col justify-between',
        isOpen ? 'translate-x-0' : '-translate-x-full'
    ]">
        <div>
            <div class="flex items-center justify-between h-16 px-6 bg-slate-950 text-white font-bold text-lg border-b border-slate-800">
                <!-- <span>3-Layer VES Inversion & Modeling App</span> -->
                <div class="flex items-center gap-3">
                <!-- Replace with your actual image path or URL -->
                <img src="/static/logo.png" alt="3-Layer VES Geophysics Logo" class="h-12 w-auto object-contain">
                </div>

                <button @click="$emit('close')" class="md:hidden text-slate-400 hover:text-white">
                    ✕
                </button>
            </div>

            <nav class="p-4 space-y-2">
                <a 
                    href="/inversion" 
                    :class="['w-full flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium transition', currentTab === 'inversion' ? 'bg-sky-600 text-white shadow-sm' : 'hover:bg-slate-800 text-slate-300']"
                >
                    ⚡ Run Inversion
                </a>
                <a 
                    href="/synthetic" 
                    :class="['w-full flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium transition', currentTab === 'synthetic' ? 'bg-sky-600 text-white shadow-sm' : 'hover:bg-slate-800 text-slate-300']"
                >
                    ⚙️ Synthetic Data Generation
                </a>
            </nav>
        </div>

        <div class="p-4 border-t border-slate-800 space-y-3">
        <!-- Contact Me Button -->
        <a 
            href="/how-to" 
            :class="['w-full flex items-center justify-center gap-2 px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white font-medium text-xs rounded-lg transition shadow-sm', currentTab === 'how-to' ? 'bg-sky-600 text-white shadow-sm' : 'hover:bg-slate-800 text-slate-300']"
        >
            📺 How to use the App
        </a>

        <a 
            href="/contact" 
            :class="['w-full flex items-center justify-center gap-2 px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white font-medium text-xs rounded-lg transition shadow-sm' , currentTab === 'contact' ? 'bg-sky-600 text-white shadow-sm' : 'hover:bg-slate-800 text-slate-300']"
        >
            ✉️ Contact Us
        </a>

        <!-- Copyright Footer -->
        <div class="text-center text-[11px] text-slate-500 pt-1">
            Copyright © 2026 Yusuf A. Musa
        </div>
    </div>
        <!-- Sidebar Footer Note -->
        <!-- <div class="p-4 border-t border-slate-800 text-xs text-slate-500">
            Copyright © 2026 Dr. Yusuf A. Musa
        </div> -->
    </aside>
</template>

<script>
export default {
    name: 'Sidebar',
    props: ['currentTab', 'isOpen']
};
</script>