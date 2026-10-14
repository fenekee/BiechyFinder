<script>
  import { onMount, tick } from 'svelte';
  import gsap from 'gsap';
  import BackgroundCanvas from './components/BackgroundCanvas.svelte';
  import Navbar from './components/Navbar.svelte';
  import SearchExplorer from './components/SearchExplorer.svelte';
  import AiChat from './components/AiChat.svelte';
  import SettingsModal from './components/SettingsModal.svelte';

  let activeTab = 'search'; // 'search' | 'chat'
  let appState = 'idle'; // 'idle' | 'scanning' | 'ai_thinking'
  let serverStatus = null;
  let isSettingsOpen = false;
  let toastMessage = '';
  let toastVisible = false;
  let toastTimer = null;

  let searchViewRef;
  let chatViewRef;

  function showToast(msg) {
    if (toastTimer) clearTimeout(toastTimer);
    toastMessage = msg;
    toastVisible = true;
    toastTimer = setTimeout(() => {
      toastVisible = false;
    }, 2400);
  }

  async function fetchStatus() {
    try {
      const res = await fetch('/api/status');
      if (res.ok) {
        serverStatus = await res.json();
        // Mettre à jour l'appState si le serveur scanne et qu'on n'est pas en train d'attendre l'IA
        if (serverStatus.app_state === 'scanning') {
          appState = 'scanning';
        } else if (appState !== 'ai_thinking') {
          appState = 'idle';
        }
      }
    } catch (e) {
      // Serveur en cours de démarrage ou injoignable
    }
  }

  async function startScan() {
    try {
      const res = await fetch('/api/scan/start', { method: 'POST' });
      if (res.ok) {
        showToast('Scan du NAS démarré...');
        appState = 'scanning';
        fetchStatus();
      } else {
        const err = await res.json();
        showToast(`Erreur : ${err.detail || 'Impossible de démarrer'}`);
      }
    } catch {
      showToast('Impossible de contacter le serveur');
    }
  }

  // Animation GSAP fluide lors du switch d'onglets (y: 10 -> 0 + fondu)
  async function switchTab(tab) {
    if (activeTab === tab) return;
    activeTab = tab;
    await tick();

    const targetEl = tab === 'search' ? searchViewRef : chatViewRef;
    if (targetEl) {
      gsap.fromTo(
        targetEl,
        { opacity: 0, y: 10 },
        { opacity: 1, y: 0, duration: 0.24, ease: 'power2.out' }
      );
    }
  }

  onMount(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 3500);
    return () => clearInterval(interval);
  });
</script>

<!-- Fond Canvas 2D interactif avec grille de points et ondes GSAP -->
<BackgroundCanvas {appState} />

<div class="relative flex min-h-screen flex-col">
  <!-- Barre de Navigation Haute -->
  <Navbar 
    {activeTab} 
    {serverStatus} 
    onTabChange={switchTab} 
    onOpenSettings={() => isSettingsOpen = true}
    onStartScan={startScan}
  />

  <!-- Vues principales préservant l'état sans rechargement -->
  <main class="flex-1">
    <!-- Vue 1 : Explorateur de fichiers NAS -->
    <div 
      bind:this={searchViewRef}
      class="{activeTab === 'search' ? 'block' : 'hidden'}"
    >
      <SearchExplorer onNotify={showToast} />
    </div>

    <!-- Vue 2 : Assistant IA RAG sur fichiers NAS -->
    <div 
      bind:this={chatViewRef}
      class="{activeTab === 'chat' ? 'block' : 'hidden'}"
    >
      <AiChat 
        onNotify={showToast} 
        onStateChange={(state) => appState = state} 
      />
    </div>
  </main>

  <!-- Modal de Paramètres -->
  <SettingsModal 
    bind:isOpen={isSettingsOpen} 
    onClose={() => isSettingsOpen = false} 
    onNotify={showToast} 
  />

  <!-- Toast Notification Moderne en bas à droite -->
  {#if toastVisible}
    <div class="fixed bottom-6 right-6 z-50 flex items-center gap-2 rounded-xl border border-white/15 bg-zinc-900/90 px-4 py-2.5 text-xs font-medium text-white shadow-2xl backdrop-blur-xl animate-in fade-in slide-in-from-bottom-2">
      <span class="flex h-2 w-2 rounded-full bg-indigo-400"></span>
      <span>{toastMessage}</span>
    </div>
  {/if}
</div>
