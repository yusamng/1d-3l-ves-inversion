<template>
    <div class="min-h-screen flex bg-slate-50 text-slate-800">
        <!-- Sidebar Navigation -->
        <Sidebar 
            :currentTab="page" 
            :isOpen="mobileMenuOpen" 
            @close="mobileMenuOpen = false" 
        />

        <!-- Overlay for mobile drawer -->
        <div v-if="mobileMenuOpen" @click="mobileMenuOpen = false" class="fixed inset-0 bg-black/50 z-40 md:hidden"></div>

        <!-- Main Workspace Content Area -->
        <div class="flex-1 flex flex-col min-w-0">
            <!-- Mobile Top Header Bar -->
            <header class="h-16 bg-white border-b border-slate-200 flex items-center px-6 md:hidden justify-between">
                <span class="font-bold text-slate-800">VES Geophysics</span>
                <button @click="mobileMenuOpen = true" class="p-2 text-slate-600 hover:text-slate-900 focus:outline-none">
                    ☰ Menu
                </button>
            </header>

            <!-- Dynamic View Container -->
            <main class="flex-1 p-6 sm:p-10 max-w-5xl w-full mx-auto">
                <component :is="pageComponent" />
            </main>
        </div>
    </div>
</template>

<script>
import { ref, computed, defineAsyncComponent } from 'vue';

export default {
    name: 'DashboardLayout',
    props: ['page'],
    components: {
        Sidebar: defineAsyncComponent(() => import('./Sidebar.vue')),
        InversionView: defineAsyncComponent(() => import('./InversionView.vue')),
        SyntheticView: defineAsyncComponent(() => import('./SyntheticView.vue')),
        ContactView: defineAsyncComponent(() => import('./ContactView.vue')),
        HowView: defineAsyncComponent(() => import('./HowView.vue')),
    },
    setup(props) {
        const mobileMenuOpen = ref(false);

        const pageComponent = computed(() => {
            if (props.page === 'synthetic') {
                return 'SyntheticView';
            } else if (props.page === 'contact') {
                return 'ContactView';
            } else if (props.page === 'how_to') {
                return 'HowView';
            } else {
                return 'InversionView';
            }
        });

        return {
            mobileMenuOpen,
            pageComponent
        };
    }
};
</script>