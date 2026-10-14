<script>
  import { onMount, tick } from 'svelte';
  import gsap from 'gsap';
  import { 
    Search, 
    X, 
    Folder, 
    FileText, 
    Code2, 
    Image, 
    Film, 
    Archive, 
    File, 
    ExternalLink, 
    Copy, 
    Check, 
    Clock, 
    Zap,
    Filter
  } from 'lucide-svelte';

  export let onNotify = (msg) => {};

  let query = '';
  let selectedCategory = 'all';
  let results = [];
  let totalCount = 0;
  let elapsedMs = 0;
  let isLoading = false;
  let searchInput;
  let resultsContainer;
  let debounceTimer = null;
  let copiedId = null;

  const categories = [
    { id: 'all', label: 'Tous', icon: Filter },
    { id: 'folders', label: 'Dossiers', icon: Folder },
    { id: 'docs', label: 'Documents', icon: FileText },
    { id: 'code', label: 'Code', icon: Code2 },
    { id: 'images', label: 'Images', icon: Image },
    { id: 'videos', label: 'Vidéos', icon: Film },
    { id: 'archives', label: 'Archives', icon: Archive },
  ];

  async function performSearch(immediate = false) {
    if (debounceTimer) clearTimeout(debounceTimer);

    const execute = async () => {
      isLoading = true;
      try {
        const url = `/api/search?q=${encodeURIComponent(query)}&category=${selectedCategory}&limit=120`;
        const res = await fetch(url);
        const data = await res.json();
        results = data.results || [];
        totalCount = data.total || 0;
        elapsedMs = data.elapsed_ms || 0;

        // Animation d'apparition GSAP en cascade rapide
        await tick();
        animateResults();
      } catch (err) {
        console.error('Erreur de recherche:', err);
      } finally {
        isLoading = false;
      }
    };

    if (immediate) {
      execute();
    } else {
      debounceTimer = setTimeout(execute, 160);
    }
  }

  function animateResults() {
    if (!resultsContainer) return;
    const cards = resultsContainer.querySelectorAll('.result-card');
    if (cards.length > 0) {
      gsap.killTweensOf(cards);
      gsap.fromTo(
        cards,
        { opacity: 0, y: 12 },
        { 
          opacity: 1, 
          y: 0, 
          duration: 0.25, 
          stagger: 0.015, 
          ease: 'power2.out' 
        }
      );
    }
  }

  function handleInput() {
    performSearch(false);
  }

  function clearQuery() {
    query = '';
    performSearch(true);
    if (searchInput) searchInput.focus();
  }

  function selectCategory(catId) {
    selectedCategory = catId;
    performSearch(true);
  }

  async function copyPath(item) {
    try {
      await navigator.clipboard.writeText(item.path);
      copiedId = item.id;
      onNotify(`Copié : ${item.name}`);
      setTimeout(() => {
        if (copiedId === item.id) copiedId = null;
      }, 2000);
    } catch (err) {
      console.error(err);
    }
  }

  async function openItem(item, reveal = false) {
    try {
      const res = await fetch('/api/open', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: item.path, reveal })
      });
      if (res.ok) {
        onNotify(`Ouverture : ${item.name}`);
      } else {
        const err = await res.json();
        onNotify(`Erreur : ${err.detail || 'Impossible d\'ouvrir'}`);
      }
    } catch (err) {
      onNotify('Erreur de connexion au serveur');
    }
  }

  function formatDate(timestamp) {
    if (!timestamp) return '';
    try {
      const d = new Date(timestamp * 1000);
      return d.toLocaleDateString('fr-FR', {
        day: '2-digit',
        month: 'short',
        year: 'numeric'
      });
    } catch {
      return '';
    }
  }

  function getFileIcon(item) {
    if (item.is_dir) return { icon: Folder, color: 'text-amber-400 bg-amber-400/10 border-amber-400/20' };
    const ext = (item.ext || '').toLowerCase();
    if (['pdf', 'doc', 'docx', 'txt', 'rtf', 'odt', 'xlsx', 'xls', 'csv'].includes(ext)) {
      return { icon: FileText, color: 'text-red-400 bg-red-400/10 border-red-400/20' };
    }
    if (['py', 'js', 'ts', 'html', 'css', 'json', 'cpp', 'c', 'sql', 'svelte'].includes(ext)) {
      return { icon: Code2, color: 'text-emerald-400 bg-emerald-400/10 border-emerald-400/20' };
    }
    if (['jpg', 'jpeg', 'png', 'gif', 'svg', 'webp', 'bmp'].includes(ext)) {
      return { icon: Image, color: 'text-purple-400 bg-purple-400/10 border-purple-400/20' };
    }
    if (['mp4', 'mkv', 'avi', 'mov', 'wmv'].includes(ext)) {
      return { icon: Film, color: 'text-blue-400 bg-blue-400/10 border-blue-400/20' };
    }
    if (['zip', 'rar', '7z', 'tar', 'gz', 'iso'].includes(ext)) {
      return { icon: Archive, color: 'text-orange-400 bg-orange-400/10 border-orange-400/20' };
    }
    return { icon: File, color: 'text-zinc-400 bg-zinc-400/10 border-zinc-400/20' };
  }

  // Raccourci clavier global Ctrl+K
  function handleKeyDown(e) {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
      e.preventDefault();
      if (searchInput) {
        searchInput.focus();
        searchInput.select();
      }
    }
  }

  onMount(() => {
    performSearch(true);
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  });
</script>

<div class="mx-auto flex w-full max-w-5xl flex-col gap-6 py-6 px-4 sm:px-6">

  <!-- Spotlight Search Container -->
  <div class="relative w-full">
    <div class="glass-panel relative flex items-center rounded-2xl border border-white/10 shadow-2xl shadow-black/60 transition-all focus-within:border-indigo-500/50 focus-within:ring-2 focus-within:ring-indigo-500/20">
      
      <!-- Loupe -->
      <div class="flex items-center pl-4.5 pr-2 text-zinc-400">
        <Search class="h-5 w-5 {isLoading ? 'animate-pulse text-indigo-400' : ''}" />
      </div>

      <!-- Input de recherche -->
      <input
        bind:this={searchInput}
        bind:value={query}
        on:input={handleInput}
        type="text"
        placeholder="Rechercher des fichiers, dossiers, devis, projets... (Ctrl+K)"
        class="h-14 w-full bg-transparent pr-4 text-base text-white placeholder-zinc-500 focus:outline-none"
      />

      <!-- Actions dans la barre : Clear & Badge raccourci -->
      <div class="flex items-center gap-2 pr-3">
        {#if query}
          <button
            on:click={clearQuery}
            class="flex h-7 w-7 items-center justify-center rounded-lg text-zinc-400 hover:bg-white/10 hover:text-white"
            title="Effacer"
          >
            <X class="h-4 w-4" />
          </button>
        {/if}

        <kbd class="hidden items-center gap-0.5 rounded-lg border border-white/10 bg-zinc-800/80 px-2 py-1 text-[11px] font-semibold text-zinc-400 sm:flex">
          <span class="text-[12px]">⌘</span>K
        </kbd>
      </div>
    </div>
  </div>

  <!-- Filtres rapides par type (Chips modernes) -->
  <div class="flex items-center justify-between gap-2 overflow-x-auto pb-1 scrollbar-none">
    <div class="flex items-center gap-1.5">
      {#each categories as cat}
        {@const IconComp = cat.icon}
        <button
          on:click={() => selectCategory(cat.id)}
          class="flex items-center gap-1.5 rounded-xl border px-3 py-1.5 text-xs font-medium transition-all {selectedCategory === cat.id ? 'border-indigo-500/50 bg-indigo-500/15 text-indigo-200 shadow-sm shadow-indigo-500/20' : 'border-white/5 bg-zinc-900/40 text-zinc-400 hover:border-white/15 hover:bg-zinc-800/60 hover:text-zinc-200'}"
        >
          <IconComp class="h-3.5 w-3.5" />
          <span>{cat.label}</span>
        </button>
      {/each}
    </div>

    <!-- Badge stats de la recherche -->
    {#if totalCount > 0}
      <div class="hidden items-center gap-1.5 rounded-lg border border-white/5 bg-zinc-900/40 px-2.5 py-1 text-[11px] font-medium text-zinc-400 sm:flex">
        <Zap class="h-3 w-3 text-amber-400" />
        <span>{totalCount} résultat{totalCount > 1 ? 's' : ''}</span>
        <span class="text-zinc-600">•</span>
        <span>{elapsedMs} ms</span>
      </div>
    {/if}
  </div>

  <!-- Liste des résultats -->
  <div bind:this={resultsContainer} class="flex flex-col gap-2">
    {#if results.length > 0}
      {#each results as item (item.id)}
        {@const badge = getFileIcon(item)}
        {@const BadgeIcon = badge.icon}
        <div
          class="result-card group glass-panel flex items-center justify-between gap-4 rounded-xl p-3 transition-all hover:bg-zinc-800/60 hover:border-white/15 hover:shadow-lg hover:shadow-black/40"
        >
          <!-- Côté Gauche : Icône + Nom + Chemin -->
          <div class="flex min-w-0 items-center gap-3">
            <div class="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border {badge.color}">
              <BadgeIcon class="h-5 w-5" />
            </div>

            <div class="min-w-0">
              <div class="flex items-center gap-2">
                <span class="truncate text-sm font-medium text-white group-hover:text-indigo-200">
                  {item.name}
                </span>
                {#if item.ext}
                  <span class="rounded bg-white/5 px-1.5 py-0.2 text-[10px] font-semibold uppercase text-zinc-400">
                    {item.ext}
                  </span>
                {/if}
              </div>
              <p class="truncate text-xs text-zinc-500 group-hover:text-zinc-400" title={item.path}>
                {item.path}
              </p>
            </div>
          </div>

          <!-- Côté Droit : Date + Boutons d'action -->
          <div class="flex shrink-0 items-center gap-3">
            {#if item.mod_time}
              <div class="hidden items-center gap-1 text-[11px] text-zinc-500 md:flex">
                <Clock class="h-3 w-3" />
                <span>{formatDate(item.mod_time)}</span>
              </div>
            {/if}

            <div class="flex items-center gap-1.5">
              <!-- Copier le chemin -->
              <button
                on:click={() => copyPath(item)}
                class="flex h-8 w-8 items-center justify-center rounded-lg border border-white/5 bg-zinc-900/60 text-zinc-400 transition-colors hover:border-white/20 hover:bg-zinc-800 hover:text-white"
                title="Copier le chemin réseau"
              >
                {#if copiedId === item.id}
                  <Check class="h-3.5 w-3.5 text-emerald-400" />
                {:else}
                  <Copy class="h-3.5 w-3.5" />
                {/if}
              </button>

              <!-- Ouvrir dans l'explorateur -->
              <button
                on:click={() => openItem(item, true)}
                class="flex items-center gap-1 rounded-lg border border-indigo-500/30 bg-indigo-500/10 px-2.5 py-1.5 text-xs font-medium text-indigo-300 transition-colors hover:bg-indigo-500/20 hover:text-white"
                title="Ouvrir l'emplacement dans l'explorateur Windows"
              >
                <ExternalLink class="h-3.5 w-3.5" />
                <span class="hidden sm:inline">Ouvrir</span>
              </button>
            </div>
          </div>
        </div>
      {/each}
    {:else if !isLoading}
      <div class="glass-panel flex flex-col items-center justify-center rounded-2xl py-16 text-center">
        <div class="flex h-12 w-12 items-center justify-center rounded-2xl bg-zinc-900 text-zinc-500">
          <Search class="h-6 w-6" />
        </div>
        <h3 class="mt-4 text-base font-medium text-zinc-300">Aucun résultat trouvé</h3>
        <p class="mt-1 text-sm text-zinc-500">
          {query ? `Aucun fichier ne correspond à "${query}" dans cette catégorie.` : 'Lancez une recherche ci-dessus.'}
        </p>
      </div>
    {/if}
  </div>

</div>
