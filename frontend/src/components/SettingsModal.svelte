<script>
  import { onMount } from 'svelte';
  import { X, Key, HardDrive, FolderPlus, Trash2, Check, Save } from 'lucide-svelte';

  export let isOpen = false;
  export let onClose = () => {};
  export let onNotify = (msg) => {};

  let mistralKey = '';
  let mistralModel = 'mistral-small-latest';
  let scanPaths = [];
  let newPath = '';
  let nasDriveLetter = '';
  let isSaving = false;
  let hasKeyConfigured = false;

  async function loadConfig() {
    try {
      const res = await fetch('/api/config');
      const data = await res.json();
      mistralModel = data.mistral_model || 'mistral-small-latest';
      scanPaths = data.scan_paths || [];
      nasDriveLetter = data.nas_drive_letter || '';
      hasKeyConfigured = data.has_mistral_key;
    } catch (e) {
      console.error(e);
    }
  }

  function addPath() {
    const p = newPath.trim();
    if (p && !scanPaths.includes(p)) {
      scanPaths = [...scanPaths, p];
      newPath = '';
    }
  }

  function removePath(index) {
    scanPaths = scanPaths.filter((_, i) => i !== index);
  }

  async function saveSettings() {
    isSaving = true;
    try {
      const payload = {
        mistral_model: mistralModel,
        scan_paths: scanPaths,
        nas_drive_letter: nasDriveLetter
      };
      if (mistralKey.trim()) {
        payload.mistral_api_key = mistralKey.trim();
      }
      const res = await fetch('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      if (res.ok) {
        onNotify('Configuration enregistrée !');
        mistralKey = '';
        hasKeyConfigured = true;
        onClose();
      }
    } catch (e) {
      onNotify('Erreur d\'enregistrement');
    } finally {
      isSaving = false;
    }
  }

  $: if (isOpen) {
    loadConfig();
  }
</script>

{#if isOpen}
  <!-- Backdrop -->
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm">
    <div class="glass-panel w-full max-w-lg rounded-2xl border border-white/15 bg-zinc-900/90 p-6 shadow-2xl">
      
      <!-- Header -->
      <div class="flex items-center justify-between pb-4 border-b border-white/10">
        <h3 class="text-base font-semibold text-white">Paramètres BiechyFinder</h3>
        <button
          on:click={onClose}
          class="rounded-lg p-1 text-zinc-400 hover:bg-white/10 hover:text-white"
        >
          <X class="h-5 w-5" />
        </button>
      </div>

      <div class="mt-4 space-y-4 text-sm">
        <!-- Clé API Mistral -->
        <div>
          <label for="mistral-key-input" class="block text-xs font-medium text-zinc-300">
            Clé API Mistral (pour l'Assistant IA)
          </label>
          <div class="relative mt-1">
            <input
              id="mistral-key-input"
              type="password"
              bind:value={mistralKey}
              placeholder={hasKeyConfigured ? "•••••••••••••••• (Clé déjà configurée)" : "Collez votre clé API Mistral"}
              class="w-full rounded-xl border border-white/10 bg-zinc-950 px-3 py-2 text-white placeholder-zinc-500 focus:border-indigo-500 focus:outline-none"
            />
          </div>
          <p class="mt-1 text-[11px] text-zinc-500">Obtenez une clé gratuite sur console.mistral.ai</p>
        </div>

        <!-- Lettre de lecteur NAS -->
        <div>
          <label for="nas-drive-input" class="block text-xs font-medium text-zinc-300">
            Lettre de lecteur réseau Windows (Optionnel, ex: Z:)
          </label>
          <input
            id="nas-drive-input"
            type="text"
            bind:value={nasDriveLetter}
            placeholder="Ex: Z:"
            class="mt-1 w-full rounded-xl border border-white/10 bg-zinc-950 px-3 py-2 text-white placeholder-zinc-500 focus:border-indigo-500 focus:outline-none"
          />
        </div>

        <!-- Dossiers du NAS à scanner -->
        <div>
          <label for="scan-path-input" class="block text-xs font-medium text-zinc-300">
            Dossiers du NAS à indexer
          </label>
          <div class="mt-1 flex gap-2">
            <input
              id="scan-path-input"
              type="text"
              bind:value={newPath}
              placeholder="Ex: \\mon-nas\partage ou Z:\Dossier"
              class="flex-1 rounded-xl border border-white/10 bg-zinc-950 px-3 py-2 text-white placeholder-zinc-500 focus:border-indigo-500 focus:outline-none"
            />
            <button
              on:click={addPath}
              class="flex items-center gap-1 rounded-xl bg-indigo-600 px-3 py-2 text-xs font-medium text-white hover:bg-indigo-500"
            >
              <FolderPlus class="h-4 w-4" />
              <span>Ajouter</span>
            </button>
          </div>

          <!-- Liste des dossiers -->
          <div class="mt-2 max-h-32 overflow-y-auto space-y-1">
            {#each scanPaths as path, i}
              <div class="flex items-center justify-between rounded-lg bg-zinc-950/70 px-2.5 py-1.5 text-xs text-zinc-300">
                <span class="truncate">{path}</span>
                <button
                  on:click={() => removePath(i)}
                  class="text-zinc-500 hover:text-red-400"
                >
                  <Trash2 class="h-3.5 w-3.5" />
                </button>
              </div>
            {/each}
          </div>
        </div>
      </div>

      <!-- Footer Buttons -->
      <div class="mt-6 flex justify-end gap-2 border-t border-white/10 pt-4">
        <button
          on:click={onClose}
          class="rounded-xl border border-white/10 bg-zinc-800 px-4 py-2 text-xs font-medium text-zinc-300 hover:bg-zinc-700"
        >
          Annuler
        </button>
        <button
          on:click={saveSettings}
          disabled={isSaving}
          class="flex items-center gap-1.5 rounded-xl bg-indigo-600 px-4 py-2 text-xs font-medium text-white hover:bg-indigo-500 disabled:opacity-50"
        >
          <Save class="h-3.5 w-3.5" />
          <span>{isSaving ? 'Enregistrement...' : 'Enregistrer'}</span>
        </button>
      </div>

    </div>
  </div>
{/if}
