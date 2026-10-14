<script>
  import { onMount, afterUpdate } from 'svelte';
  import gsap from 'gsap';
  import { 
    HardDrive, 
    Sparkles, 
    Search, 
    RefreshCw, 
    Database, 
    CheckCircle2, 
    AlertCircle,
    Settings
  } from 'lucide-svelte';

  export let activeTab = 'search'; // 'search' | 'chat'
  export let onTabChange = (tab) => {};
  export let serverStatus = null;
  export let onOpenSettings = () => {};
  export let onStartScan = () => {};

  let pillElement;
  let btnSearch;
  let btnChat;

  // Animation GSAP de la pilule d'onglet
  function updatePillPosition() {
    if (!pillElement) return;
    const targetBtn = activeTab === 'search' ? btnSearch : btnChat;
    if (targetBtn) {
      const parentRect = targetBtn.parentElement.getBoundingClientRect();
      const rect = targetBtn.getBoundingClientRect();
      gsap.to(pillElement, {
        x: rect.left - parentRect.left,
        width: rect.width,
        duration: 0.28,
        ease: 'power2.out'
      });
    }
  }

  $: if (activeTab && pillElement) {
    updatePillPosition();
  }

  onMount(() => {
    updatePillPosition();
    window.addEventListener('resize', updatePillPosition);
    return () => window.removeEventListener('resize', updatePillPosition);
  });

  $: isScanning = serverStatus?.app_state === 'scanning' || serverStatus?.scan_progress?.is_scanning;
  $: isAiThinking = serverStatus?.app_state === 'ai_thinking';
  $: totalIndexed = serverStatus?.total_items ? serverStatus.total_items.toLocaleString('fr-FR') : '0';
</script>

<header class="sticky top-0 z-40 w-full border-b border-white/10 bg-zinc-950/70 backdrop-blur-xl">
  <div class="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
    
    <!-- Logo & Statut NAS -->
    <div class="flex items-center gap-4">
      <div class="flex items-center gap-2.5">
        <div class="relative flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-tr from-indigo-600 to-violet-500 shadow-lg shadow-indigo-500/20">
          <HardDrive class="h-4.5 w-4.5 text-white" />
          {#if isScanning}
            <span class="absolute -top-1 -right-1 flex h-3 w-3">
              <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-sky-400 opacity-75"></span>
              <span class="relative inline-flex rounded-full h-3 w-3 bg-sky-500"></span>
            </span>
          {:else if isAiThinking}
            <span class="absolute -top-1 -right-1 flex h-3 w-3">
              <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-violet-400 opacity-75"></span>
              <span class="relative inline-flex rounded-full h-3 w-3 bg-violet-500"></span>
            </span>
          {/if}
        </div>
        <div>
          <div class="flex items-center gap-2">
            <span class="text-base font-semibold tracking-tight text-white">BiechyFinder</span>
            <span class="rounded-md border border-indigo-500/30 bg-indigo-500/10 px-1.5 py-0.5 text-[10px] font-medium text-indigo-300">
              v5.6 Web
            </span>
          </div>
          <p class="text-[11px] text-zinc-400">NAS Fast Search & IA RAG</p>
        </div>
      </div>

      <!-- Séparateur vertical -->
      <div class="hidden h-5 w-[1px] bg-white/10 sm:block"></div>

      <!-- Badge statut NAS -->
      <div class="hidden items-center gap-2 rounded-full border border-white/5 bg-zinc-900/60 px-2.5 py-1 text-xs text-zinc-300 sm:flex">
        {#if serverStatus?.status === 'connected'}
          <span class="h-2 w-2 rounded-full bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.7)]"></span>
          <span>{totalIndexed} éléments</span>
          {#if serverStatus?.db_size_mb}
            <span class="text-zinc-500">• {serverStatus.db_size_mb} Mo</span>
          {/if}
        {:else}
          <span class="h-2 w-2 rounded-full bg-amber-500"></span>
          <span class="text-amber-400">Base non trouvée</span>
        {/if}
      </div>
    </div>

    <!-- Navigation par Onglets avec Pilule GSAP -->
    <div class="relative flex items-center rounded-xl border border-white/10 bg-zinc-900/80 p-1 backdrop-blur-md">
      <!-- Pilule glissante animée -->
      <div
        bind:this={pillElement}
        class="absolute top-1 bottom-1 rounded-lg bg-gradient-to-r from-indigo-600/90 to-violet-600/90 shadow-md shadow-indigo-500/25 pointer-events-none"
        style="left: 0; width: 0;"
      ></div>

      <!-- Onglet 1: Explorateur -->
      <button
        bind:this={btnSearch}
        on:click={() => onTabChange('search')}
        class="relative z-10 flex items-center gap-2 rounded-lg px-4 py-1.5 text-xs font-medium transition-colors {activeTab === 'search' ? 'text-white' : 'text-zinc-400 hover:text-zinc-200'}"
      >
        <Search class="h-3.5 w-3.5" />
        <span>Explorateur NAS</span>
      </button>

      <!-- Onglet 2: Assistant IA -->
      <button
        bind:this={btnChat}
        on:click={() => onTabChange('chat')}
        class="relative z-10 flex items-center gap-2 rounded-lg px-4 py-1.5 text-xs font-medium transition-colors {activeTab === 'chat' ? 'text-white' : 'text-zinc-400 hover:text-zinc-200'}"
      >
        <Sparkles class="h-3.5 w-3.5 {isAiThinking ? 'text-violet-300 animate-spin' : ''}" />
        <span>Assistant IA</span>
        {#if serverStatus?.has_mistral_key}
          <span class="h-1.5 w-1.5 rounded-full bg-emerald-400"></span>
        {/if}
      </button>
    </div>

    <!-- Actions Droite : Rescan & Paramètres -->
    <div class="flex items-center gap-2.5">
      <!-- Bouton Rescan -->
      <button
        on:click={onStartScan}
        disabled={isScanning}
        class="flex items-center gap-1.5 rounded-lg border border-white/10 bg-zinc-900/60 px-3 py-1.5 text-xs font-medium text-zinc-300 transition-all hover:bg-zinc-800 hover:text-white disabled:opacity-50"
        title="Lancer l'indexation du NAS"
      >
        <RefreshCw class="h-3.5 w-3.5 {isScanning ? 'animate-spin text-sky-400' : ''}" />
        <span class="hidden md:inline">
          {isScanning ? 'Scan en cours...' : 'Indexer le NAS'}
        </span>
      </button>

      <!-- Bouton Paramètres -->
      <button
        on:click={onOpenSettings}
        class="flex h-8 w-8 items-center justify-center rounded-lg border border-white/10 bg-zinc-900/60 text-zinc-400 transition-colors hover:bg-zinc-800 hover:text-white"
        title="Paramètres de configuration"
      >
        <Settings class="h-4 w-4" />
      </button>
    </div>

  </div>

  <!-- Barre de progression du scan (visible uniquement lors du scan) -->
  {#if isScanning}
    <div class="h-1 w-full bg-zinc-900 overflow-hidden">
      <div class="h-full bg-gradient-to-r from-sky-500 via-indigo-500 to-violet-500 animate-pulse w-full"></div>
    </div>
  {/if}
</header>
